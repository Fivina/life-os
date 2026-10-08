from __future__ import annotations

import inspect

import httpx
import pytest
from sqlalchemy import func, select

from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.database.models import CognitiveTrace, DecisionDisagreement, DecisionProviderUsage, DecisionTrainingExample
from app.decision.benchmark import BENCHMARK_DATASET_VERSION, representative_life_os_cases, run_provider_benchmark
from app.decision.context import DecisionContextBuilder
from app.decision.errors import DecisionProviderError, DecisionProviderTimeout, DecisionProviderUnavailable, UnsupportedDecisionQuestion
from app.decision.evidence import DecisionProviderEvidenceService
from app.decision.gateway import DecisionGateway
from app.decision.provider_schemas import ProviderCapabilities, ProviderHealth, ProviderSupport
from app.decision.providers.base import DecisionProvider
from app.decision.providers.fake import FakeDecisionProvider
from app.decision.providers.jev import JevProvider
from app.decision.providers.laya import LayaLocalProvider
from app.decision.questions import ATTENTION_ACTION_V1, MEMORY_CONTEXT_RELEVANT_V1
from app.decision.routing import DecisionRoutingPolicy
from app.decision.schemas import CognitiveEvent, DecisionContext, DecisionOutputType, DecisionProviderResult, DecisionQuestion
from app.decision.traces import DecisionTraceService


AUTH_HEADERS = {"Authorization": "Bearer dev-local-token"}


def _event(event_id: str = "v16d:event:1") -> CognitiveEvent:
    return CognitiveEvent(event_id=event_id, event_type="memory.candidate", source="test", domains=("memory",))


def _context(
    event: CognitiveEvent | None = None,
    question: DecisionQuestion = MEMORY_CONTEXT_RELEVANT_V1,
    *,
    metadata: dict | None = None,
) -> DecisionContext:
    return DecisionContextBuilder().build(
        event=event or _event(),
        question=question,
        facts={"candidate": "prefers short recipes", "current_domain": "kitchen"},
        metadata=metadata,
    )


class ControlledProvider(FakeDecisionProvider):
    def __init__(
        self,
        name: str,
        answer: str = "relevant",
        confidence: float = 0.82,
        *,
        error: DecisionProviderError | None = None,
        supported: bool = True,
    ):
        self.name = name
        self.provider_version = f"{name}-adapter-v1"
        self.model_version = f"{name}-model-v1"
        self.answer = answer
        self.confidence = confidence
        self.error = error
        self.is_supported = supported
        self.calls = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            enabled=True,
            available=True,
            supported_output_types=(DecisionOutputType.categorical, DecisionOutputType.boolean),
            max_choices=255,
        )

    def supports(self, *, question: DecisionQuestion, context: DecisionContext) -> ProviderSupport:
        del question, context
        return ProviderSupport(supported=self.is_supported, reason_code="SUPPORTED" if self.is_supported else "UNSUPPORTED")

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.name, enabled=True, available=True, loaded=True,
            provider_version=self.provider_version, model_version=self.model_version,
        )

    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        del context
        self.calls += 1
        if self.error:
            raise self.error
        remainder = (1 - self.confidence) / (len(question.allowed_choices) - 1)
        return DecisionProviderResult(
            question_id=question.question_id,
            question_version=question.question_version,
            selected_answer=self.answer,
            probabilities={choice: self.confidence if choice == self.answer else remainder for choice in question.allowed_choices},
            provider=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            confidence=self.confidence,
            metadata={"usage": {"input_tokens": 7, "output_tokens": 1}, "estimated_cost_eur": 0.001},
        )


class MockLayaRuntime:
    def __init__(self):
        self.calls: list[tuple[dict, dict, dict]] = []

    def predict(self, state, questions, **kwargs):  # noqa: ANN001
        self.calls.append((state, questions, kwargs))
        answers = {}
        for question_id, definition in questions.items():
            if definition["type"] == "score":
                answers[question_id] = {
                    "type": "score", "score": 1.6,
                    "probabilities": {"0": 0.1, "1": 0.2, "2": 0.7}, "confidence": 0.62,
                }
            else:
                answers[question_id] = {
                    "type": "choice",
                    "choice": "relevant",
                    "probabilities": {"relevant": 0.8, "irrelevant": 0.2},
                    "confidence": 0.8,
                }
        return {
            "answers": answers,
            "routing": {"model": "english"},
            "usage": {"input_tokens": 12, "output_tokens": 1},
        }


