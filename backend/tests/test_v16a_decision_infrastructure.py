from __future__ import annotations

import ast
from datetime import UTC, datetime
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.ai.gateway import AIGateway
from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.database.models import Action, CognitiveTrace, DecisionAudit, Event, PlanBlock
from app.decision.benchmark import DecisionBenchmarkHarness, representative_fake_cases
from app.decision.context import DecisionContextBuilder
from app.decision.contributors import StaticDecisionContributor
from app.decision.errors import (
    DecisionInfrastructureDisabled,
    DecisionProviderError,
    DecisionProviderTimeout,
    DecisionProviderUnavailable,
    DecisionValidationError,
    UnsupportedDecisionQuestion,
)
from app.decision.events import cognitive_event_from_domain_event
from app.decision.gateway import DecisionGateway
from app.decision.providers.base import DecisionProvider
from app.decision.providers.fake import FakeDecisionProvider
from app.decision.questions import (
    DecisionQuestionRegistry,
    MEMORY_CONTEXT_RELEVANT_V1,
    SYSTEM_TEST_BOOLEAN_V1,
)
from app.decision.schemas import (
    CognitiveEvent,
    DecisionContext,
    DecisionOutputType,
    DecisionProviderResult,
    DecisionQuestion,
    EntityReference,
    ProvenanceReference,
)
from app.decision.traces import DecisionTraceService


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _event() -> CognitiveEvent:
    return CognitiveEvent(
        event_id="test:event:1",
        event_type="test.decision_requested",
        source="test",
        domains=("memory",),
        entity_refs=(EntityReference(entity_type="memory_candidate", entity_id="candidate-1"),),
        world_revision=7,
        correlation_id="correlation-1",
    )


def _context(*, scenario: str = "normal") -> DecisionContext:
    return DecisionContextBuilder().build(
        event=_event(),
        question=MEMORY_CONTEXT_RELEVANT_V1,
        facts={"candidate_kind": "preference", "current_domain": "kitchen"},
        provenance={
            "candidate_kind": (ProvenanceReference(source_type="memory_candidate", source_id="candidate-1"),),
            "current_domain": (ProvenanceReference(source_type="cognitive_event", source_id="test:event:1"),),
        },
        memory_refs=("memory-1",),
        pattern_refs=("pattern-1",),
        metadata={"fake_scenario": scenario},
    )


def test_decision_question_is_versioned_validated_immutable_and_deterministic() -> None:
    first = MEMORY_CONTEXT_RELEVANT_V1.canonical_json()
    second = MEMORY_CONTEXT_RELEVANT_V1.canonical_json()
    assert first == second
    assert '"question_version":1' in first

    with pytest.raises(ValidationError):
        DecisionQuestion(
            question_id="memory.bad",
            family="memory",
            output_type=DecisionOutputType.categorical,
            allowed_choices=("yes", "no"),
            description="Missing version.",
        )
    with pytest.raises(ValidationError, match="at least two"):
        DecisionQuestion(
            question_id="memory.bad",
            question_version=1,
            family="memory",
            output_type=DecisionOutputType.categorical,
            allowed_choices=("yes",),
            description="Invalid choice set.",
        )
    with pytest.raises(ValidationError):
        MEMORY_CONTEXT_RELEVANT_V1.question_version = 2


def test_question_registry_rejects_semantic_change_without_version_bump() -> None:
    registry = DecisionQuestionRegistry((MEMORY_CONTEXT_RELEVANT_V1,))
    changed = MEMORY_CONTEXT_RELEVANT_V1.model_copy(update={"description": "Changed semantics."})
    with pytest.raises(ValueError, match="without a version change"):
        registry.register(changed)


