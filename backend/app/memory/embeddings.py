from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.embedding_models import DEFAULT_EMBEDDING_MODEL, EMBEDDING_MODELS
from app.ai.providers import GeminiProvider, OpenAIEmbeddingProvider
from app.ai.routing import AIModelRoute
from app.ai.types import AICapability, AIEmbeddingRequest, AIEmbeddingResponse, AIProvider, AIProviderError
from app.core.config import Settings
from app.database.models import UserIntelligenceSettings, UserProfile
from app.intelligence_settings.provider_credentials import ProviderSecretStore


EMBEDDING_VERSION = "memory-embedding-v2"


class EmbeddingService:
    def __init__(self, settings: Settings, gateway: AIGateway, secret_store: ProviderSecretStore | None = None):
        self.settings = settings
        self.gateway = gateway
        self.secret_store = secret_store or ProviderSecretStore()

    def route_for_user(self, db: Session, user: UserProfile) -> AIModelRoute:
        return self._selection(db, user)[0]

    def _selection(self, db: Session, user: UserProfile, *, provider_override: str | None = None, model_override: str | None = None) -> tuple[AIModelRoute, bool]:
        if provider_override is not None:
            return self._override_route(provider_override, model_override), True
        row = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        preference = (row.metadata_json or {}).get("embedding_settings") if row is not None else None
        provider = preference.get("provider", "default") if isinstance(preference, dict) else "default"
        if provider == "default":
            return self.gateway.router.resolve(AICapability.embedding), False
        if provider not in EMBEDDING_MODELS:
            raise AIProviderError("invalid_embedding_settings", "The saved embedding provider setting is invalid.")
        model = preference.get("model") or DEFAULT_EMBEDDING_MODEL[provider]
        if model not in EMBEDDING_MODELS[provider]:
            raise AIProviderError("invalid_embedding_settings", "The saved embedding model setting is invalid.")
        return AIModelRoute(provider=provider, model=model, capability=AICapability.embedding, temperature=0.0), True

    @staticmethod
    def compatible(response: AIEmbeddingResponse, target) -> bool:
        if not response.vectors:
            return False
        return (
            response.provider == getattr(target, "embedding_provider", None)
            and response.model == getattr(target, "embedding_model", None)
            and response.dimensions == getattr(target, "embedding_dimension", None)
            and len(response.vectors[0]) == response.dimensions
        )

    def embed(
        self,
        db: Session,
        user: UserProfile,
        texts: list[str],
        *,
        task_type: str,
        request_id: str | None = None,
        optional: bool = True,
        provider_override: str | None = None,
        model_override: str | None = None,
    ):
        route, is_explicit = self._selection(
            db, user, provider_override=provider_override, model_override=model_override,
        )
        provider: AIProvider | None = None
        if provider_override is not None or route.provider in EMBEDDING_MODELS:
            if is_explicit:
                try:
                    key = self.secret_store.get(db, user, route.provider)
                except HTTPException as exc:
                    raise AIProviderError("embedding_provider_not_configured", str(exc.detail)) from None
            elif route.provider == "openai":
                key = self.settings.openai_api_key.get_secret_value() if self.settings.openai_api_key else None
            else:
                key = self.settings.gemini_api_key
            provider = (
                OpenAIEmbeddingProvider(api_key=key, timeout_seconds=self.settings.ai_timeout_seconds)
                if route.provider == "openai"
                else GeminiProvider(api_key=key, timeout_seconds=self.settings.ai_timeout_seconds)
            )
        return self.gateway.embed(
            db,
            user,
            request_id=request_id or str(uuid4()),
            assistant_role="MEMORY_SYSTEM",
            skill_name="memory-curator",
            skill_version="1.0.0",
            request=AIEmbeddingRequest(
                texts=texts,
                task_type=task_type,
                dimensions=self.settings.embedding_dimensions,
                metadata={"embedding_version": EMBEDDING_VERSION},
            ),
            optional=optional,
            route_override=route if provider is not None or provider_override is not None else None,
            provider_override=provider,
        )

    def _override_route(self, provider: str, model: str | None) -> AIModelRoute:
        if provider not in EMBEDDING_MODELS:
            raise AIProviderError("invalid_embedding_settings", "The requested embedding provider is unsupported.")
        selected_model = model or DEFAULT_EMBEDDING_MODEL[provider]
        if selected_model not in EMBEDDING_MODELS[provider]:
            raise AIProviderError("invalid_embedding_settings", "The requested embedding model is unsupported.")
        return AIModelRoute(provider=provider, model=selected_model, capability=AICapability.embedding, temperature=0.0)

    def attach(self, target, response, index: int = 0, *, content: str | None = None) -> None:
        target.embedding_vector = response.vectors[index]
        target.embedding_provider = response.provider
        target.embedding_model = response.model
        target.embedding_dimension = response.dimensions
        target.embedding_version = EMBEDDING_VERSION
        target.embedded_at = datetime.now(UTC)
        if content is not None and hasattr(target, "metadata_json"):
            metadata = dict(target.metadata_json or {})
            metadata["embedding_content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
            target.metadata_json = metadata

    def try_attach(
        self,
        db: Session,
        user: UserProfile,
        target,
        text: str,
        *,
        request_id: str | None = None,
    ) -> bool:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        metadata = target.metadata_json if isinstance(getattr(target, "metadata_json", None), dict) else {}
        route = self.route_for_user(db, user)
        if (
            target.embedding_vector is not None
            and target.embedding_version == EMBEDDING_VERSION
            and target.embedding_provider == route.provider
            and target.embedding_model == route.model
            and target.embedding_dimension == self.settings.embedding_dimensions
            and metadata.get("embedding_content_hash") == content_hash
        ):
            return False
        try:
            response = self.embed(
                db,
                user,
                [text],
                task_type="RETRIEVAL_DOCUMENT",
                request_id=request_id,
            )
        except AIProviderError:
            return False
        self.attach(target, response, content=text)
        return True