def test_safe_defaults_keep_real_providers_disabled_and_health_secret_free() -> None:
    settings = Settings(_env_file=None, jev_api_key="top-secret")
    gateway = DecisionGateway(settings)
    health = gateway.provider_health()
    assert settings.decision_infra_enabled is False
    assert settings.decision_routing_mode == "AUTO"
    assert next(item for item in health if item["provider_id"] == "laya_local")["enabled"] is False
    assert next(item for item in health if item["provider_id"] == "jev")["available"] is False
    assert "top-secret" not in str(health)


def test_provider_health_endpoint_is_authenticated_and_contains_no_credentials(client) -> None:
    assert client.get("/api/v1/decision/providers").status_code == 401
    response = client.get("/api/v1/decision/providers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert {item["provider_id"] for item in payload["providers"]} == {"fake", "laya_local", "jev"}
    assert "api_key" not in response.text.lower()
    assert "authorization" not in response.text.lower()


def test_laya_is_lazy_and_maps_only_bounded_structured_context() -> None:
    runtime = MockLayaRuntime()
    factory_calls = 0

    def factory(settings):  # noqa: ANN001
        nonlocal factory_calls
        factory_calls += 1
        assert settings.laya_enabled
        return runtime

    provider = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True, laya_model="auto"),
        runtime_factory=factory,
    )
    context = _context(metadata={"private_dump": "must not leave the adapter"})
    assert provider.supports(question=MEMORY_CONTEXT_RELEVANT_V1, context=context).supported
    assert factory_calls == 0
    result = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=context)
    assert result.selected_answer == "relevant"
    assert factory_calls == 1
    state, questions, kwargs = runtime.calls[0]
    assert state["facts"]["candidate"] == "prefers short recipes"
    assert "private_dump" not in str(state)
    assert questions["memory.context_relevant"]["type"] == "choice"
    assert kwargs == {}


def test_laya_batches_typed_questions_in_one_runtime_call_and_maps_score() -> None:
    runtime = MockLayaRuntime()
    provider = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True), runtime_factory=lambda _: runtime
    )
    score_question = DecisionQuestion(
        question_id="benchmark.urgency_score", question_version=1, family="attention",
        output_type=DecisionOutputType.scalar,
        score_rubric=("can wait", "soon", "blocking"),
        description="How urgent is this bounded candidate?",
    )
    event = _event("v16d:batch")
    memory_context = _context(event)
    score_context = _context(event, score_question)
    results = provider.evaluate_batch(
        questions=(MEMORY_CONTEXT_RELEVANT_V1, score_question),
        contexts=(memory_context, score_context),
    )
    assert len(runtime.calls) == 1
    assert results[score_question.question_id].selected_answer == 1.6
    assert results[score_question.question_id].probabilities == {"0": 0.1, "1": 0.2, "2": 0.7}
    results[score_question.question_id].validate_for(score_question)


def test_laya_disabled_load_failure_inference_failure_and_contract_rejection() -> None:
    disabled_calls = 0

    def disabled_factory(_):
        nonlocal disabled_calls
        disabled_calls += 1

    disabled = LayaLocalProvider(Settings(_env_file=None, laya_enabled=False), runtime_factory=disabled_factory)
    assert not disabled.supports(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()).supported
    with pytest.raises(DecisionProviderUnavailable):
        disabled.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    assert disabled_calls == 0

    failing_load = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True),
        runtime_factory=lambda _: (_ for _ in ()).throw(RuntimeError("checkpoint unavailable")),
    )
    with pytest.raises(DecisionProviderUnavailable):
        failing_load.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())

    class BrokenRuntime:
        def predict(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("inference failed")

    inference_failure = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True), runtime_factory=lambda _: BrokenRuntime()
    )
    with pytest.raises(DecisionProviderError):
        inference_failure.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())

    class InvalidRuntime:
        def predict(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return {"answers": {"memory.context_relevant": {"type": "choice", "choice": "unknown"}}}

    invalid = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True), runtime_factory=lambda _: InvalidRuntime()
    )
    with pytest.raises(DecisionProviderError):
        invalid.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())

    structured = DecisionQuestion(
        question_id="benchmark.structured", question_version=1, family="system",
        output_type=DecisionOutputType.structured,
        response_schema={"type": "object", "properties": {}, "additionalProperties": False},
        description="Return a bounded structured fixture.",
    )
    assert not invalid.supports(question=structured, context=_context(_event("v16d:structured"), structured)).supported

    oversized_provider = LayaLocalProvider(
        Settings(_env_file=None, laya_enabled=True, laya_max_context_bytes=1024),
        runtime_factory=lambda _: MockLayaRuntime(),
    )
    oversized_context = DecisionContextBuilder(max_serialized_bytes=16_384).build(
        event=_event("v16d:oversized"), question=MEMORY_CONTEXT_RELEVANT_V1,
        facts={"one": "x" * 800, "two": "y" * 800},
    )
    assert oversized_provider.supports(
        question=MEMORY_CONTEXT_RELEVANT_V1, context=oversized_context
    ).reason_code == "CONTEXT_TOO_LARGE"


