from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest, AIResponse, AIStreamChunk, AIUsageMetadata
from app.api.deps import get_or_create_user
from app.attention.schemas import AttentionAction, AttentionDecision
from app.cognition.schemas import CognitiveCycleResult, CognitiveCycleStatus
from app.communication.composer import ResponseComposer
from app.communication.intents import CommunicativeIntentFactory
from app.communication.schemas import (
    CommunicativeIntent,
    ComposeRequest,
    ResponseMode,
    ResponseModePreference,
    ResponseStreamEventType,
    SpeakingPolicy,
    SpeechAct,
    StructuredFact,
)
from app.communication.service import ResponseCompositionService
from app.core.config import Settings
from app.database.models import CognitiveTrace, ConversationMessage, DecisionAudit, Event, Plan, WorldRevision
from app.domains.kitchen.schemas import InventoryItemCreate
from app.domains.kitchen.service import add_inventory_item
from app.events.service import append_event
from app.realtime.service import RealtimeStateService
from app.workspaces.schemas import StudyWorkspacePayload, WorkspaceType
from app.workspaces.service import ActiveWorkspaceService
from tests.conftest import AUTH_HEADERS
from tests.test_v17a_strategic_proposals import _service as strategic_service
from tests.test_v17a_strategic_proposals import _stack as strategic_stack


NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        ai_enabled=True,
        response_composer_enabled=True,
        response_composer_generative_enabled=True,
        realtime_state_enabled=True,
        **overrides,
    )


def _intent(**overrides) -> CommunicativeIntent:
    values = {
        "purpose": SpeechAct.inform,
        "attention_action": AttentionAction.mention_when_natural,
        "reason_code": "inventory_depleted",
        "facts": (StructuredFact(key="item", value="tomatoes", source_ref="inventory:item-1"),),
        "fallback_template_key": "inventory_empty",
    }
    values.update(overrides)
    return CommunicativeIntent(**values)


class SpyGateway:
    def __init__(self, *, response: str = "Algorithms needs attention.", chunks: tuple[str, ...] = ()) -> None:
        self.response = response
        self.chunks = chunks
        self.calls: list[dict] = []

    def complete(self, *args, **kwargs):
        self.calls.append(kwargs)
        return AIResponse(
            text=self.response,
            provider="fake",
            model="fake-economy",
            usage=AIUsageMetadata(input_tokens=10, output_tokens=4, total_tokens=14),
            finish_status="STOP",
        )

    def stream(self, *args, **kwargs):
        self.calls.append(kwargs)
        for text in self.chunks:
            yield AIStreamChunk(text_delta=text, provider="fake", model="fake-economy")
        yield AIStreamChunk(provider="fake", model="fake-economy", done=True)


class FailingGateway:
    def complete(self, *args, **kwargs):
        raise AIProviderError("provider_unavailable", "offline", retryable=True)

    def stream(self, *args, **kwargs):
        raise AIProviderError("provider_unavailable", "offline", retryable=True)
        yield  # pragma: no cover


class PartialFailingGateway:
    def stream(self, *args, **kwargs):
        yield AIStreamChunk(text_delta="Partial ", provider="fake", model="fake-economy")
        raise AIProviderError("provider_timeout", "timed out", retryable=True)


def _trace(db, user) -> CognitiveTrace:
    trace = CognitiveTrace(
        user_id=user.id,
        cognitive_event_id="event:v17b",
        event_type="strategy.proposal.created",
        event_source="test",
        question_id="attention.action",
        question_version=1,
        question_family="attention",
        output_type="ENUM",
        status="completed",
        provider="fake",
        policy_version="decision-policy-v1",
        started_at=NOW,
        completed_at=NOW,
    )
    db.add(trace)
    db.flush()
    return trace


