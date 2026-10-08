from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_or_create_user
from app.attention.curiosity import CuriosityPolicy
from app.attention.manager import AttentionManager
from app.attention.schemas import (
    AttentionAction,
    AttentionCandidate,
    AttentionDecision,
    CuriosityAction,
    CuriosityInputs,
)
from app.attention.service import AttentionItemService
from app.cognition.contributors import DEFAULT_COGNITIVE_CONTRIBUTORS
from app.cognition.cycle import CognitiveCycleRunner
from app.cognition.schemas import CognitiveCycleStatus
from app.core.config import Settings
from app.database import models  # noqa: F401
from app.database.base import Base
from app.database.models import (
    Action,
    ActiveWorkspace,
    AttentionItem,
    CognitiveTrace,
    Commitment,
    DecisionAudit,
    Event,
    Goal,
    OpenThread,
    Plan,
    PlanBlock,
    ProspectiveThread,
)
from app.decision.contributors import ContributorDescriptor, DecisionContributorRegistry
from app.decision.questions import ATTENTION_ACTION_V1
from app.decision.schemas import CognitiveEvent, DecisionQuestionRequest
from app.events.service import append_event
from app.threads.eligibility import ProspectiveThreadEligibilityService
from app.threads.schemas import (
    ProspectiveEvaluationContext,
    ProspectiveThreadStatus,
    ProspectiveTriggerType,
)
from app.threads.service import OpenThreadService, ProspectiveThreadService
from app.workspaces.schemas import (
    CookingWorkspacePayload,
    PlanningWorkspacePayload,
    StudyWorkspacePayload,
    WorkoutWorkspacePayload,
    WorkspaceStatus,
    WorkspaceType,
)
from app.workspaces.service import ActiveWorkspaceService
from app.workspaces.situation import (
    BroadContext,
    ExplicitSelfReportedState,
    GlobalWorkspaceBuilder,
    MAX_ATTENTION_REFS,
    MAX_OPEN_THREAD_REFS,
    MAX_RECENT_EVENTS,
    MAX_WORKSPACE_REFS,
)


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def _enabled_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        decision_infra_enabled=True,
        cognitive_workspace_enabled=True,
        attention_policy_enabled=True,
        **overrides,
    )


def _study_payload(topic: str = "graphs") -> StudyWorkspacePayload:
    return StudyWorkspacePayload(
        course_ref="course:algorithms",
        exam_ref="exam:final",
        topic_ref=f"topic:{topic}",
        current_question_ref="question:7",
        session_goal="Solve three graph problems",
        session_phase="practice",
        started_at=NOW,
        effective_minutes=20,
        quality_self_report=0.8,
    )


def _attention_event(action: AttentionAction, **payload) -> CognitiveEvent:
    return CognitiveEvent(
        event_id=f"test:{action.value.lower()}",
        event_type="attention.candidate",
        source="test",
        occurred_at=NOW,
        input_payload={
            "subject": "A bounded attention candidate",
            "reason_code": "candidate_ready",
            "priority": 70,
            "urgency": 0.5,
            "evidence_quality": 0.8,
            **payload,
        },
        metadata={"fake_selected_answer": action.value},
    )


def test_all_workspace_payload_contracts_are_typed_versioned_and_strict() -> None:
    payloads = (
        CookingWorkspacePayload(recipe_ref="recipe:1", servings=2, current_step="Simmer"),
        WorkoutWorkspacePayload(workout_session_ref="session:1", current_set_index=2, load_kg=80, reps=5),
        _study_payload(),
        PlanningWorkspacePayload(plan_ref="plan:1", plan_version=2, current_phase="review"),
    )
    assert {payload.workspace_type for payload in payloads} == set(WorkspaceType)
    assert all(payload.payload_version == 1 for payload in payloads)
    with pytest.raises(ValidationError):
        StudyWorkspacePayload(course_ref="course:1", diagnostic_label="ADHD")
    with pytest.raises(ValidationError):
        PlanningWorkspacePayload(horizon_start=NOW, horizon_end=NOW - timedelta(days=1))