def test_missing_laya_dependency_is_provider_unavailable_not_startup_failure(monkeypatch) -> None:
    import app.decision.providers.laya as laya_module

    original_import = laya_module.import_module

    def missing(name: str):
        if name == "laya":
            raise ModuleNotFoundError("laya is optional")
        return original_import(name)

    monkeypatch.setattr(laya_module, "import_module", missing)
    provider = LayaLocalProvider(Settings(_env_file=None, laya_enabled=True))
    assert provider.capabilities().available is False
    with pytest.raises(DecisionProviderUnavailable):
        provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())


def test_jev_verified_wire_contract_retry_and_no_secret_in_result() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"detail": "rate limited"})
        return httpx.Response(
            200,
            headers={"x-request-id": "jev-request-1"},
            json={
                "model": "jev-latest",
                "answers": {
                    "memory.context_relevant": {
                        "type": "choice", "choice": "relevant",
                        "probabilities": {"relevant": 0.76, "irrelevant": 0.24}, "confidence": 0.76,
                    }
                },
                "usage": {"input_tokens": 21, "output_tokens": 1, "cost_eur": 0.002},
                "elapsedMs": 24,
            },
        )

    settings = Settings(
        _env_file=None, jev_enabled=True, jev_api_key="jev-secret", jev_max_retries=1,
        jev_base_url="https://example.invalid",
    )
    provider = JevProvider(settings, transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    result = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    provider.close()
    assert len(calls) == 2
    assert calls[-1].url.path == "/v1/systemone"
    assert calls[-1].headers["authorization"] == "Bearer jev-secret"
    body = calls[-1].read().decode()
    assert '"state"' in body and '"questions"' in body and '"model":"jev-latest"' in body
    assert result.metadata["request_id"] == "jev-request-1"
    assert result.metadata["estimated_cost_eur"] == 0.002
    assert "jev-secret" not in result.model_dump_json()


def test_jev_timeout_permanent_auth_5xx_invalid_json_and_unsupported_contract() -> None:
    base = Settings(
        _env_file=None, jev_enabled=True, jev_api_key="secret", jev_max_retries=1,
        jev_base_url="https://example.invalid",
    )

    timeout = JevProvider(
        base,
        transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=request))),
        sleeper=lambda _: None,
    )
    with pytest.raises(DecisionProviderTimeout):
        timeout.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    timeout.close()

    auth_calls = 0

    def auth_handler(request: httpx.Request) -> httpx.Response:
        nonlocal auth_calls
        auth_calls += 1
        return httpx.Response(401, request=request, json={"detail": "invalid key"})

    auth = JevProvider(base, transport=httpx.MockTransport(auth_handler), sleeper=lambda _: None)
    with pytest.raises(DecisionProviderUnavailable):
        auth.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    auth.close()
    assert auth_calls == 1

    server_calls = 0

    def server_handler(request: httpx.Request) -> httpx.Response:
        nonlocal server_calls
        server_calls += 1
        return httpx.Response(503, request=request, json={"detail": "unavailable"})

    server = JevProvider(base, transport=httpx.MockTransport(server_handler), sleeper=lambda _: None)
    with pytest.raises(DecisionProviderError):
        server.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    server.close()
    assert server_calls == 2

    malformed = JevProvider(
        base,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request, content=b"not-json")),
    )
    with pytest.raises(DecisionProviderError):
        malformed.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    malformed.close()

    structured = DecisionQuestion(
        question_id="benchmark.jev_structured", question_version=1, family="system",
        output_type=DecisionOutputType.structured,
        response_schema={"type": "object", "properties": {}, "additionalProperties": False},
        description="Return a bounded structured fixture.",
    )
    unsupported_context = _context(_event("v16d:jev-structured"), structured)
    assert not malformed.supports(question=structured, context=unsupported_context).supported
    with pytest.raises(UnsupportedDecisionQuestion):
        malformed.evaluate(question=structured, context=unsupported_context)


