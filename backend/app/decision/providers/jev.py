from __future__ import annotations

from datetime import UTC, datetime
import time
from time import perf_counter
from typing import Callable

import httpx

from app.core.config import Settings
from app.decision.errors import DecisionProviderError, DecisionProviderTimeout, DecisionProviderUnavailable, UnsupportedDecisionQuestion
from app.decision.provider_schemas import ProviderCapabilities, ProviderHealth, ProviderSupport
from app.decision.providers.mapping import bounded_state, normalize_answer, typed_question
from app.decision.schemas import DecisionContext, DecisionOutputType, DecisionProviderResult, DecisionQuestion


class JevProvider:
    """Pooled direct HTTP adapter for Jev's documented POST /v1/systemone contract."""

    name = "jev"
    provider_version = "jev-http-adapter-v1"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.model_version = settings.jev_model
        self._transport = transport
        self._sleeper = sleeper
        self._client: httpx.Client | None = None
        self._last_error: str | None = None
        self._last_success_at: datetime | None = None

    def capabilities(self) -> ProviderCapabilities:
        enabled = self.settings.jev_enabled
        return ProviderCapabilities(
            provider_id=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            enabled=enabled,
            available=enabled and bool(self.settings.jev_api_key),
            supported_output_types=(DecisionOutputType.categorical, DecisionOutputType.boolean, DecisionOutputType.scalar),
            max_choices=255,
            max_questions_per_request=8,
            max_context_bytes=32_768,
            supported_languages=("en",),
            external=True,
            metadata={"base_url": self.settings.jev_base_url, "endpoint": "/v1/systemone"},
        )

    def supports(self, *, question: DecisionQuestion, context: DecisionContext) -> ProviderSupport:
        capabilities = self.capabilities()
        if not capabilities.enabled:
            return ProviderSupport(supported=False, reason_code="PROVIDER_DISABLED")
        if not capabilities.available:
            return ProviderSupport(supported=False, reason_code="CREDENTIALS_UNAVAILABLE")
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
            loaded=self._client is not None,
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
        capabilities = self.capabilities()
        if not questions or len(questions) != len(contexts) or len(questions) > capabilities.max_questions_per_request:
            raise UnsupportedDecisionQuestion("Jev batch size is invalid or exceeds its declared limit.")
        if len({question.question_id for question in questions}) != len(questions):
            raise UnsupportedDecisionQuestion("Jev batch question IDs must be unique.")
        for question, context in zip(questions, contexts, strict=True):
            support = self.supports(question=question, context=context)
            if not support.supported:
                if support.reason_code in {"PROVIDER_DISABLED", "CREDENTIALS_UNAVAILABLE"}:
                    raise DecisionProviderUnavailable(f"Jev is unavailable: {support.reason_code}.")
                raise UnsupportedDecisionQuestion(f"Jev does not support this question: {support.reason_code}.")
        states = [bounded_state(context, max_bytes=capabilities.max_context_bytes) for context in contexts]
        if any(state != states[0] for state in states[1:]):
            raise UnsupportedDecisionQuestion("Jev batching requires every question to share the same bounded state.")
        body = {
            "state": states[0],
            "model": self.settings.jev_model,
            "questions": {question.question_id: typed_question(question) for question in questions},
        }
        endpoint = f"{self.settings.jev_base_url.rstrip('/')}/v1/systemone"
        started = perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.settings.jev_max_retries + 1):
            try:
                response = self._get_client().post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.settings.jev_api_key}", "Content-Type": "application/json"},
                    json=body,
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.settings.jev_max_retries:
                    self._sleeper(min(0.25 * (2 ** attempt), 1.0))
                    continue
                if response.status_code in {401, 403}:
                    raise DecisionProviderUnavailable("Jev authentication failed.")
                if response.status_code >= 400:
                    raise DecisionProviderError(f"Jev rejected the request with HTTP {response.status_code}.", retryable=False)
                payload = response.json()
                result_payload = payload.get("result") if isinstance(payload, dict) and isinstance(payload.get("result"), dict) else payload
                usage = result_payload.get("usage") or {}
                request_id = (
                    response.headers.get("x-request-id")
                    or result_payload.get("request_id")
                    or payload.get("request_id")
                )
                latency_ms = max(0, round((perf_counter() - started) * 1000))
                results: dict[str, DecisionProviderResult] = {}
                for question in questions:
                    answer = result_payload["answers"][question.question_id]
                    selected, probabilities, confidence = normalize_answer(answer, question)
                    provider_result = DecisionProviderResult(
                        question_id=question.question_id,
                        question_version=question.question_version,
                        selected_answer=selected,
                        probabilities=probabilities,
                        provider=self.name,
                        provider_version=self.provider_version,
                        model_version=str(result_payload.get("model") or self.settings.jev_model),
                        confidence=confidence,
                        metadata={
                            "raw_confidence": answer.get("confidence"),
                            "request_id": request_id,
                            "usage": usage,
                            "batch_question_count": len(questions),
                            "reported_elapsed_ms": result_payload.get("elapsedMs") or result_payload.get("elapsed"),
                            "estimated_cost_eur": usage.get("cost_eur"),
                            "cost_usd": usage.get("cost_usd") or usage.get("cost"),
                            "network_latency_ms": latency_ms,
                        },
                    )
                    provider_result.validate_for(question)
                    results[question.question_id] = provider_result
                self._last_error = None
                self._last_success_at = datetime.now(UTC)
                return results
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.settings.jev_max_retries:
                    self._sleeper(min(0.25 * (2 ** attempt), 1.0))
                    continue
                self._last_error = "timeout"
                raise DecisionProviderTimeout("Jev request timed out.", retryable=True) from exc
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self.settings.jev_max_retries:
                    self._sleeper(min(0.25 * (2 ** attempt), 1.0))
                    continue
                self._last_error = type(exc).__name__
                raise DecisionProviderError("Jev transport failed.", retryable=True) from exc
            except (DecisionProviderError, DecisionProviderUnavailable, UnsupportedDecisionQuestion):
                raise
            except Exception as exc:
                self._last_error = type(exc).__name__
                raise DecisionProviderError("Jev returned an invalid response.", retryable=False) from exc
        raise DecisionProviderError("Jev request failed.", retryable=True) from last_error

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.jev_timeout_seconds, transport=self._transport)
        return self._client