def test_workspace_lifecycle_foreground_uniqueness_and_events(db_session) -> None:
    user = get_or_create_user(db_session)
    service = ActiveWorkspaceService()
    study = service.start_workspace(
        db_session, user, workspace_type=WorkspaceType.study, payload=_study_payload(), idempotency_key="study-1"
    )
    with pytest.raises(ValidationError):
        service.start_workspace(
            db_session, user, workspace_type=WorkspaceType.cooking, payload=_study_payload(), foreground=False
        )
    assert service.start_workspace(
        db_session, user, workspace_type=WorkspaceType.study, payload=_study_payload(), idempotency_key="study-1"
    ).id == study.id
    cooking = service.start_workspace(
        db_session,
        user,
        workspace_type=WorkspaceType.cooking,
        payload=CookingWorkspacePayload(recipe_ref="recipe:1", current_step="Prep"),
    )
    db_session.flush()
    assert service.get_foreground_workspace(db_session, user).id == cooking.id
    assert db_session.scalar(select(func.count(ActiveWorkspace.id)).where(ActiveWorkspace.is_foreground.is_(True))) == 1

    service.pause_workspace(db_session, user, cooking.id, now=NOW)
    assert cooking.status == WorkspaceStatus.paused.value
    service.resume_workspace(db_session, user, cooking.id, now=NOW + timedelta(minutes=5))
    service.update_workspace(
        db_session,
        user,
        cooking.id,
        payload=CookingWorkspacePayload(recipe_ref="recipe:1", current_step="Simmer"),
        current_phase="cooking",
        current_step="Simmer",
        canonical_change_refs=("inventory_event:42",),
    )
    service.complete_workspace(db_session, user, cooking.id, now=NOW + timedelta(hours=1))
    service.abandon_workspace(db_session, user, study.id, now=NOW + timedelta(hours=1))
    assert cooking.status == WorkspaceStatus.completed.value
    assert study.status == WorkspaceStatus.abandoned.value
    assert cooking.completed_at is not None and cooking.abandoned_at is None
    assert study.abandoned_at is not None and study.completed_at is None
    emitted = set(db_session.scalars(select(Event.event_type).where(Event.aggregate_type == "active_workspace")))
    assert {"workspace.started", "workspace.paused", "workspace.resumed", "workspace.updated", "workspace.completed", "workspace.abandoned"}.issubset(emitted)