def test_routing_modes_capability_and_deterministic_shadow_sampling() -> None:
    providers = {
        "fake": FakeDecisionProvider(),
        "laya_local": ControlledProvider("laya_local"),
        "jev": ControlledProvider("jev"),
    }
    auto = DecisionRoutingPolicy(Settings(_env_file=None, decision_routing_mode="AUTO"))
    route = auto.route(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(), providers=providers)
    assert route.primary_provider == "jev"
    assert route.fallback_provider == "laya_local"

    unsupported_laya = {
        "laya_local": ControlledProvider("laya_local", supported=False),
        "jev": ControlledProvider("jev"),
    }
    unsupported_route = auto.route(
        question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(), providers=unsupported_laya
    )
    assert unsupported_route.primary_provider == "jev"

    fake_route = DecisionRoutingPolicy(Settings(_env_file=None, decision_routing_mode="FAKE")).route(
        question=MEMORY_CONTEXT_RELEVANT_V1,
        context=_context(),
        providers={"fake": providers["fake"]},
    )
    assert fake_route.primary_provider == "fake"

    high_cardinality = DecisionQuestion(
        question_id="benchmark.large_choice", question_version=1, family="routing",
        output_type=DecisionOutputType.categorical,
        allowed_choices=tuple(f"choice_{index}" for index in range(17)),
        description="Choose one explicitly supplied routing candidate.",
    )
    high_context = _context(_event("v16d:large"), high_cardinality)
    high_route = auto.route(question=high_cardinality, context=high_context, providers=providers)
    assert high_route.primary_provider == "jev"
    assert high_route.reason_code.value == "HIGH_CARDINALITY"

    shadow_policy = DecisionRoutingPolicy(Settings(
        _env_file=None, decision_routing_mode="SHADOW", decision_shadow_provider="jev",
        decision_shadow_sample_rate=0.5,
    ))
    first = shadow_policy.should_sample_shadow(event_id="stable-event", question=MEMORY_CONTEXT_RELEVANT_V1)
    assert first == shadow_policy.should_sample_shadow(event_id="stable-event", question=MEMORY_CONTEXT_RELEVANT_V1)
    filtered = DecisionRoutingPolicy(Settings(
        _env_file=None, decision_routing_mode="SHADOW", decision_shadow_sample_rate=1,
        decision_shadow_families="attention",
    ))
    assert not filtered.should_sample_shadow(event_id="stable-event", question=MEMORY_CONTEXT_RELEVANT_V1)


def test_low_confidence_fallback_persists_usage_and_disagreement(db_session) -> None:
    user = get_or_create_user(db_session)
    laya = ControlledProvider("laya_local", answer="relevant", confidence=0.88)
    jev = ControlledProvider("jev", answer="irrelevant", confidence=0.55)
    gateway = DecisionGateway(
        Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="AUTO"),
        providers={"laya_local": laya, "jev": jev},
    )
    execution = gateway.evaluate(
        db_session, user, event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()
    )
    assert execution.result.provider == "laya_local"
    assert execution.result.selected_answer == "relevant"
    usage = list(db_session.scalars(select(DecisionProviderUsage).order_by(DecisionProviderUsage.created_at)))
    assert [(row.provider, row.provider_role, row.status) for row in usage] == [
        ("jev", "PRIMARY", "COMPLETED"), ("laya_local", "FALLBACK", "COMPLETED")
    ]
    disagreement = db_session.scalar(select(DecisionDisagreement))
    assert disagreement is not None
    assert disagreement.disagreement_type == "PRIMARY_UNCERTAIN_SECONDARY_CONFIDENT"
    assert disagreement.operational_provider == "laya_local"
    assert disagreement.training_eligible is False
    assert disagreement.cognitive_trace_id == execution.trace_id
    assert disagreement.question_id == MEMORY_CONTEXT_RELEVANT_V1.question_id
    assert disagreement.question_version == MEMORY_CONTEXT_RELEVANT_V1.question_version
    assert disagreement.primary_model_version == jev.model_version
    assert disagreement.comparison_model_version == laya.model_version
    assert disagreement.routing_policy_version == "decision-routing-v1"
    assert len(disagreement.context_hash) == 64
    assert db_session.scalar(select(func.count(DecisionTrainingExample.id))) == 0
    trace = db_session.get(CognitiveTrace, execution.trace_id)
    audit = DecisionTraceService().add_audit(
        db_session, user, trace=trace, audit_type="explicit_outcome", outcome={"worked": True}
    )
    linked = DecisionProviderEvidenceService().link_audit(
        db_session, user, disagreement_id=disagreement.id, audit=audit
    )
    assert linked.decision_audit_id == audit.id
    assert linked.review_status == "EVIDENCE_LINKED"


