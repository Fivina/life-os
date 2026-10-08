from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module, metadata as importlib_metadata
import os
from time import perf_counter
from typing import Any, Callable

from app.core.config import Settings
from app.decision.errors import DecisionProviderError, DecisionProviderUnavailable, UnsupportedDecisionQuestion
from app.decision.provider_schemas import ProviderCapabilities, ProviderHealth, ProviderSupport
from app.decision.providers.mapping import bounded_state, normalize_answer, typed_question
from app.decision.schemas import DecisionContext, DecisionOutputType, DecisionProviderResult, DecisionQuestion


RuntimeFactory = Callable[[Settings], Any]


class LayaLocalProvider:
    """Lazy adapter for the upstream laya Router.predict typed-decision contract."""

    name = "laya_local"
    provider_version = "laya-adapter-v1"

    def __init__(self, settings: Settings, *, runtime_factory: RuntimeFactory | None = None):
        self.settings = settings
        self.model_version = settings.laya_model
        self._runtime_factory_injected = runtime_factory is not None
        self._runtime_factory = runtime_factory or self._load_upstream_runtime
        self._runtime: Any | None = None
        self._package_version: str | None = None
        self._loaded_at: datetime | None = None
        self._load_latency_ms: int | None = None
        self._last_error: str | None = None
        self._last_success_at: datetime | None = None

    def capabilities(self) -> ProviderCapabilities:
        available = self._dependency_available() if self.settings.laya_enabled else False
        return ProviderCapabilities(
            provider_id=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            enabled=self.settings.laya_enabled,
            available=available,
            supported_output_types=(DecisionOutputType.categorical, DecisionOutputType.boolean, DecisionOutputType.scalar),
            max_choices=self.settings.laya_max_choices,
            max_questions_per_request=8,
            max_context_bytes=self.settings.laya_max_context_bytes,
            supported_languages=("en", "multilingual"),
            external=False,
            metadata={
                "device": self.settings.laya_device,
                "cache_path": self.settings.laya_cache_path,
                "package_version": self._package_version,
                "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
                "load_latency_ms": self._load_latency_ms,
            },
        )

    def supports(self, *, question: DecisionQuestion, context: DecisionContext) -> ProviderSupport:
        capabilities = self.capabilities()
        if not capabilities.enabled:
            return ProviderSupport(supported=False, reason_code="PROVIDER_DISABLED")
        if not capabilities.available:
            return ProviderSupport(supported=False, reason_code="DEPENDENCY_UNAVAILABLE")
        if question.output_type not in capabilities.supported_output_types:
            return ProviderSupport(supported=False, reason_code="UNSUPPORTED_PRIMITIVE")
        if question.output_type == DecisionOutputType.categorical and len(question.allowed_choices) > capabilities.max_choices:
            return ProviderSupport(supported=False, reason_code="HIGH_CARDINALITY")
        try:
            bounded_state(context, max_bytes=capabilities.max_context_bytes)
        except UnsupportedDecisionQuestion:
            return ProviderSupport(supported=False, reason_code="CONTEXT_TOO_LARGE")
        return ProviderSupport(supported=True, reason_code="SUPPORTED")

    def health(self) -> ProviderHealth:
        capabilities = self.capabilities()
        return ProviderHealth(
            provider_id=self.name,
            enabled=capabilities.enabled,
            available=capabilities.available,
            loaded=self._runtime is not None,
            provider_version=self.provider_version,
            model_version=self.model_version,
            last_error=self._last_error,
            last_success_at=self._last_success_at,
            runtime_metadata=capabilities.metadata,
        )

    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        return self.evaluate_batch(questions=(question,), contexts=(context,))[question.question_id]

    def evaluate_batch(
        self,
        *,
        questions: tuple[DecisionQuestion, ...],
        contexts: tuple[DecisionContext, ...],
    ) -> dict[str, DecisionProviderResult]:
        if not questions or len(questions) != len(contexts) or len(questions) > self.capabilities().max_questions_per_request:
            raise UnsupportedDecisionQuestion("Laya batch size is invalid or exceeds its declared limit.")
        if len({question.question_id for question in questions}) != len(questions):
            raise UnsupportedDecisionQuestion("Laya batch question IDs must be unique.")
        for question, context in zip(questions, contexts, strict=True):
            support = self.supports(question=question, context=context)
            if not support.supported:
                if support.reason_code in {"PROVIDER_DISABLED", "DEPENDENCY_UNAVAILABLE"}:
                    raise DecisionProviderUnavailable(f"Laya is unavailable: {support.reason_code}.")
                raise UnsupportedDecisionQuestion(f"Laya does not support this question: {support.reason_code}.")
        runtime = self._ensure_runtime()
        states = [bounded_state(context, max_bytes=self.settings.laya_max_context_bytes) for context in contexts]
        if any(state != states[0] for state in states[1:]):
            raise UnsupportedDecisionQuestion("Laya batching requires every question to share the same bounded state.")
        state = states[0]
        upstream_questions = {question.question_id: typed_question(question) for question in questions}
        started = perf_counter()
        try:
            model_override = None if self.settings.laya_model == "auto" else self.settings.laya_model
            payload = runtime.predict(state, upstream_questions, **({"model": model_override} if model_override else {}))
        except (DecisionProviderUnavailable, UnsupportedDecisionQuestion):
            raise
        except Exception as exc:
            self._last_error = type(exc).__name__
            raise DecisionProviderError("Laya inference failed.", retryable=True) from exc
        self._last_error = None
        self._last_success_at = datetime.now(UTC)
        routing = payload.get("routing") or {}
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        results: dict[str, DecisionProviderResult] = {}
        try:
            for question in questions:
                answer = payload["answers"][question.question_id]
                selected, probabilities, confidence = normalize_answer(answer, question)
                provider_result = DecisionProviderResult(
                    question_id=question.question_id,
                    question_version=question.question_version,
                    selected_answer=selected,
                    probabilities=probabilities,
                    provider=self.name,
                    provider_version=self.provider_version,
                    model_version=str(routing.get("repo") or routing.get("model") or self.model_version),
                    confidence=confidence,
                    metadata={
                        "raw_confidence": answer.get("confidence"),
                        "runtime_latency_ms": latency_ms,
                        "batch_question_count": len(questions),
                        "routing": routing,
                        "usage": payload.get("usage") or {},
                        "package_version": self._package_version,
                        "device": self.settings.laya_device,
                        "load_latency_ms": self._load_latency_ms,
                    },
                )
                provider_result.validate_for(question)
                results[question.question_id] = provider_result
        except Exception as exc:
            self._last_error = type(exc).__name__
            raise DecisionProviderError("Laya returned an invalid response.", retryable=False) from exc
        return results

    def _ensure_runtime(self) -> Any:
        if self._runtime is not None:
            return self._runtime
        started = perf_counter()
        try:
            self._runtime = self._runtime_factory(self.settings)
            self._package_version = self._read_package_version()
            self._loaded_at = datetime.now(UTC)
            self._load_latency_ms = max(0, round((perf_counter() - started) * 1000))
            return self._runtime
        except Exception as exc:
            self._last_error = type(exc).__name__
            raise DecisionProviderUnavailable("Laya runtime or checkpoint could not be loaded.") from exc

    @staticmethod
    def _load_upstream_runtime(settings: Settings) -> Any:
        if settings.laya_cache_path:
            os.environ.setdefault("HF_HOME", settings.laya_cache_path)
        laya = import_module("laya")
        kwargs: dict[str, Any] = {"preload": False}
        if settings.laya_device != "auto":
            kwargs["device"] = settings.laya_device
        return laya.Router(**kwargs)

    @staticmethod
    def _read_package_version() -> str | None:
        try:
            return importlib_metadata.version("laya")
        except importlib_metadata.PackageNotFoundError:
            return None

    def _dependency_available(self) -> bool:
        if self._runtime is not None or self._runtime_factory_injected:
            return True
        try:
            import_module("laya")
            return True
        except (ImportError, ModuleNotFoundError):
            return False