def test_probability_and_answer_validation_are_not_authority_defaults() -> None:
    with pytest.raises(ValidationError, match="sum to 1"):
        DecisionProviderResult(
            question_id="memory.context_relevant",
            question_version=1,
            selected_answer="relevant",
            probabilities={"relevant": 0.9, "irrelevant": 0.9},
            provider="test",
            provider_version="1",
        )
    wrong_choice = DecisionProviderResult(
        question_id="memory.context_relevant",
        question_version=1,
        selected_answer="unknown",
        provider="test",
        provider_version="1",
    )
    with pytest.raises(ValueError, match="allowed categorical"):
        wrong_choice.validate_for(MEMORY_CONTEXT_RELEVANT_V1)


def test_fake_provider_is_deterministic_and_supports_simulations() -> None:
    provider = FakeDecisionProvider()
    normal_one = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    normal_two = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context())
    assert normal_one == normal_two
    normal_one.validate_for(MEMORY_CONTEXT_RELEVANT_V1)

    low = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(scenario="low_confidence"))
    assert low.confidence == 0.51
    assert max(low.probabilities.values()) == pytest.approx(0.5)

    invalid = provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(scenario="invalid_response"))
    with pytest.raises(ValidationError):
        DecisionProviderResult.model_validate(invalid.model_dump(mode="python"))
    with pytest.raises(UnsupportedDecisionQuestion):
        provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(scenario="unsupported"))
    with pytest.raises(DecisionProviderTimeout):
        provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(scenario="timeout"))
    with pytest.raises(DecisionProviderError):
        provider.evaluate(question=MEMORY_CONTEXT_RELEVANT_V1, context=_context(scenario="error"))


class _CountingProvider(FakeDecisionProvider):
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        self.calls += 1
        return super().evaluate(question=question, context=context)


class _TimeoutProvider(FakeDecisionProvider):
    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        raise TimeoutError("fixture")


class _FailingTraceService(DecisionTraceService):
    def record_completed(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("trace store unavailable")


def test_gateway_disabled_does_not_call_provider_or_write_trace(db_session) -> None:
    user = get_or_create_user(db_session)
    provider = _CountingProvider()
    gateway = DecisionGateway(Settings(_env_file=None), providers={"fake": provider})
    with pytest.raises(DecisionInfrastructureDisabled):
        gateway.evaluate(
            db_session,
            user,
            event=_event(),
            question=MEMORY_CONTEXT_RELEVANT_V1,
            context=_context(),
        )
    assert provider.calls == 0
    assert db_session.scalar(select(func.count(CognitiveTrace.id))) == 0


def test_gateway_provider_resolution_validation_and_timeout_normalization(db_session) -> None:
    user = get_or_create_user(db_session)
    with pytest.raises(DecisionProviderUnavailable):
        DecisionGateway(Settings(_env_file=None, decision_infra_enabled=True, decision_provider="missing"), providers={}).evaluate(
            db_session, user, event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()
        )
    gateway = DecisionGateway(
        Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="FAKE"),
        providers={"fake": FakeDecisionProvider()},
    )
    with pytest.raises(DecisionValidationError):
        gateway.evaluate(
            db_session,
            user,
            event=_event(),
            question=MEMORY_CONTEXT_RELEVANT_V1,
            context=_context(scenario="invalid_response"),
        )
    timeout_gateway = DecisionGateway(
        Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="FAKE"),
        providers={"fake": _TimeoutProvider()},
    )
    with pytest.raises(DecisionProviderTimeout):
        timeout_gateway.evaluate(
            db_session, user, event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()
        )


def test_context_is_bounded_structured_and_forbids_whole_dump_fields() -> None:
    context = _context()
    assert len(context.facts) == 2
    assert context.memory_refs == ("memory-1",)
    assert all(fact.provenance for fact in context.facts)
    assert "conversation_history" not in DecisionContext.model_fields
    assert "semantic_memory_dump" not in DecisionContext.model_fields

    too_many = {f"fact_{index}": index for index in range(25)}
    with pytest.raises(ValueError, match="24-fact"):
        DecisionContextBuilder().build(event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, facts=too_many)
    with pytest.raises(ValidationError):
        DecisionContext.model_validate({**context.model_dump(), "conversation_history": ["entire chat"]})