def test_primary_error_falls_back_and_double_failure_is_safe(db_session) -> None:
    user = get_or_create_user(db_session)
    failing_laya = ControlledProvider("laya_local", error=DecisionProviderError("local failed", retryable=True))
    failing_jev = ControlledProvider("jev", error=DecisionProviderError("hosted failed", retryable=True))
    laya = ControlledProvider("laya_local", answer="relevant", confidence=0.9)
    settings = Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="AUTO")
    execution = DecisionGateway(settings, providers={"laya_local": laya, "jev": failing_jev}).evaluate(
        db_session, user, event=_event("v16d:fallback"), question=MEMORY_CONTEXT_RELEVANT_V1,
        context=_context(_event("v16d:fallback")),
    )
    assert execution.result.provider == "laya_local"

    with pytest.raises(DecisionProviderError):
        DecisionGateway(settings, providers={"laya_local": failing_laya, "jev": failing_jev}).evaluate(
            db_session, user, event=_event("v16d:all-fail"), question=MEMORY_CONTEXT_RELEVANT_V1,
            context=_context(_event("v16d:all-fail")),
        )
    assert db_session.scalar(select(func.count(DecisionProviderUsage.id))) >= 4


def test_builtin_jev_uses_only_the_authenticated_users_vault_key(db_session, monkeypatch) -> None:
    from app.decision.gateway import DecisionGateway
    from app.intelligence_settings.provider_credentials import ProviderSecretStore

    user = get_or_create_user(db_session)
    settings = Settings(_env_file=None, jev_enabled=True, jev_api_key="process-env-secret")
    gateway = DecisionGateway(settings)
    monkeypatch.setattr(ProviderSecretStore, "configured", lambda self, db, current_user, provider: provider == "jev")
    monkeypatch.setattr(ProviderSecretStore, "get", lambda self, db, current_user, provider: f"vault-secret-{current_user.id}")

    request_providers = gateway._providers_for_user(db_session, user)
    assert request_providers["jev"].settings.jev_api_key == f"vault-secret-{user.id}"
    other_user = get_or_create_user(db_session, email="other@example.test", auth_subject="other-user")
    other_providers = gateway._providers_for_user(db_session, other_user)
    assert other_providers["jev"].settings.jev_api_key == f"vault-secret-{other_user.id}"
    assert request_providers["jev"].settings.jev_api_key != other_providers["jev"].settings.jev_api_key
    assert gateway.providers["jev"].settings.jev_api_key is None
    assert "process-env-secret" not in str(gateway.provider_health())


def test_shadow_never_overrides_operational_result_and_timeout_is_recorded(db_session) -> None:
    user = get_or_create_user(db_session)
    laya = ControlledProvider("laya_local", error=DecisionProviderError("local shadow failed", retryable=True))
    jev = ControlledProvider("jev", answer="relevant", confidence=0.9)
    settings = Settings(
        _env_file=None,
        decision_infra_enabled=True,
        decision_routing_mode="SHADOW",
        decision_shadow_provider="laya_local",
        decision_shadow_sample_rate=1.0,
        decision_shadow_daily_budget_eur=1.0,
    )
    execution = DecisionGateway(settings, providers={"laya_local": laya, "jev": jev}).evaluate(
        db_session, user, event=_event("v16d:shadow"), question=MEMORY_CONTEXT_RELEVANT_V1,
        context=_context(_event("v16d:shadow")),
    )
    assert execution.result.provider == "jev"
    assert execution.result.selected_answer == "relevant"
    shadow_usage = db_session.scalar(select(DecisionProviderUsage).where(DecisionProviderUsage.provider_role == "SHADOW"))
    assert shadow_usage is not None and shadow_usage.status == "FAILED"
    disagreement = db_session.scalar(select(DecisionDisagreement).where(DecisionDisagreement.comparison_role == "SHADOW"))
    assert disagreement is not None
    assert disagreement.metadata_json["shadow_had_no_operational_authority"] is True