def test_communicative_intent_policy_and_structured_bridges_are_versioned():
    policy = SpeakingPolicy()
    assert policy.version == "response-policy-v1"
    decision = AttentionDecision(
        action=AttentionAction.ask,
        reason_code="clarification_needed",
        subject="Study priority",
        priority=90,
        urgency=0.7,
        confidence=0.8,
        evidence_quality=0.8,
        source_trace_id="trace-1",
        workspace_id="workspace-1",
        policy_version="attention-policy-v1",
    )
    intent = CommunicativeIntentFactory().from_attention(
        decision,
        question="Should Algorithms remain the priority?",
        facts=(StructuredFact(key="course", value="Algorithms"),),
    )
    assert intent.purpose == SpeechAct.ask
    assert intent.user_response_required is True
    assert intent.cognitive_trace_ref == "trace-1"
    assert intent.tone.value == "SERIOUS"
    assert CommunicativeIntent.model_validate_json(intent.model_dump_json()) == intent

    cycle = CognitiveCycleResult(
        cycle_id="cycle-1",
        status=CognitiveCycleStatus.completed,
        trace_refs=("trace-2",),
        attention_action=AttentionAction.mention_when_natural,
        attention_reason_code="trajectory_shifted",
    )
    bridged = CommunicativeIntentFactory().from_cycle(cycle, subject="Algorithms")
    assert bridged.cognitive_trace_ref == "trace-2"
    assert bridged.attention_action == AttentionAction.mention_when_natural
    with pytest.raises(ValidationError):
        CommunicativeIntent.model_validate({**intent.model_dump(), "importance": 101})


def test_deterministic_composition_persists_final_message_and_silent_does_nothing(db_session):
    user = get_or_create_user(db_session)

    class NoCallGateway:
        def complete(self, *args, **kwargs):
            raise AssertionError("Deterministic composition must not call a provider.")

    service = ResponseCompositionService(_settings(), gateway=NoCallGateway())
    result = service.compose(db_session, user, ComposeRequest(intent=_intent()))
    db_session.commit()
    assert result is not None
    assert result.mode == ResponseMode.deterministic
    assert result.text == "Tomatoes are now empty."
    message = db_session.get(ConversationMessage, result.message_id)
    assert message.content == result.text
    assert message.metadata_json["communicative_intent"]["facts"][0]["source_ref"] == "inventory:item-1"
    assert message.metadata_json["response_policy_version"] == "response-policy-v1"
    before = db_session.scalar(select(func.count(ConversationMessage.id)))
    silent = service.compose(
        db_session,
        user,
        ComposeRequest(intent=_intent(attention_action=AttentionAction.silent)),
    )
    assert silent is None
    assert db_session.scalar(select(func.count(ConversationMessage.id))) == before


def test_generative_composition_is_economy_toolless_bounded_and_falls_back(db_session):
    user = get_or_create_user(db_session)
    gateway = SpyGateway(response="Algorithms is below pace. Review the proposal before applying changes.")
    intent = _intent(
        purpose=SpeechAct.propose,
        facts=(StructuredFact(key="subject", value="Algorithms"),),
        response_mode_preference=ResponseModePreference.generative,
        fallback_template_key="plan_proposal",
    )
    result = ResponseCompositionService(_settings(), gateway=gateway).compose(
        db_session, user, ComposeRequest(intent=intent, persist_message=False, recent_context=("Earlier wording",))
    )
    assert result.mode == ResponseMode.generative
    call = gateway.calls[0]
    assert call["capability"].value == "ECONOMY"
    assert call["request"].tools == []
    assert len(call["request"].messages[0].content) <= ResponseComposer.max_dynamic_chars

    fallback = ResponseCompositionService(_settings(), gateway=FailingGateway()).compose(
        db_session, user, ComposeRequest(intent=intent, persist_message=False)
    )
    assert fallback.mode == ResponseMode.deterministic_fallback
    assert fallback.fallback_used is True
    assert "recovery proposal" in fallback.text

    with pytest.raises(ValueError, match="numeric claim"):
        ResponseComposer().validate_generated(intent, "Algorithms needs 99 hours.")


