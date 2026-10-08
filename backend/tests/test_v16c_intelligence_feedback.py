from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_or_create_user
from app.assistant.schemas import AssistantMessageRequest, AssistantResponseType
from app.assistant.service import AssistantService
from app.core.config import Settings
from app.database import models  # noqa: F401
from app.database.base import Base
from app.database.models import (
    AttentionItem,
    CognitiveTrace,
    ConversationMessage,
    DecisionAudit,
    DecisionTrainingExample,
    FeedbackResponse,
    FeedbackSession,
)
from app.feedback.command import match_log_feedback
from app.feedback.quality import IntelligenceQualityService
from app.feedback.questions import FeedbackQuestionSelector
from app.feedback.schemas import (
    FeedbackConfidence,
    FeedbackDimension,
    FeedbackResponseInput,
    FeedbackScope,
    FeedbackSessionStatus,
    QualityFilter,
)
from app.feedback.service import FeedbackService
from app.feedback.targeting import FeedbackTraceSelector
from app.conversations.service import ConversationService
from app.workspaces.schemas import CookingWorkspacePayload, StudyWorkspacePayload, WorkspaceType
from app.workspaces.service import ActiveWorkspaceService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        intelligence_feedback_enabled=True,
        decision_infra_enabled=True,
        cognitive_workspace_enabled=True,
        attention_policy_enabled=True,
        **overrides,
    )


def _conversation(db, user, title="Feedback parent"):
    return ConversationService(_settings()).create_thread(db, user, title=title, default_skill="self-core")


def _trace(
    db,
    user,
    *,
    conversation_id=None,
    workspace_id=None,
    family="attention",
    question_id="attention.action",
    selected_answer="MENTION_WHEN_NATURAL",
    event_source="cognitive_cycle",
    event_type="attention.candidate",
    completed_at=NOW,
    planner_ref=None,
):
    trace = CognitiveTrace(
        user_id=user.id,
        cognitive_event_id=f"event:{question_id}:{completed_at.timestamp()}",
        event_type=event_type,
        event_source=event_source,
        conversation_thread_id=conversation_id,
        workspace_ref=workspace_id,
        world_revision=user.world_revision,
        question_id=question_id,
        question_version=1,
        question_family=family,
        output_type="categorical",
        status="completed",
        provider="fake",
        provider_version="1",
        model_version="fake-decision-checkpoint-v1",
        policy_version="decision-policy-v1",
        started_at=completed_at - timedelta(milliseconds=5),
        completed_at=completed_at,
        latency_ms=5,
        context_json={"facts": [{"key": "broad_context", "value": "HOME"}]},
        context_refs_json=[{"entity_type": "context", "entity_id": "home"}],
        memory_refs_json=["memory:1"] if family == "memory" else [],
        pattern_refs_json=["pattern:1"],
        input_json={"question_description": "Bounded decision"},
        output_json={"selected_answer": selected_answer},
        probabilities_json={selected_answer: 0.82, "SILENT": 0.18},
        confidence=0.82,
        planner_ref=planner_ref,
        tool_call_refs_json=[],
        state_change_refs_json=[],
        metadata_json={"cycle_id": "cycle:1", "situation_snapshot_ref": "situation:1"},
    )
    db.add(trace)
    db.flush()
    return trace


def _start(db, user, conversation, command="Log feedback. Bad timing."):
    return FeedbackService(_settings()).start_from_command(
        db,
        user,
        command=command,
        parent_conversation_id=conversation.id if conversation else None,
        now=NOW,
    )


def _answer(service, db, user, state, score, *, skip=False, scope=FeedbackScope.exact_case, explanation=None, explicit_scope_statement=None):
    question = state.next_question
    assert question is not None
    return service.submit_response(
        db,
        user,
        state.session_id,
        FeedbackResponseInput(
            question_id=question.question_id,
            question_version=question.question_version,
            score=None if skip else score,
            is_skipped=skip,
            feedback_scope=scope,
            feedback_confidence=FeedbackConfidence.high,
            explanation=explanation,
            explicit_scope_statement=explicit_scope_statement,
        ),
    )


@pytest.mark.parametrize("text", ["Log feedback", "log feedback", " Log feedback. ", "Log feedback. Bad timing."])
def test_reserved_command_is_deterministic_and_extracts_only_inline_evidence(text) -> None:
    result = match_log_feedback(text)
    assert result.matched
    if "Bad timing" in text:
        assert result.inline_explanation == "Bad timing."