def test_shadow_disagreement_never_overrides_primary_attention_action(db_session) -> None:
    user = get_or_create_user(db_session)
    laya = ControlledProvider("laya_local", answer="ASK", confidence=0.9)
    jev = ControlledProvider("jev", answer="SILENT", confidence=0.9)
    settings = Settings(
        _env_file=None, decision_infra_enabled=True, decision_routing_mode="SHADOW",
        decision_shadow_provider="laya_local", decision_shadow_sample_rate=1,
        decision_shadow_daily_budget_eur=1,
    )
    event = _event("v16d:attention-shadow")
    execution = DecisionGateway(settings, providers={"laya_local": laya, "jev": jev}).evaluate(
        db_session, user, event=event, question=ATTENTION_ACTION_V1,
        context=_context(event, ATTENTION_ACTION_V1),
    )
    assert execution.result.selected_answer == "SILENT"
    disagreement = db_session.scalar(select(DecisionDisagreement).where(
        DecisionDisagreement.cognitive_event_id == event.event_id
    ))
    assert disagreement.primary_answer_json == {"value": "SILENT"}
    assert disagreement.comparison_answer_json == {"value": "ASK"}
    assert disagreement.operational_answer_json == {"value": "SILENT"}
    assert disagreement.training_eligible is False


def test_jev_budget_exhaustion_skips_external_call_without_breaking_core_state(db_session) -> None:
    user = get_or_create_user(db_session)
    jev = ControlledProvider("jev", answer="relevant", confidence=0.9)
    settings = Settings(
        _env_file=None,
        decision_infra_enabled=True,
        decision_routing_mode="JEV_ONLY",
        jev_daily_budget_eur=0,
    )
    with pytest.raises(DecisionProviderUnavailable, match="budget"):
        DecisionGateway(settings, providers={"jev": jev}).evaluate(
            db_session, user, event=_event("v16d:budget"), question=MEMORY_CONTEXT_RELEVANT_V1,
            context=_context(_event("v16d:budget")),
        )
    assert jev.calls == 0
    usage = db_session.scalar(select(DecisionProviderUsage).where(DecisionProviderUsage.provider == "jev"))
    assert usage is not None and usage.status == "SKIPPED"


def test_benchmark_is_versioned_family_specific_and_never_activates_profile() -> None:
    cases = representative_life_os_cases()
    assert len(cases) == 21
    assert {case.task_family for case in cases} == {
        "attention", "curiosity", "context_relevance", "prospective", "memory", "contributor_activation",
        "urgency_score",
    }
    report = run_provider_benchmark((FakeDecisionProvider(),), cases)
    assert report.dataset_version == BENCHMARK_DATASET_VERSION
    assert all(metric.n == 3 for metric in report.task_family_metrics)
    assert all(
        metric.exact_match_rate == 1.0
        for metric in report.task_family_metrics
        if metric.task_family != "urgency_score"
    )
    score_metrics = next(metric for metric in report.task_family_metrics if metric.task_family == "urgency_score")
    assert score_metrics.mean_absolute_error is not None
    assert score_metrics.within_half_level_rate is not None
    assert report.routing_recommendation.status == "candidate"
    assert report.routing_recommendation.task_family_routes == {}
    assert all(
        family["fake_is_test_only"]
        for family in report.routing_recommendation.evidence_summary.values()
    )
    assert "composite_score" not in report.model_dump_json().lower()


def test_provider_contract_has_no_database_or_domain_mutation_handle() -> None:
    parameters = set(inspect.signature(DecisionProvider.evaluate).parameters)
    assert parameters == {"self", "question", "context"}
    assert "db" not in parameters and "session" not in parameters and "service" not in parameters


@pytest.mark.laya_integration
def test_real_laya_optional_smoke() -> None:
    settings = Settings()
    if not settings.decision_live_provider_tests or not settings.laya_enabled:
        pytest.skip("Set DECISION_LIVE_PROVIDER_TESTS=true and LAYA_ENABLED=true for real local inference.")
    provider = LayaLocalProvider(settings)
    if not provider.capabilities().available:
        pytest.skip("Laya dependency is not installed.")
    result = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    result.validate_for(MEMORY_CONTEXT_RELEVANT_V1)


@pytest.mark.jev_live
def test_real_jev_optional_smoke() -> None:
    settings = Settings()
    if not settings.decision_live_provider_tests or not settings.jev_enabled or not settings.jev_api_key:
        pytest.skip("Enable DECISION_LIVE_PROVIDER_TESTS and JEV_ENABLED with JEV_API_KEY for live Jev.")
    provider = JevProvider(settings)
    try:
        result = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
        result.validate_for(MEMORY_CONTEXT_RELEVANT_V1)
    finally:
        provider.close()