def test_stream_contract_orders_chunks_persists_only_complete_and_handles_failures(db_session):
    user = get_or_create_user(db_session)
    intent = _intent(
        facts=(StructuredFact(key="subject", value="Algorithms"),),
        response_mode_preference=ResponseModePreference.generative,
    )
    service = ResponseCompositionService(_settings(), gateway=SpyGateway(chunks=("Algorithms ", "needs attention.")))
    events = list(service.stream(db_session, user, ComposeRequest(intent=intent)))
    assert [item.event_type for item in events] == [
        ResponseStreamEventType.start,
        ResponseStreamEventType.text_delta,
        ResponseStreamEventType.text_delta,
        ResponseStreamEventType.complete,
    ]
    assert [item.sequence for item in events] == [0, 1, 2, 3]
    final = events[-1].final_response
    assert final.text == "Algorithms needs attention."
    assert db_session.get(ConversationMessage, final.message_id).content == final.text

    fallback_events = list(
        ResponseCompositionService(_settings(), gateway=FailingGateway()).stream(
            db_session, user, ComposeRequest(intent=intent, persist_message=False)
        )
    )
    assert fallback_events[-1].event_type == ResponseStreamEventType.complete
    assert fallback_events[-1].final_response.mode == ResponseMode.deterministic_fallback

    before = db_session.scalar(select(func.count(ConversationMessage.id)))
    partial = list(
        ResponseCompositionService(_settings(), gateway=PartialFailingGateway()).stream(
            db_session, user, ComposeRequest(intent=intent)
        )
    )
    assert partial[-1].event_type == ResponseStreamEventType.error
    assert db_session.scalar(select(func.count(ConversationMessage.id))) == before


def test_ai_gateway_adapts_non_streaming_provider_to_stream_contract(db_session):
    user = get_or_create_user(db_session)

    class CompleteOnlyProvider:
        def complete(self, *, model, request):
            return AIResponse(
                text="One complete chunk.",
                provider="fake",
                model=model,
                usage=AIUsageMetadata(output_tokens=3, total_tokens=3),
                finish_status="STOP",
            )

    gateway = AIGateway(_settings(ai_provider="fake"), providers={"fake": CompleteOnlyProvider()})
    chunks = list(gateway.stream(
        db_session,
        user,
        request_id="00000000-0000-0000-0000-000000000017",
        assistant_role="RESPONSE_COMPOSER",
        skill_name="response-composer",
        skill_version="1",
        capability=AICapability.economy,
        request=AIRequest(system_instruction="Render.", messages=[AIMessage(role="user", content="Intent")]),
    ))
    assert [chunk.text_delta for chunk in chunks] == ["One complete chunk.", ""]
    assert chunks[-1].done is True


def test_communication_audit_preserves_decision_intent_and_prose_separation(db_session):
    user = get_or_create_user(db_session)
    trace = _trace(db_session, user)
    result = ResponseCompositionService(_settings()).compose(
        db_session,
        user,
        ComposeRequest(intent=_intent(cognitive_trace_ref=trace.id)),
    )
    db_session.commit()
    audit = db_session.scalar(select(DecisionAudit).where(DecisionAudit.trace_id == trace.id, DecisionAudit.audit_type == "response_composed"))
    assert audit.downstream_action_ref == result.message_id
    assert audit.metadata_json["communicative_intent_id"] == result.intent_id
    assert audit.metadata_json["response_policy_version"] == "response-policy-v1"
    assert audit.metadata_json["streamed"] is False