def test_workspace_reconstructs_after_fresh_database_session(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'restart.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as first:
        user = get_or_create_user(first, email="restart@example.test", auth_subject="restart-user")
        row = ActiveWorkspaceService().start_workspace(
            first,
            user,
            workspace_type=WorkspaceType.study,
            payload=_study_payload("dynamic-programming"),
            current_phase="practice",
            current_step="question:7",
        )
        workspace_id = row.id
        user_id = user.id
        first.commit()
    engine.dispose()

    fresh_engine = create_engine(f"sqlite:///{tmp_path / 'restart.db'}", future=True)
    FreshSession = sessionmaker(bind=fresh_engine, expire_on_commit=False, future=True)
    with FreshSession() as second:
        user = second.get(models.UserProfile, user_id)
        service = ActiveWorkspaceService()
        restored = service.get_foreground_workspace(second, user)
        payload = service.reconstruct_payload(restored)
        assert restored.id == workspace_id
        assert restored.current_step == "question:7"
        assert isinstance(payload, StudyWorkspacePayload)
        assert payload.topic_ref == "topic:dynamic-programming"
        assert payload.current_question_ref == "question:7"
    fresh_engine.dispose()


def test_workspace_references_do_not_overwrite_canonical_domain_state(db_session) -> None:
    user = get_or_create_user(db_session)
    action = Action(user_id=user.id, domain="learning", title="Canonical study action")
    db_session.add(action)
    db_session.flush()
    blocks_before = db_session.scalar(select(func.count(PlanBlock.id)))
    ActiveWorkspaceService().start_workspace(
        db_session,
        user,
        workspace_type=WorkspaceType.study,
        payload=StudyWorkspacePayload(course_ref="course:1", topic_ref="topic:1"),
        primary_entity_type="action",
        primary_entity_id=action.id,
    )
    db_session.flush()
    assert db_session.get(Action, action.id).title == "Canonical study action"
    assert db_session.scalar(select(func.count(PlanBlock.id))) == blocks_before


def test_open_thread_lifecycle_is_not_goal_or_task_creation(db_session) -> None:
    user = get_or_create_user(db_session)
    goal_count = db_session.scalar(select(func.count(Goal.id)))
    action_count = db_session.scalar(select(func.count(Action.id)))
    service = OpenThreadService()
    row = service.create(db_session, user, subject="Maybe learn Italian", intent="Preserve an unresolved interest")
    assert service.get(db_session, user, row.id).status == "OPEN"
    service.resolve(db_session, user, row.id, now=NOW)
    service.archive(db_session, user, row.id, now=NOW + timedelta(minutes=1))
    assert row.status == "ARCHIVED"
    assert db_session.scalar(select(func.count(Goal.id))) == goal_count
    assert db_session.scalar(select(func.count(Action.id))) == action_count


@pytest.mark.parametrize(
    ("trigger_type", "conditions", "context", "expected"),
    [
        (ProspectiveTriggerType.manual, {}, ProspectiveEvaluationContext(now=NOW, manual=True), True),
        (
            ProspectiveTriggerType.goal_state_changed,
            {"goal_ref": "goal:1", "target_state": "completed"},
            ProspectiveEvaluationContext(now=NOW, goal_states={"goal:1": "completed"}),
            True,
        ),
        (
            ProspectiveTriggerType.location_relevant,
            {"location": "GYM"},
            ProspectiveEvaluationContext(now=NOW, location="GYM"),
            True,
        ),
        (
            ProspectiveTriggerType.event_available,
            {"observation_key": "movie:released", "expected_value": True},
            ProspectiveEvaluationContext(now=NOW),
            False,
        ),
    ],
)
def test_prospective_deterministic_trigger_contracts(db_session, trigger_type, conditions, context, expected) -> None:
    user = get_or_create_user(db_session)
    row = ProspectiveThreadService().create(
        db_session,
        user,
        subject="A future possibility",
        intent="Evaluate only when triggered",
        trigger_type=trigger_type,
        trigger_conditions=conditions,
    )
    result = ProspectiveThreadEligibilityService().evaluate(row, context)
    assert result.eligible is expected
    assert db_session.scalar(select(func.count(Action.id))) == 0
    assert db_session.scalar(select(func.count(PlanBlock.id))) == 0


def test_prospective_date_thread_is_dormant_then_eligible_and_expires(db_session) -> None:
    user = get_or_create_user(db_session)
    service = ProspectiveThreadService()
    row = service.create(
        db_session,
        user,
        subject="See the film when it releases",
        intent="Mention near release",
        trigger_type=ProspectiveTriggerType.date_approaching,
        trigger_conditions={"target_at": NOW + timedelta(days=10), "lead_minutes": 1440},
        earliest_relevance=NOW + timedelta(days=9),
        latest_relevance=NOW + timedelta(days=12),
    )
    eligibility = ProspectiveThreadEligibilityService()
    assert not eligibility.evaluate(row, ProspectiveEvaluationContext(now=NOW)).eligible
    assert eligibility.evaluate(row, ProspectiveEvaluationContext(now=NOW + timedelta(days=9))).eligible
    expired_result = eligibility.evaluate(row, ProspectiveEvaluationContext(now=NOW + timedelta(days=13)))
    assert expired_result.expired and not expired_result.eligible
    expired = service.expire_due(db_session, user, now=NOW + timedelta(days=13))
    assert [item.id for item in expired] == [row.id]
    assert row.status == ProspectiveThreadStatus.expired.value


@pytest.mark.parametrize("action", list(AttentionAction))
def test_attention_manager_supports_entire_typed_action_space_without_side_effects(action) -> None:
    candidate = AttentionCandidate(
        requested_action=action,
        reason_code="explicit_test_evidence",
        subject="Policy candidate",
        priority=95,
        urgency=0.95,
        evidence_quality=0.9,
        confidence=0.9,
        active_task_interruption_cost=0.1,
        host_authorized_actions=(action,),
    )
    assert AttentionManager().decide(candidate).action == action


def test_attention_host_guardrails_default_to_silence_or_safe_downgrade() -> None:
    manager = AttentionManager()
    weak = AttentionCandidate(
        requested_action=AttentionAction.interrupt,
        reason_code="weak",
        subject="Weak evidence",
        evidence_quality=0.1,
        confidence=0.9,
    )
    assert manager.decide(weak).action == AttentionAction.silent
    mutation = weak.model_copy(update={
        "requested_action": AttentionAction.act_silently,
        "evidence_quality": 0.9,
        "requires_canonical_mutation": True,
    })
    assert manager.decide(mutation).reason_code == "canonical_authority_required"
    unauthorised = weak.model_copy(update={"evidence_quality": 0.9, "priority": 95, "urgency": 0.95})
    assert manager.decide(unauthorised).action == AttentionAction.mention_when_natural


def test_curiosity_policy_asks_defers_and_skips_without_diagnostic_inputs() -> None:
    policy = CuriosityPolicy()
    ask = CuriosityInputs(
        importance=1, uncertainty=1, decision_impact=1, naturalness=1,
        interruption_cost=0.05, annoyance=0.05, inferability_elsewhere=0.05,
    )
    assert policy.evaluate(ask).action == CuriosityAction.ask_now
    assert policy.evaluate(ask.model_copy(update={"interruption_cost": 0.9})).action == CuriosityAction.defer
    assert policy.evaluate(ask.model_copy(update={"inferability_elsewhere": 0.95})).action == CuriosityAction.skip
    assert policy.evaluate(ask.model_copy(update={"importance": 0.1})).action == CuriosityAction.skip
    assert {"depression", "adhd", "diagnosis", "intoxication"}.isdisjoint(CuriosityInputs.model_fields)


def test_attention_item_persists_deduplicates_and_defers(db_session) -> None:
    user = get_or_create_user(db_session)
    decision = AttentionDecision(
        action=AttentionAction.mention_when_natural,
        reason_code="future_context",
        subject="Mention this later",
        priority=60,
        urgency=0.3,
        confidence=0.8,
        evidence_quality=0.8,
        not_before=NOW + timedelta(hours=1),
        policy_version="attention-policy-v1",
    )
    service = AttentionItemService()
    first, created = service.enqueue(db_session, user, decision, deduplication_key="thread:movie")
    second, duplicate_created = service.enqueue(db_session, user, decision, deduplication_key="thread:movie")
    db_session.commit()
    assert created and not duplicate_created and first.id == second.id
    assert service.list_pending(db_session, user, now=NOW) == []
    assert [item.id for item in service.list_pending(db_session, user, now=NOW + timedelta(hours=2))] == [first.id]


def test_global_workspace_rebuilds_from_current_bounded_authoritative_state(db_session) -> None:
    user = get_or_create_user(db_session)
    workspaces = ActiveWorkspaceService()
    for index in range(MAX_WORKSPACE_REFS + 2):
        workspaces.start_workspace(
            db_session,
            user,
            workspace_type=WorkspaceType.study,
            payload=StudyWorkspacePayload(topic_ref=f"topic:{index}"),
            foreground=index == MAX_WORKSPACE_REFS + 1,
        )
    threads = OpenThreadService()
    for index in range(MAX_OPEN_THREAD_REFS + 2):
        threads.create(db_session, user, subject=f"Thread {index}", intent="Keep bounded")
    for index in range(MAX_RECENT_EVENTS + 3):
        append_event(
            db_session,
            user,
            event_type="test.meaningful",
            aggregate_type="test",
            aggregate_id=f"event-{index}",
            payload={"index": index},
            outbox=False,
        )
    prospective = ProspectiveThreadService().create(
        db_session,
        user,
        subject="Manual future thread",
        intent="Become eligible only with explicit context",
        trigger_type=ProspectiveTriggerType.manual,
        trigger_conditions={},
    )
    pending, _ = AttentionItemService().enqueue(
        db_session,
        user,
        AttentionDecision(
            action=AttentionAction.show_passively,
            reason_code="bounded_snapshot",
            subject="Pending attention",
            priority=55,
            urgency=0.2,
            confidence=0.8,
            evidence_quality=0.8,
            policy_version="attention-policy-v1",
        ),
        deduplication_key="snapshot:pending",
    )
    plan = Plan(user_id=user.id, status="active", planner_version="test", horizon_start=NOW, horizon_end=NOW + timedelta(days=1))
    db_session.add(plan)
    db_session.flush()
    block = PlanBlock(
        user_id=user.id,
        plan_id=plan.id,
        title="Canonical current block",
        starts_at=NOW - timedelta(minutes=10),
        ends_at=NOW + timedelta(minutes=20),
        duration_minutes=30,
        status="planned",
    )
    commitment = Commitment(
        user_id=user.id,
        title="Next lecture",
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=2),
        status="active",
    )
    db_session.add_all([block, commitment])
    db_session.flush()

    builder = GlobalWorkspaceBuilder()
    first = builder.build(
        db_session,
        user,
        now=NOW,
        broad_context=BroadContext.university,
        self_reported_state=ExplicitSelfReportedState(energy=0.4, availability="until 14:00"),
        manual_trigger=True,
    )
    assert len(first.active_workspaces) == MAX_WORKSPACE_REFS
    assert len(first.recent_events) == MAX_RECENT_EVENTS
    assert len(first.open_threads) == MAX_OPEN_THREAD_REFS
    assert first.foreground_workspace is not None
    assert first.current_plan_block.label == "Canonical current block"
    assert first.next_commitment.label == "Next lecture"
    assert first.self_reported_state.energy == 0.4
    assert [ref.ref_id for ref in first.pending_attention] == [pending.id]
    assert [ref.ref_id for ref in first.eligible_prospective_threads] == [prospective.id]

    block.title = "New canonical title"
    user.world_revision += 1
    db_session.flush()
    rebuilt = builder.build(db_session, user, now=NOW)
    assert rebuilt.snapshot_ref != first.snapshot_ref
    assert rebuilt.current_plan_block.label == "New canonical title"
    assert rebuilt.world_revision == first.world_revision + 1