def test_cognitive_event_and_domain_event_adapter_preserve_references(db_session) -> None:
    user = get_or_create_user(db_session)
    domain_event = Event(
        user_id=user.id,
        event_type="learning.exam_updated",
        aggregate_type="exam",
        aggregate_id="exam-1",
        world_revision=9,
        payload={"changed": ["deadline"]},
        occurred_at=datetime.now(UTC),
    )
    db_session.add(domain_event)
    db_session.flush()
    cognitive = cognitive_event_from_domain_event(
        domain_event,
        domains=("learning",),
        correlation_id="correlation-9",
        causation_id="cause-8",
    )
    serialized = cognitive.model_dump(mode="json")
    assert serialized["source_event_id"] == domain_event.id
    assert serialized["world_revision"] == 9
    assert serialized["entity_refs"][0]["entity_id"] == "exam-1"
    assert serialized["metadata"] == {"payload_keys": ["changed"]}
    assert "changed" not in serialized["input_payload"]


def test_contributor_returns_zero_or_bounded_versioned_questions() -> None:
    contributor = StaticDecisionContributor(
        name="memory-test",
        event_types=("test.decision_requested",),
        questions=(MEMORY_CONTEXT_RELEVANT_V1,),
    )
    requests = contributor.contribute(event=_event(), state={})
    assert len(requests) == 1
    assert requests[0].question.question_version == 1
    unrelated = _event().model_copy(update={"event_type": "unrelated.event"})
    assert contributor.contribute(event=unrelated, state={}) == ()
    with pytest.raises(ValueError, match="4-question"):
        StaticDecisionContributor(
            name="too-many",
            event_types=("test",),
            questions=(MEMORY_CONTEXT_RELEVANT_V1,) * 5,
        )


def test_end_to_end_decision_trace_and_audit_do_not_mutate_domain_state(db_session) -> None:
    user = get_or_create_user(db_session)
    counts_before = {
        "actions": db_session.scalar(select(func.count(Action.id))),
        "events": db_session.scalar(select(func.count(Event.id))),
        "blocks": db_session.scalar(select(func.count(PlanBlock.id))),
        "world_revision": user.world_revision,
    }
    contributor = StaticDecisionContributor(
        name="memory-test",
        event_types=("test.decision_requested",),
        questions=(MEMORY_CONTEXT_RELEVANT_V1,),
    )
    request = contributor.contribute(event=_event(), state={})[0]
    context = DecisionContextBuilder().build(
        event=_event(),
        question=request.question,
        facts={"candidate_kind": "preference"},
        memory_refs=("memory-1",),
    )
    gateway = DecisionGateway(Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="FAKE"))
    execution = gateway.evaluate(
        db_session,
        user,
        event=_event(),
        question=request.question,
        context=context,
        skill_name="decision-fixture",
        skill_version="1",
    )
    assert execution.trace_status == "persisted"
    trace = db_session.get(CognitiveTrace, execution.trace_id)
    assert trace.question_id == "memory.context_relevant"
    assert trace.question_version == 1
    assert trace.provider == "fake"
    assert trace.provider_version == "1"
    assert trace.model_version == "fake-decision-checkpoint-v1"
    assert trace.policy_version == "decision-policy-v1"
    assert trace.probabilities_json
    assert trace.confidence == 0.82
    assert trace.latency_ms >= 0
    forbidden_columns = {"reasoning", "chain_of_thought", "scratchpad", "private_reasoning"}
    assert forbidden_columns.isdisjoint(CognitiveTrace.__table__.columns.keys())

    original_output = dict(trace.output_json)
    audit = DecisionTraceService().add_audit(
        db_session,
        user,
        trace=trace,
        audit_type="outcome_observed",
        outcome={"accepted": True},
        correction={"label": "still_relevant"},
        training_eligible=True,
    )
    assert isinstance(audit, DecisionAudit)
    assert audit.trace_id == trace.id
    assert trace.output_json == original_output

    assert db_session.scalar(select(func.count(Action.id))) == counts_before["actions"]
    assert db_session.scalar(select(func.count(Event.id))) == counts_before["events"]
    assert db_session.scalar(select(func.count(PlanBlock.id))) == counts_before["blocks"]
    assert user.world_revision == counts_before["world_revision"]