def test_realtime_inventory_workspace_and_conversation_converge_from_committed_truth(client, db_session):
    assert client.get("/api/v1/realtime/events").status_code == 401
    user = get_or_create_user(db_session)
    initial_revision = user.world_revision
    item = add_inventory_item(db_session, user, InventoryItemCreate(ingredient_name="Tomatoes", quantity=3))
    db_session.commit()

    catchup = client.get(
        f"/api/v1/realtime/events?after_revision={initial_revision}", headers=AUTH_HEADERS
    ).json()
    assert catchup["resync_required"] is False
    assert catchup["events"][0]["world_revision"] == initial_revision + 1
    assert "inventory" in catchup["events"][0]["invalidates"]
    assert any(row["id"] == item.id for row in client.get("/api/v1/kitchen/inventory", headers=AUTH_HEADERS).json())

    cursor = catchup["current_revision"]
    workspace = ActiveWorkspaceService().start_workspace(
        db_session,
        user,
        workspace_type=WorkspaceType.study,
        payload=StudyWorkspacePayload(topic_ref="topic:graphs", current_question_ref="question:8"),
    )
    db_session.commit()
    workspace_events = RealtimeStateService().changes_since(db_session, user, after_revision=cursor)
    assert any("active_workspace" in event.invalidates for event in workspace_events.events)
    foreground = client.get("/api/v1/workspaces/foreground", headers=AUTH_HEADERS).json()
    assert foreground["id"] == workspace.id
    assert foreground["payload"]["current_question_ref"] == "question:8"

    cursor = workspace_events.current_revision
    response = client.post(
        "/api/v1/communication/compose",
        headers=AUTH_HEADERS,
        json={"intent": _intent().model_dump(mode="json")},
    )
    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]
    conversation_events = RealtimeStateService().changes_since(db_session, user, after_revision=cursor)
    assert any(f"conversation:{conversation_id}" in event.invalidates for event in conversation_events.events)
    stream = client.get("/api/v1/realtime/stream?after_revision=0&once=true", headers=AUTH_HEADERS)
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["content-type"]
    assert "world_revision" in stream.text


def test_realtime_never_exposes_rolled_back_state_and_requires_resync_for_gap(db_session):
    user = get_or_create_user(db_session)
    append_event(
        db_session,
        user,
        event_type="inventory.adjust",
        aggregate_type="inventory_item",
        aggregate_id="rolled-back",
        payload={},
    )
    db_session.rollback()
    db_session.refresh(user)
    assert RealtimeStateService().changes_since(db_session, user, after_revision=0).events == []

    for aggregate_id in ("one", "two", "three"):
        append_event(
            db_session,
            user,
            event_type="inventory.adjust",
            aggregate_type="inventory_item",
            aggregate_id=aggregate_id,
            payload={},
        )
    db_session.commit()
    db_session.execute(delete(WorldRevision).where(WorldRevision.user_id == user.id, WorldRevision.revision == 2))
    db_session.commit()
    catchup = RealtimeStateService().changes_since(db_session, user, after_revision=1)
    assert catchup.resync_required is True
    assert catchup.reason_code == "revision_gap"
    ahead = RealtimeStateService().changes_since(db_session, user, after_revision=99)
    assert ahead.resync_required is True
    assert ahead.current_revision == 3
    assert ahead.reason_code == "client_revision_ahead"


def test_accepted_plan_proposal_advances_revision_and_refetches_canonical_plan(db_session):
    user, exam, _donor, old_plan, _protected, now = strategic_stack(db_session)
    service = strategic_service()
    proposal = service.evaluate_exam(db_session, user, exam.id, now=now).proposal
    db_session.commit()
    cursor = user.world_revision
    accepted = service.accept(db_session, user, proposal.id)
    db_session.commit()
    catchup = RealtimeStateService().changes_since(db_session, user, after_revision=cursor)
    assert catchup.current_revision > cursor
    assert any("current_plan" in event.invalidates for event in catchup.events)
    assert any("plan_proposals" in event.invalidates for event in catchup.events)

    FreshSession = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    with FreshSession() as fresh:
        assert fresh.get(Plan, old_plan.id).status == "superseded"
        assert fresh.get(Plan, accepted.applied_plan_id).status == "current"


def test_response_composer_has_no_canonical_write_or_tool_authority():
    source = Path(ResponseComposer.__module__.replace(".", "/") + ".py")
    source = Path(__file__).resolve().parents[1] / source
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(name.startswith("sqlalchemy") for name in imported)
    assert not any(name.startswith("app.planning") for name in imported)
    assert not any(name.startswith("app.tools") for name in imported)
    assert "app.ai.gateway" not in imported
    assert "Session" not in source.read_text(encoding="utf-8")
