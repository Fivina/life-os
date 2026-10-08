from __future__ import annotations

from time import perf_counter
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.ai.providers import FakeAIProvider, GeminiProvider
from app.ai.routing import AIModelRoute, CapabilityRouter
from app.ai.types import AICapability, AIEmbeddingRequest, AIEmbeddingResponse, AIImageRequest, AIImageResponse, AIProvider, AIProviderError, AIRequest, AIResponse, AIStreamChunk, AIUsageMetadata
from app.ai.usage import AIUsageService
from app.core.config import Settings
from app.database.models import UserProfile


class AIGateway:
    def __init__(self, settings: Settings, providers: dict[str, AIProvider] | None = None):
        self.settings = settings
        self.router = CapabilityRouter(settings)
        self.usage = AIUsageService(settings)
        self.providers = providers or {
            "fake": FakeAIProvider(),
            "gemini": GeminiProvider(api_key=settings.gemini_api_key, timeout_seconds=settings.ai_timeout_seconds),
        }

    def complete(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        assistant_role: str,
        skill_name: str,
        skill_version: str,
        capability: AICapability,
        request: AIRequest,
        conversation_thread_id: str | None = None,
        optional: bool = False,
    ) -> AIResponse:
        if not self.settings.ai_enabled:
            raise AIProviderError("ai_disabled", "AI is disabled.")
        budget = self.usage.budget_state(db, user.id)
        route = self.router.resolve(capability, budget=budget, optional=optional)
        provider = self.providers.get(route.provider)
        if provider is None:
            raise AIProviderError("provider_unavailable", f"AI provider {route.provider} is not configured.")
        request.temperature = request.temperature if request.temperature is not None else route.temperature
        request.timeout_seconds = self.settings.ai_timeout_seconds
        started = perf_counter()
        try:
            response = provider.complete(model=route.model, request=request)
        except AIProviderError as exc:
            self.usage.record(
                db,
                user,
                request_id=request_id,
                assistant_role=assistant_role,
                provider=route.provider,
                model=route.model,
                capability=route.capability,
                skill_name=skill_name,
                skill_version=skill_version,
                prompt_version=self.settings.agent_prompt_version,
                status="error",
                conversation_thread_id=conversation_thread_id,
                latency_ms=round((perf_counter() - started) * 1000),
                error_category=exc.code,
            )
            raise
        self.usage.record(
            db,
            user,
            request_id=request_id,
            assistant_role=assistant_role,
            provider=response.provider,
            model=response.model,
            capability=route.capability,
            skill_name=skill_name,
            skill_version=skill_version,
            prompt_version=self.settings.agent_prompt_version,
            status="completed",
            usage=response.usage,
            conversation_thread_id=conversation_thread_id,
            tool_call_count=len(response.tool_calls),
            latency_ms=round((perf_counter() - started) * 1000),
        )
        return response

    def stream(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        assistant_role: str,
        skill_name: str,
        skill_version: str,
        capability: AICapability,
        request: AIRequest,
        conversation_thread_id: str | None = None,
        optional: bool = False,
    ) -> Iterator[AIStreamChunk]:
        if not self.settings.ai_enabled:
            raise AIProviderError("ai_disabled", "AI is disabled.")
        budget = self.usage.budget_state(db, user.id)
        route = self.router.resolve(capability, budget=budget, optional=optional)
        provider = self.providers.get(route.provider)
        if provider is None:
            raise AIProviderError("provider_unavailable", f"AI provider {route.provider} is not configured.")
        request.temperature = request.temperature if request.temperature is not None else route.temperature
        request.timeout_seconds = self.settings.ai_timeout_seconds
        started = perf_counter()
        usage = AIUsageMetadata()
        try:
            provider_stream = getattr(provider, "stream", None)
            if callable(provider_stream):
                chunks = provider_stream(model=route.model, request=request)
            else:
                response = provider.complete(model=route.model, request=request)
                chunks = iter((
                    AIStreamChunk(text_delta=response.text or "", provider=response.provider, model=response.model),
                    AIStreamChunk(provider=response.provider, model=response.model, done=True, usage=response.usage, finish_status=response.finish_status),
                ))
            for chunk in chunks:
                if chunk.done:
                    usage = chunk.usage
                yield chunk
        except AIProviderError as exc:
            self.usage.record(
                db, user, request_id=request_id, assistant_role=assistant_role, provider=route.provider, model=route.model,
                capability=route.capability, skill_name=skill_name, skill_version=skill_version,
                prompt_version=self.settings.agent_prompt_version, status="error",
                conversation_thread_id=conversation_thread_id,
                latency_ms=round((perf_counter() - started) * 1000), error_category=exc.code,
            )
            raise
        self.usage.record(
            db, user, request_id=request_id, assistant_role=assistant_role, provider=route.provider, model=route.model,
            capability=route.capability, skill_name=skill_name, skill_version=skill_version,
            prompt_version=self.settings.agent_prompt_version, status="completed", usage=usage,
            conversation_thread_id=conversation_thread_id,
            latency_ms=round((perf_counter() - started) * 1000),
        )

    def embed(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        assistant_role: str,
        skill_name: str,
        skill_version: str,
        request: AIEmbeddingRequest,
        conversation_thread_id: str | None = None,
        optional: bool = False,
        route_override: AIModelRoute | None = None,
        provider_override: AIProvider | None = None,
    ) -> AIEmbeddingResponse:
        if not self.settings.ai_enabled:
            raise AIProviderError("ai_disabled", "AI is disabled.")
        budget = self.usage.budget_state(db, user.id)
        if route_override is not None:
            self.router.effective_capability(AICapability.embedding, budget=budget, optional=optional)
            route = route_override
        else:
            route = self.router.resolve(AICapability.embedding, budget=budget, optional=optional)
        provider = provider_override or self.providers.get(route.provider)
        if provider is None:
            raise AIProviderError("provider_unavailable", f"AI provider {route.provider} is not configured.")
        request.timeout_seconds = self.settings.ai_timeout_seconds
        started = perf_counter()
        try:
            response = provider.embed(model=route.model, request=request)
        except AIProviderError as exc:
            self.usage.record(
                db,
                user,
                request_id=request_id,
                assistant_role=assistant_role,
                provider=route.provider,
                model=route.model,
                capability=AICapability.embedding,
                skill_name=skill_name,
                skill_version=skill_version,
                prompt_version=self.settings.agent_prompt_version,
                status="error",
                conversation_thread_id=conversation_thread_id,
                latency_ms=round((perf_counter() - started) * 1000),
                error_category=exc.code,
            )
            raise
        self.usage.record(
            db,
            user,
            request_id=request_id,
            assistant_role=assistant_role,
            provider=response.provider,
            model=response.model,
            capability=AICapability.embedding,
            skill_name=skill_name,
            skill_version=skill_version,
            prompt_version=self.settings.agent_prompt_version,
            status="completed",
            usage=response.usage,
            conversation_thread_id=conversation_thread_id,
            latency_ms=round((perf_counter() - started) * 1000),
        )
        return response

    def generate_image(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        assistant_role: str,
        skill_name: str,
        skill_version: str,
        request: AIImageRequest,
        optional: bool = True,
    ) -> AIImageResponse:
        if not self.settings.ai_enabled:
            raise AIProviderError("ai_disabled", "AI is disabled.")
        budget = self.usage.budget_state(db, user.id)
        route = self.router.resolve(AICapability.image, budget=budget, optional=optional)
        provider = self.providers.get(route.provider)
        if provider is None:
            raise AIProviderError("provider_unavailable", f"AI provider {route.provider} is not configured.")
        started = perf_counter()
        try:
            response = provider.generate_image(model=route.model, request=request)
        except AIProviderError as exc:
            self.usage.record(
                db, user, request_id=request_id, assistant_role=assistant_role, provider=route.provider, model=route.model,
                capability=AICapability.image, skill_name=skill_name, skill_version=skill_version,
                prompt_version=self.settings.agent_prompt_version, status="error",
                latency_ms=round((perf_counter() - started) * 1000), error_category=exc.code,
            )
            raise
        self.usage.record(
            db, user, request_id=request_id, assistant_role=assistant_role, provider=response.provider, model=response.model,
            capability=AICapability.image, skill_name=skill_name, skill_version=skill_version,
            prompt_version=self.settings.agent_prompt_version, status="completed", usage=response.usage,
            latency_ms=round((perf_counter() - started) * 1000),
        )
        return response