@pytest.mark.parametrize(
    "text",
    ["Please log feedback later", "Log some feedback", "I want to log feedback about this", "feedback"],
)
def test_reserved_command_does_not_fuzzy_match_normal_sentences(text) -> None:
    assert not match_log_feedback(text).matched


def test_feedback_scale_enforces_skip_as_distinct_from_zero() -> None:
    base = {"question_id": "feedback.timing", "question_version": 1}
    assert FeedbackResponseInput(**base, score=0).score == 0
    assert FeedbackResponseInput(**base, score=5).score == 5
    assert FeedbackResponseInput(**base, is_skipped=True).is_skipped
    with pytest.raises(ValidationError):
        FeedbackResponseInput(**base, score=6)
    with pytest.raises(ValidationError):
        FeedbackResponseInput(**base, score=-1)
    with pytest.raises(ValidationError):
        FeedbackResponseInput(**base, score=3, is_skipped=True)
    with pytest.raises(ValidationError):
        FeedbackResponseInput(**base)


def test_trace_selection_scopes_to_conversation_and_ignores_later_background(db_session) -> None:
    user = get_or_create_user(db_session)
    first = _conversation(db_session, user, "First")
    second = _conversation(db_session, user, "Second")
    target = _trace(db_session, user, conversation_id=first.id, completed_at=NOW)
    _trace(db_session, user, conversation_id=second.id, completed_at=NOW + timedelta(minutes=3))
    _trace(
        db_session,
        user,
        conversation_id=first.id,
        completed_at=NOW + timedelta(minutes=5),
        event_source="worker",
        event_type="housekeeping.completed",
    )
    selected = FeedbackTraceSelector().select_target(
        db_session, user, conversation_id=first.id, foreground_workspace=None
    )
    assert selected.trace.id == target.id


def test_workspace_related_trace_is_targetable_and_no_context_has_safe_failure(db_session) -> None:
    user = get_or_create_user(db_session)
    workspace = ActiveWorkspaceService().start_workspace(
        db_session,
        user,
        workspace_type=WorkspaceType.study,
        payload=StudyWorkspacePayload(course_ref="course:1", topic_ref="topic:graphs"),
    )
    trace = _trace(db_session, user, workspace_id=workspace.id)
    selected = FeedbackTraceSelector().select_target(
        db_session, user, conversation_id=None, foreground_workspace=workspace
    )
    assert selected.trace.id == trace.id

    other_user = get_or_create_user(db_session, email="other@example.test", auth_subject="other")
    assert FeedbackTraceSelector().select_target(
        db_session, other_user, conversation_id=None, foreground_workspace=None
    ) is None