class _ManyQuestionsContributor:
    name = "many"
    descriptor = ContributorDescriptor(
        contributor_id="many", version="1", supported_event_types=frozenset({"bounded.event"}), priority=100
    )

    def contribute(self, *, event, state) -> tuple[DecisionQuestionRequest, ...]:
        del event, state
        return tuple(DecisionQuestionRequest(question=ATTENTION_ACTION_V1) for _ in range(5))


def test_contributor_registry_activates_relevant_subset_and_enforces_bound() -> None:
    registry = DecisionContributorRegistry((*DEFAULT_COGNITIVE_CONTRIBUTORS, _ManyQuestionsContributor()))
    activation = registry.activate(CognitiveEvent(event_type="bounded.event", source="test"), max_contributors=1)
    assert [item.descriptor.contributor_id for item in activation.contributors] == ["many"]
    assert registry.activate(CognitiveEvent(event_type="unrelated.event", source="test")).contributors == ()
    workspace = registry.activate(CognitiveEvent(event_type="workspace.updated", source="domain"))
    assert [item.descriptor.contributor_id for item in workspace.contributors] == ["workspace-attention"]


def test_cognitive_cycle_enforces_per_contributor_question_bound(db_session) -> None:
    user = get_or_create_user(db_session)
    registry = DecisionContributorRegistry((_ManyQuestionsContributor(),))
    event = CognitiveEvent(
        event_type="bounded.event",
        source="test",
        occurred_at=NOW,
        metadata={"fake_selected_answer": "SILENT"},
    )
    result = CognitiveCycleRunner(_enabled_settings(), contributor_registry=registry).run(
        db_session, user, event, now=NOW
    )
    assert len(result.question_refs) == 4
    assert result.errors == ("contributor_question_bound:many",)
    assert result.attention_action == AttentionAction.silent