def test_completed_trace_rows_are_immutable(db_session) -> None:
    user = get_or_create_user(db_session)
    execution = DecisionGateway(Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="FAKE")).evaluate(
        db_session, user, event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()
    )
    trace = db_session.get(CognitiveTrace, execution.trace_id)
    trace.status = "rewritten"
    with pytest.raises(ValueError, match="immutable"):
        db_session.flush()
    db_session.rollback()


def test_trace_failure_is_observable_without_converting_decision_or_mutating_domain(db_session, caplog) -> None:
    user = get_or_create_user(db_session)
    gateway = DecisionGateway(
        Settings(_env_file=None, decision_infra_enabled=True, decision_routing_mode="FAKE"),
        trace_service=_FailingTraceService(),
    )
    execution = gateway.evaluate(
        db_session, user, event=_event(), question=MEMORY_CONTEXT_RELEVANT_V1, context=_context()
    )
    assert execution.trace_status == "failed"
    assert execution.trace_id is None
    assert "decision_trace_persistence_failed" in caplog.text
    assert db_session.scalar(select(func.count(PlanBlock.id))) == 0


def test_benchmark_records_validity_identity_latency_and_invalid_results() -> None:
    results = DecisionBenchmarkHarness(FakeDecisionProvider()).run(representative_fake_cases())
    assert len(results) == 3
    assert results[0].schema_valid is True
    assert results[0].question_version == 1
    assert results[0].provider == "fake"
    assert results[0].model_version == "fake-decision-checkpoint-v1"
    assert results[0].latency_ms >= 0
    assert results[1].confidence == 0.51
    assert results[2].schema_valid is False
    assert results[2].error_code == "decision_validation_error"


def test_structured_question_uses_declared_schema() -> None:
    question = DecisionQuestion(
        question_id="system.fixture_structured",
        question_version=1,
        family="system",
        output_type=DecisionOutputType.structured,
        description="Exercise a bounded structured decision.",
        response_schema={
            "type": "object",
            "properties": {"label": {"type": "string"}, "accepted": {"type": "boolean"}},
            "required": ["label", "accepted"],
            "additionalProperties": False,
        },
    )
    event = _event()
    context = DecisionContextBuilder().build(event=event, question=question)
    result = FakeDecisionProvider().evaluate(question=question, context=context)
    result.validate_for(question)
    invalid = result.model_copy(update={"selected_answer": {"label": "missing boolean"}})
    with pytest.raises(ValueError, match="missing required"):
        invalid.validate_for(question)


def test_decision_architecture_is_independent_and_contains_no_future_provider() -> None:
    assert not issubclass(DecisionGateway, AIGateway)
    signature = inspect.signature(DecisionProvider.evaluate)
    assert set(signature.parameters) == {"self", "question", "context"}
    decision_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (BACKEND_DIR / "app" / "decision").rglob("*.py")
    )
    assert "LayaLocalProvider" in decision_source
    assert "JevProvider" in decision_source
    assert "ToolRegistry" not in decision_source

    offenders = []
    for source_path in (BACKEND_DIR / "app").rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PlanBlock" for node in ast.walk(tree)):
            if "planning" not in source_path.relative_to(BACKEND_DIR / "app").parts:
                offenders.append(str(source_path))
    assert offenders == []


def test_production_cannot_enable_fake_decision_intelligence() -> None:
    with pytest.raises(ValidationError, match="cannot be enabled"):
        Settings(
            _env_file=None,
            app_env="production",
            development_auth_enabled=False,
            database_url="postgresql+psycopg://user:password@example.invalid/life_os",
            supabase_jwt_secret="test-secret",
            supabase_project_url="https://project.example.invalid",
            authorized_auth_subjects="user-1",
            cors_origins="https://life.example.invalid",
            decision_infra_enabled=True,
            decision_provider="fake",
            decision_routing_mode="FAKE",
        )