def test_nested_feedback_freezes_original_context_and_preserves_parent_activity(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    workspace = ActiveWorkspaceService().start_workspace(
        db_session,
        user,
        workspace_type=WorkspaceType.cooking,
        payload=CookingWorkspacePayload(recipe_ref="recipe:curry", current_step="Simmer"),
        conversation_thread_id=conversation.id,
        current_phase="cooking",
        current_step="Simmer",
    )
    trace = _trace(db_session, user, conversation_id=conversation.id, workspace_id=workspace.id)
    item = AttentionItem(
        user_id=user.id,
        action="MENTION_WHEN_NATURAL",
        reason_code="social_suggestion",
        subject="Message Mehmet tonight",
        priority=55,
        source_trace_id=trace.id,
        workspace_id=workspace.id,
        status="SURFACED",
        deduplication_key="feedback:target",
    )
    db_session.add(item)
    db_session.flush()
    message_count = db_session.scalar(select(func.count(ConversationMessage.id)))

    service = FeedbackService(_settings())
    state = service.start_from_command(
        db_session,
        user,
        command="Log feedback. Bad timing.",
        parent_conversation_id=conversation.id,
        attention_item_id=item.id,
        now=NOW,
    )
    session = db_session.get(FeedbackSession, state.session_id)
    frozen = session.frozen_context_json
    assert session.parent_workspace_id == workspace.id
    assert session.parent_conversation_id == conversation.id
    assert frozen["workspace"]["current_step"] == "Simmer"
    assert workspace.is_foreground and workspace.status == "ACTIVE"
    assert db_session.scalar(select(func.count(ConversationMessage.id))) == message_count

    workspace.current_step = "Serve"
    workspace.current_phase = "plating"
    workspace.state_revision += 1
    user.world_revision += 1
    db_session.flush()
    state = _answer(service, db_session, user, state, 0)
    state = _answer(service, db_session, user, state, 4)
    state = _answer(service, db_session, user, state, 2)
    completed = service.complete(db_session, user, state.session_id, now=NOW + timedelta(minutes=2))
    examples = list(db_session.scalars(
        select(DecisionTrainingExample).where(DecisionTrainingExample.feedback_session_id == session.id)
    ))
    assert len(examples) == 3
    assert all(example.context_json["workspace"]["current_step"] == "Simmer" for example in examples)
    assert {example.feedback_dimension: example.feedback_score for example in examples} == {
        "TIMING": 0,
        "CONTENT_USEFULNESS": 4,
        "CONTEXT_SELECTION": 2,
    }
    assert completed.resume_state["resume_result"]["same_conversation"]
    assert completed.resume_state["resume_result"]["same_workspace"]
    assert completed.resume_state["resume_result"]["external_workspace_change"]
    assert db_session.get(CognitiveTrace, trace.id).output_json["selected_answer"] == "MENTION_WHEN_NATURAL"
    assert db_session.scalar(select(func.count(DecisionAudit.id)).where(DecisionAudit.feedback_ref == session.id)) == 1


def test_adaptive_question_selection_uses_trace_semantics_and_caps_at_four(db_session) -> None:
    user = get_or_create_user(db_session)
    selector = FeedbackQuestionSelector(max_questions=4)
    memory = _trace(db_session, user, family="memory", question_id="memory.context_relevant", selected_answer="relevant")
    ask = _trace(db_session, user, selected_answer="ASK", completed_at=NOW + timedelta(seconds=1))
    planning = _trace(
        db_session,
        user,
        family="planning",
        question_id="planning.feasibility",
        selected_answer="feasible",
        completed_at=NOW + timedelta(seconds=2),
        planner_ref="plan:1",
    )
    assert [q.dimension for q in selector.select(memory).questions][:2] == [
        FeedbackDimension.memory_correctness,
        FeedbackDimension.context_selection,
    ]
    assert [q.dimension for q in selector.select(ask).questions][0] == FeedbackDimension.question_usefulness
    assert [q.dimension for q in selector.select(planning).questions][0] == FeedbackDimension.plan_realism
    assert len(selector.select(planning).questions) <= 4
    assert selector.select(ask, inline_explanation="This was bad.").clarification is not None
    assert selector.select(ask, inline_explanation="Bad timing.").clarification is None


def test_scope_stays_contextual_unless_explicitly_generalized(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    _trace(db_session, user, conversation_id=conversation.id)
    service = FeedbackService(_settings())
    state = service.start_from_command(
        db_session, user, command="Log feedback. Bad timing.", parent_conversation_id=conversation.id
    )
    state = _answer(service, db_session, user, state, 0, scope=FeedbackScope.general_preference)
    response = db_session.scalar(select(FeedbackResponse).where(FeedbackResponse.feedback_session_id == state.session_id))
    assert response.feedback_scope == FeedbackScope.exact_case.value


def test_explicit_permanent_rule_is_preserved_as_policy_handoff(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    _trace(db_session, user, conversation_id=conversation.id, selected_answer="INTERRUPT")
    statement = "Never interrupt me with non-urgent things while I study."
    service = FeedbackService(_settings())
    state = service.start_from_command(
        db_session, user, command=f"Log feedback. {statement}", parent_conversation_id=conversation.id
    )
    state = _answer(
        service,
        db_session,
        user,
        state,
        0,
        scope=FeedbackScope.permanent_explicit_rule,
        explicit_scope_statement=statement,
    )
    response = db_session.scalar(select(FeedbackResponse).where(FeedbackResponse.feedback_session_id == state.session_id))
    session = db_session.get(FeedbackSession, state.session_id)
    assert response.feedback_scope == FeedbackScope.permanent_explicit_rule.value
    assert session.metadata_json["explicit_policy_handoff"]["statement"] == statement
    assert "standing" not in session.metadata_json["explicit_policy_handoff"]


def test_skip_creates_no_training_label_and_quality_excludes_it(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    _trace(db_session, user, conversation_id=conversation.id)
    service = FeedbackService(_settings())
    state = service.start_from_command(
        db_session, user, command="Log feedback. Bad timing.", parent_conversation_id=conversation.id
    )
    state = _answer(service, db_session, user, state, 0)
    state = _answer(service, db_session, user, state, 4)
    state = _answer(service, db_session, user, state, None, skip=True)
    service.complete(db_session, user, state.session_id)
    examples = list(db_session.scalars(
        select(DecisionTrainingExample).where(DecisionTrainingExample.feedback_session_id == state.session_id)
    ))
    assert len(examples) == 2
    assert {example.feedback_dimension for example in examples} == {"TIMING", "CONTENT_USEFULNESS"}

    quality = IntelligenceQualityService().summarize(db_session, user, filters=QualityFilter())
    dimensions = {item.dimension: item for item in quality.dimensions}
    assert quality.session_count == 1 and quality.completed_session_count == 1
    assert quality.numeric_response_count == 2 and quality.skipped_response_count == 1
    assert dimensions[FeedbackDimension.timing].average_score == 0
    assert dimensions[FeedbackDimension.content_usefulness].average_score == 4
    assert dimensions[FeedbackDimension.context_selection].average_score is None
    assert dimensions[FeedbackDimension.context_selection].skip_rate == 1
    assert all(item.low_sample_warning for item in quality.dimensions)
    assert quality.decision_family_distribution == {"attention": 1}
    assert quality.provider_distribution == {"fake": 1}


def test_feedback_survives_fresh_session_and_resumes_same_parent(tmp_path: Path) -> None:
    database_path = tmp_path / "feedback-restart.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as first:
        user = get_or_create_user(first, email="feedback-restart@example.test", auth_subject="feedback-restart")
        conversation = _conversation(first, user)
        workspace = ActiveWorkspaceService().start_workspace(
            first,
            user,
            workspace_type=WorkspaceType.study,
            payload=StudyWorkspacePayload(course_ref="course:1", topic_ref="topic:1"),
            conversation_thread_id=conversation.id,
            current_phase="practice",
        )
        _trace(first, user, conversation_id=conversation.id, workspace_id=workspace.id, selected_answer="ASK")
        service = FeedbackService(_settings())
        state = service.start_from_command(first, user, command="Log feedback", parent_conversation_id=conversation.id)
        state = _answer(service, first, user, state, 1)
        identifiers = (user.id, conversation.id, workspace.id, state.session_id)
        first.commit()
    engine.dispose()

    fresh_engine = create_engine(f"sqlite:///{database_path}", future=True)
    FreshSession = sessionmaker(bind=fresh_engine, expire_on_commit=False, future=True)
    with FreshSession() as second:
        user = second.get(models.UserProfile, identifiers[0])
        service = FeedbackService(_settings())
        session = service.get_active(second, user, conversation_id=identifiers[1])
        assert session.id == identifiers[3]
        state = service.state(second, user, session)
        while state.next_question is not None:
            state = _answer(service, second, user, state, 3)
        completed = service.complete(second, user, state.session_id)
        assert completed.status == FeedbackSessionStatus.completed
        assert completed.resume_state["resume_result"]["conversation_id"] == identifiers[1]
        assert completed.resume_state["resume_result"]["workspace_id"] == identifiers[2]
        second.commit()
    fresh_engine.dispose()


def test_assistant_intercepts_feedback_before_ai_memory_and_conversation_append(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    _trace(db_session, user, conversation_id=conversation.id)
    before = db_session.scalar(select(func.count(ConversationMessage.id)))
    response = AssistantService(_settings()).handle_message(
        db_session,
        user,
        AssistantMessageRequest(message="Log feedback. Bad timing.", thread_id=conversation.id),
    )
    assert response.response_type == AssistantResponseType.feedback
    assert response.model_tier.value == "NO_AI"
    assert response.provider is None and response.model is None
    assert response.feedback_session_id is not None
    assert db_session.scalar(select(func.count(ConversationMessage.id))) == before


def test_disabled_feedback_creates_no_partial_session(db_session) -> None:
    user = get_or_create_user(db_session)
    conversation = _conversation(db_session, user)
    _trace(db_session, user, conversation_id=conversation.id)
    result = FeedbackService(Settings(_env_file=None)).start_from_command(
        db_session, user, command="Log feedback", parent_conversation_id=conversation.id
    )
    assert result.result_code == "FEEDBACK_DISABLED"
    assert db_session.scalar(select(func.count(FeedbackSession.id))) == 0