def test_cognitive_cycle_persists_mention_trace_audit_and_attention_without_gemini(db_session) -> None:
    user = get_or_create_user(db_session)
    event = _attention_event(
        AttentionAction.mention_when_natural,
        prospective_thread_id=None,
        deduplication_key="cycle:mention",
    )
    result = CognitiveCycleRunner(_enabled_settings()).run(db_session, user, event, now=NOW)
    assert result.status == CognitiveCycleStatus.completed
    assert result.attention_action == AttentionAction.mention_when_natural
    assert result.activated_contributors == ("attention-candidate",)
    assert result.question_refs == ("attention.action:v1",)
    assert result.attention_item_ref is not None
    item = db_session.get(AttentionItem, result.attention_item_ref)
    trace = db_session.get(CognitiveTrace, result.trace_refs[0])
    audit = db_session.scalar(select(DecisionAudit).where(DecisionAudit.trace_id == trace.id))
    assert item.source_trace_id == trace.id
    assert trace.metadata_json["activated_contributors"] == ["attention-candidate"]
    assert trace.metadata_json["attention_policy_version"] == "attention-policy-v1"
    assert audit.outcome_json["attention_action"] == "MENTION_WHEN_NATURAL"


def test_cognitive_cycle_silent_and_ask_paths_need_no_ai_gateway(db_session) -> None:
    user = get_or_create_user(db_session)
    runner = CognitiveCycleRunner(_enabled_settings())
    silent = runner.run(db_session, user, _attention_event(AttentionAction.silent), now=NOW)
    assert silent.attention_action == AttentionAction.silent
    assert silent.attention_item_ref is None
    count_after_silent = db_session.scalar(select(func.count(AttentionItem.id)))
    ask = runner.run(
        db_session,
        user,
        _attention_event(AttentionAction.ask, deduplication_key="cycle:ask"),
        now=NOW,
    )
    assert ask.attention_action == AttentionAction.ask
    assert ask.attention_item_ref is not None
    assert db_session.scalar(select(func.count(AttentionItem.id))) == count_after_silent + 1

    source = Path(CognitiveCycleRunner.__module__.replace(".", "/") + ".py")
    cycle_path = Path(__file__).resolve().parents[1] / source
    imports = {
        node.module
        for node in ast.walk(ast.parse(cycle_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    }
    assert "app.ai.gateway" not in imports


def test_cognitive_cycle_provider_failure_is_silent_and_creates_no_attention_item(db_session) -> None:
    user = get_or_create_user(db_session)
    event = _attention_event(AttentionAction.interrupt).model_copy(
        update={"metadata": {"fake_scenario": "error"}}
    )
    result = CognitiveCycleRunner(_enabled_settings()).run(db_session, user, event, now=NOW)
    assert result.status == CognitiveCycleStatus.degraded
    assert result.attention_action == AttentionAction.silent
    assert result.attention_item_ref is None


def test_disabled_cognition_preserves_existing_behavior(db_session) -> None:
    user = get_or_create_user(db_session)
    result = CognitiveCycleRunner(Settings(_env_file=None)).run(
        db_session, user, _attention_event(AttentionAction.ask), now=NOW
    )
    assert result.status == CognitiveCycleStatus.disabled
    assert result.attention_action == AttentionAction.silent
    assert db_session.scalar(select(func.count(CognitiveTrace.id))) == 0
    assert db_session.scalar(select(func.count(AttentionItem.id))) == 0


def test_v16b_runtime_never_constructs_plan_blocks_outside_planning() -> None:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for source_path in app_dir.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        if any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PlanBlock"
            for node in ast.walk(tree)
        ) and "planning" not in source_path.relative_to(app_dir).parts:
            offenders.append(str(source_path))
    assert offenders == []
