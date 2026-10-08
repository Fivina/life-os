from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.embedding_models import DEFAULT_EMBEDDING_MODEL, EMBEDDING_MODELS
from app.ai.providers import GeminiProvider, OpenAIEmbeddingProvider
from app.ai.routing import AIModelRoute
from app.ai.types import AICapability, AIEmbeddingRequest, AIProviderError
from app.core.config import Settings
from app.database.models import UserIntelligenceSettings, UserProfile
from app.events.service import append_event
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.service import IntelligenceSettingsService
from app.intelligence_settings.schemas import (
    EmbeddingConnectionTestRead,
    EmbeddingConnectionTestRequest,
    EmbeddingSettingsRead,
    EmbeddingSettingsUpdate,
)
from app.memory.embeddings import EmbeddingService


CONNECTION_TEST_TEXT = "Life OS embedding provider connection test."


def validate_embedding_model(provider: str, model: str | None) -> str:
    if provider not in EMBEDDING_MODELS:
        raise HTTPException(status_code=422, detail="Unsupported embedding provider.")
    selected = model or DEFAULT_EMBEDDING_MODEL[provider]
    if selected not in EMBEDDING_MODELS[provider]:
        raise HTTPException(status_code=422, detail="Unsupported embedding model for this provider.")
    return selected


class EmbeddingSettingsService:
    def __init__(self, settings: Settings, secret_store: ProviderSecretStore | None = None):
        self.settings = settings
        self.secret_store = secret_store or ProviderSecretStore()

    def read(self, db: Session, user: UserProfile) -> EmbeddingSettingsRead:
        row = self._row(db, user)
        saved = (row.metadata_json or {}).get("embedding_settings") or {}
        provider = saved.get("provider", "default")
        if provider == "default":
            effective_provider = self.settings.ai_provider.lower()
            model = self.settings.ai_model_embedding
            configured = self._default_configured(effective_provider)
        else:
            effective_provider = provider
            model = saved.get("model") or validate_embedding_model(provider, None)
            configured = self.secret_store.configured(db, user, provider)
        return EmbeddingSettingsRead(
            provider=provider,
            model=model,
            effective_provider=effective_provider,
            dimensions=self.settings.embedding_dimensions,
            credential_configured=configured,
            version=row.version,
        )

    def update(self, db: Session, user: UserProfile, payload: EmbeddingSettingsUpdate) -> EmbeddingSettingsRead:
        row = self._row(db, user)
        if payload.expected_version is not None and payload.expected_version != row.version:
            raise HTTPException(status_code=409, detail="Intelligence settings changed after they were loaded.")
        if payload.provider == "default":
            preference = {"provider": "default"}
        else:
            model = validate_embedding_model(payload.provider, payload.model)
            if not self.secret_store.configured(db, user, payload.provider):
                raise HTTPException(status_code=409, detail=f"Save a {payload.provider.title()} API key in Providers before selecting its embedding model.")
            preference = {"provider": payload.provider, "model": model}
        metadata = dict(row.metadata_json or {})
        metadata["embedding_settings"] = preference
        row.metadata_json = metadata
        row.version += 1
        db.flush()
        append_event(
            db,
            user,
            event_type="intelligence_settings.embedding_route_updated",
            aggregate_type="user_intelligence_settings",
            aggregate_id=row.id,
            payload={"settings_id": row.id, **preference, "dimensions": self.settings.embedding_dimensions},
            outbox=True,
        )
        return self.read(db, user)

    def test(self, db: Session, user: UserProfile, payload: EmbeddingConnectionTestRequest) -> EmbeddingConnectionTestRead:
        model = validate_embedding_model(payload.provider, payload.model)
        embedding_service = EmbeddingService(self.settings, AIGateway(self.settings), self.secret_store)
        try:
            response = embedding_service.embed(
                db,
                user,
                [CONNECTION_TEST_TEXT],
                task_type="RETRIEVAL_QUERY",
                optional=True,
                provider_override=payload.provider,
                model_override=model,
            )
        except AIProviderError as exc:
            status_code = 429 if exc.code == "rate_limited" else 502
            raise HTTPException(status_code=status_code, detail=exc.message) from None
        if not response.vectors or not response.vectors[0]:
            raise HTTPException(status_code=502, detail="The embedding provider returned no vector.")
        return EmbeddingConnectionTestRead(
            provider=payload.provider,
            model=response.model,
            dimensions=response.dimensions,
            connected=bool(response.vectors and response.vectors[0]),
        )

    def _row(self, db: Session, user: UserProfile) -> UserIntelligenceSettings:
        return IntelligenceSettingsService(self.settings).get_model(db, user)

    def _default_configured(self, provider: str) -> bool:
        if provider == "fake":
            return True
        if provider == "gemini":
            return bool(self.settings.gemini_api_key)
        if provider == "openai":
            return bool(self.settings.openai_api_key)
        return False
