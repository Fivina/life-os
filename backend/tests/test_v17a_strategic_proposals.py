from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.database.models import (
    Action,
    AttentionItem,
    CognitiveTrace,
    DecisionAudit,
    Exam,
    Plan,
    PlanBlock,
    PlanProposal,
    StudyRequirement,
    TrainingExample,
)
from app.strategy.intervention import InterventionEngine
from app.strategy.monitor import StrategicMonitor
from app.strategy.schemas import (
    AttentionAction,
    AuthorityLevel,
    DataCompleteness,
    DeviationSeverity,
    DeviationType,
    ExamTrajectorySnapshot,
    ProposalModificationRequest,
    ProposalStatus,
    Recoverability,
    StrategicDeviation,
)
from app.strategy.service import PlanProposalService
from tests.conftest import AUTH_HEADERS


def _stack(db, *, now: datetime | None = None):
    current = now or datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0)
    user = get_or_create_user(db)
    exam = Exam(
        user_id=user.id,
        title="Algorithms Final",
        exam_at=current + timedelta(days=14),
        target_preparation_minutes=600,
        target_quality_adjusted_minutes=600,
        importance="goal_critical",
        status="active",
    )
    donor = Exam(
        user_id=user.id,
        title="Economics Final",
        exam_at=current + timedelta(days=45),
        target_preparation_minutes=300,
        target_quality_adjusted_minutes=300,
        importance="normal",
        status="active",
    )
    db.add_all([exam, donor])
    db.flush()
    db.add_all([
        StudyRequirement(user_id=user.id, exam_id=exam.id, title="Graphs", estimated_required_minutes=600),
        StudyRequirement(user_id=user.id, exam_id=donor.id, title="Review", estimated_required_minutes=300),
    ])
    target_action = Action(
        user_id=user.id, domain="learning", title="Algorithms: Graphs", level="goal_critical", status="active",
        estimated_minutes=60, duration_min_minutes=25, duration_max_minutes=180, deadline=exam.exam_at,
        source_entity_type="exam", source_entity_id=exam.id, candidate_group_id=f"exam:{exam.id}",
        variant_type="standard", variant_rank=5, mutually_exclusive=True,
        metadata_json={"trajectory_value": 65, "neglect_cost": 35, "splittable": True},
    )
    donor_action = Action(
        user_id=user.id, domain="learning", title="Economics: Review", level="maintenance", status="active",
        estimated_minutes=120, duration_min_minutes=30, duration_max_minutes=120, deadline=donor.exam_at,
        source_entity_type="exam", source_entity_id=donor.id, candidate_group_id=f"exam:{donor.id}",
        variant_type="standard", variant_rank=4, mutually_exclusive=True,
        metadata_json={"trajectory_value": 20, "neglect_cost": 8, "splittable": True},
    )
    workout_action = Action(
        user_id=user.id, domain="fitness", title="Protected workout", level="maintenance", status="active",
        estimated_minutes=60, duration_min_minutes=60, duration_max_minutes=60,
        metadata_json={"trajectory_value": 30},
    )
    db.add_all([target_action, donor_action, workout_action])
    db.flush()
    plan_day = datetime.now().astimezone().date()
    horizon_start = datetime.combine(plan_day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=8)
    plan = Plan(
        user_id=user.id, planner_version="v1.5-domain-intelligence", generated_from_world_revision=user.world_revision,
        status="current", planning_day=plan_day, horizon_start=horizon_start, horizon_end=horizon_start + timedelta(hours=14),
        generated_at=current, summary_metrics={"planning_load": "medium"}, decision_factors={}, personal_model_snapshot={},
    )
    db.add(plan)
    db.flush()
    target_block = PlanBlock(
        user_id=user.id, plan_id=plan.id, action_id=target_action.id, source_type="action", source_id=target_action.id,
        domain="learning", title=target_action.title, starts_at=horizon_start + timedelta(hours=1),
        ends_at=horizon_start + timedelta(hours=1, minutes=30), duration_minutes=30, block_type="generated_action",
        commitment_level="goal_critical", movable=True, status="planned", source="planner",
    )
    donor_block = PlanBlock(
        user_id=user.id, plan_id=plan.id, action_id=donor_action.id, source_type="action", source_id=donor_action.id,
        domain="learning", title=donor_action.title, starts_at=horizon_start + timedelta(hours=2),
        ends_at=horizon_start + timedelta(hours=4), duration_minutes=120, block_type="generated_action",
        commitment_level="maintenance", movable=True, status="planned", source="planner",
    )
    protected = PlanBlock(
        user_id=user.id, plan_id=plan.id, action_id=workout_action.id, source_type="action", source_id=workout_action.id,
        domain="fitness", title=workout_action.title, starts_at=horizon_start + timedelta(hours=5),
        ends_at=horizon_start + timedelta(hours=6), duration_minutes=60, block_type="generated_action",
        commitment_level="maintenance", movable=False, status="planned", source="planner", user_locked=True,
    )
    db.add_all([target_block, donor_block, protected])
    db.commit()
    return user, exam, donor, plan, protected, current


def _service(*, decisions: bool = False) -> PlanProposalService:
    settings = Settings(
        _env_file=None,
        decision_infra_enabled=decisions,
        decision_provider="fake",
        decision_routing_mode="FAKE",
        decision_tracing_enabled=True,
    )
    return PlanProposalService(settings)


def test_deterministic_trajectory_reports_exact_unresolved_shortfall(db_session, monkeypatch):
    user, exam, _donor, _plan, _protected, now = _stack(db_session)
    monkeypatch.setattr("app.strategy.monitor.future_capacity_minutes", lambda *args, **kwargs: (540, {"fixture": True}))
    snapshot = StrategicMonitor().assess_exam(db_session, user, exam, now=now)

    assert snapshot.total_workload_minutes == 600
    assert snapshot.remaining_workload_minutes == 600
    assert snapshot.planned_future_minutes == 30
    assert snapshot.future_allocated_minutes == 210
    assert snapshot.future_capacity_minutes == 330
    assert snapshot.projected_shortfall_minutes == 240
    assert snapshot.calculation_version == "trajectory-calculation-v1"
    assert snapshot.completeness in {DataCompleteness.partial, DataCompleteness.complete}


def test_missing_deadline_is_insufficient_not_zero(db_session):
    user, exam, *_ = _stack(db_session)
    exam.exam_at = None
    exam.exam_date = None
    db_session.flush()
    snapshot = StrategicMonitor().assess_exam(db_session, user, exam)
    assert snapshot.days_remaining is None
    assert snapshot.future_capacity_minutes is None
    assert snapshot.completeness == DataCompleteness.insufficient
    assert StrategicMonitor().deviation(snapshot) is None


def test_healthy_trajectory_is_silent():
    snapshot = ExamTrajectorySnapshot(
        exam_id="exam", exam_title="Healthy", as_of=datetime.now(UTC), exam_at=datetime.now(UTC) + timedelta(days=20),
        days_remaining=20, total_workload_minutes=300, workload_source="study_requirements", completed_effective_minutes=300,
        remaining_workload_minutes=0, planned_future_minutes=0, recent_actual_effective_minutes=180, recent_window_days=14,
        actual_weekly_pace_minutes=90, required_weekly_pace_minutes=0, pace_gap_minutes=0, future_capacity_minutes=600,
        future_allocated_minutes=0, capacity_shortfall_minutes=0, projected_shortfall_minutes=0, planning_debt_minutes=0,
        readiness_score=100, readiness_source="effective_workload_completion", buffer_minutes=600,
        completeness=DataCompleteness.complete, completeness_score=1, source_world_revision=1,
    )
    decision = InterventionEngine().decide(snapshot, None)
    assert decision.authority_level == AuthorityLevel.observe
    assert decision.attention_action == AttentionAction.silent


@pytest.mark.parametrize(
    ("severity", "recoverability", "days_remaining", "authority", "action"),
    [
        (DeviationSeverity.moderate, Recoverability.existing_capacity, 14, AuthorityLevel.prepare_proposal, AttentionAction.mention_when_natural),
        (DeviationSeverity.high, Recoverability.meaningful_tradeoff, 7, AuthorityLevel.prepare_proposal, AttentionAction.propose),
        (DeviationSeverity.critical, Recoverability.meaningful_tradeoff, 2, AuthorityLevel.ask_or_discuss_tradeoff, AttentionAction.ask),
        (DeviationSeverity.critical, Recoverability.unrecoverable, 1, AuthorityLevel.urgent_attention, AttentionAction.interrupt),
    ],
)
def test_intervention_policy_maps_evidence_to_bounded_attention(
    severity, recoverability, days_remaining, authority, action
):
    snapshot = ExamTrajectorySnapshot(
        exam_id="exam", exam_title="At risk", as_of=datetime.now(UTC),
        exam_at=datetime.now(UTC) + timedelta(days=days_remaining), days_remaining=days_remaining,
        total_workload_minutes=600, workload_source="study_requirements", completed_effective_minutes=60,
        remaining_workload_minutes=540, planned_future_minutes=60, recent_actual_effective_minutes=30,
        recent_window_days=14, actual_weekly_pace_minutes=15, required_weekly_pace_minutes=270,
        pace_gap_minutes=255, future_capacity_minutes=120, future_allocated_minutes=180,
        capacity_shortfall_minutes=360, projected_shortfall_minutes=360, planning_debt_minutes=60,
        readiness_score=10, readiness_source="effective_workload_completion", buffer_minutes=0,
        completeness=DataCompleteness.complete, completeness_score=0.9, source_world_revision=1,
    )
    deviation = StrategicDeviation(
        exam_id="exam", deviation_types=(DeviationType.capacity_shortfall,), severity=severity,
        recoverability=recoverability, magnitude_minutes=360, days_remaining=days_remaining,
        evidence_quality=0.9, reason_codes=("remaining_work_exceeds_capacity",), fingerprint="a" * 64,
    )
    decision = InterventionEngine().decide(snapshot, deviation, provider_judgment="SUPPORT_HOST_POLICY")
    assert decision.authority_level == authority
    assert decision.attention_action == action


def test_proposal_simulation_is_non_committing_and_preserves_protected_blocks(db_session):
    user, exam, _donor, plan, protected, now = _stack(db_session)
    before = [(row.id, row.starts_at.replace(tzinfo=None), row.ends_at.replace(tzinfo=None), row.duration_minutes, row.status) for row in plan.blocks]
    result = _service().evaluate_exam(db_session, user, exam.id, now=now)
    db_session.commit()

    assert result.proposal is not None
    assert result.proposal.status == ProposalStatus.draft
    assert result.proposal.expected_effects["protected_blocks_changed"] == 0
    db_session.refresh(plan)
    after = [(row.id, row.starts_at, row.ends_at, row.duration_minutes, row.status) for row in plan.blocks]
    assert after == before
    assert any(
        item["action_id"] == protected.action_id
        and datetime.fromisoformat(item["starts_at"]).replace(tzinfo=None) == protected.starts_at.replace(tzinfo=None)
        for item in result.proposal.candidate_plan["blocks"]
    )
    assert db_session.scalar(select(AttentionItem).where(AttentionItem.user_id == user.id)) is not None


def test_proposal_survives_fresh_session_and_deduplicates(db_session):
    user, exam, *_rest, now = _stack(db_session)
    first = _service().evaluate_exam(db_session, user, exam.id, now=now)
    db_session.commit()
    proposal_id = first.proposal.id
    Session = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    with Session() as fresh:
        fresh_user = fresh.get(type(user), user.id)
        second = _service().evaluate_exam(fresh, fresh_user, exam.id, now=now)
        restored = _service().get(fresh, fresh_user, proposal_id)
        assert restored.candidate_plan_json["simulation_version"] == "planner-strategic-simulation-v1"
        assert second.proposal.id == proposal_id
        assert second.deduplicated is True


def test_accept_applies_through_planner_and_records_contextual_learning(db_session):
    user, exam, _donor, old_plan, protected, now = _stack(db_session)
    service = _service()
    proposal = service.evaluate_exam(db_session, user, exam.id, now=now).proposal
    db_session.commit()
    accepted = service.accept(db_session, user, proposal.id)
    db_session.commit()

    assert accepted.status == ProposalStatus.accepted.value
    assert accepted.applied_plan_id is not None
    db_session.refresh(old_plan)
    assert old_plan.status == "superseded"
    new_plan = db_session.get(Plan, accepted.applied_plan_id)
    assert new_plan.status == "current"
    assert any(block.action_id == protected.action_id and block.starts_at == protected.starts_at for block in new_plan.blocks)
    evidence = db_session.scalar(select(TrainingExample).where(TrainingExample.source_entity_id == proposal.id))
    assert evidence.label_json["proposal_choice"] == "ACCEPT"
    assert evidence.provenance_json["does_not_imply_universal_preference"] is True


def test_stale_or_expired_proposal_cannot_apply(db_session):
    user, exam, _donor, plan, _protected, now = _stack(db_session)
    service = _service()
    proposal = service.evaluate_exam(db_session, user, exam.id, now=now).proposal
    db_session.commit()
    exam.version += 1
    db_session.commit()
    with pytest.raises(ValueError, match="stale"):
        service.accept(db_session, user, proposal.id)
    db_session.rollback()
    assert db_session.get(Plan, plan.id).status == "current"

    row = db_session.get(PlanProposal, proposal.id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    with pytest.raises(ValueError, match="expired"):
        service.accept(db_session, user, proposal.id)


def test_modify_versions_proposal_and_reject_learns_without_plan_change(db_session):
    user, exam, _donor, plan, _protected, now = _stack(db_session)
    service = _service()
    original = service.evaluate_exam(db_session, user, exam.id, now=now).proposal
    db_session.commit()
    replacement = service.modify(db_session, user, original.id, ProposalModificationRequest(requested_target_minutes=90))
    db_session.commit()
    assert db_session.get(PlanProposal, original.id).status == ProposalStatus.modified.value
    assert replacement.parent_proposal_id == original.id
    assert replacement.modification_json["requested_target_minutes"] == 90
    service.reject(db_session, user, replacement.id)
    db_session.commit()
    assert db_session.get(Plan, plan.id).status == "current"
    choices = {row.label_json["proposal_choice"] for row in db_session.scalars(select(TrainingExample)).all()}
    assert choices == {"MODIFY", "REJECT"}


def test_decision_gateway_trace_and_outcome_audit_are_linked(db_session):
    user, exam, *_rest, now = _stack(db_session)
    service = _service(decisions=True)
    proposal = service.evaluate_exam(db_session, user, exam.id, now=now).proposal
    db_session.commit()
    assert proposal.source_trace_id is not None
    trace = db_session.get(CognitiveTrace, proposal.source_trace_id)
    assert trace.question_id == "strategy.intervention_needed"
    assert trace.metadata_json["strategic_path"]["calculation_version"] == "trajectory-calculation-v1"
    service.reject(db_session, user, proposal.id)
    db_session.commit()
    audit = db_session.scalar(select(DecisionAudit).where(DecisionAudit.trace_id == trace.id))
    assert audit.audit_type == "proposal_rejected"


def test_provider_failure_uses_deterministic_strategy_fallback(db_session):
    class FailingGateway:
        def evaluate(self, *args, **kwargs):
            from app.decision.errors import DecisionProviderUnavailable

            raise DecisionProviderUnavailable("fixture unavailable")

    user, exam, *_rest, now = _stack(db_session)
    settings = Settings(_env_file=None, decision_infra_enabled=True, decision_provider="fake")
    result = PlanProposalService(settings, gateway=FailingGateway()).evaluate_exam(db_session, user, exam.id, now=now)
    assert result.proposal is not None
    assert result.proposal.source_trace_id is None
    assert result.intervention.authority_level >= AuthorityLevel.prepare_proposal


def test_authenticated_proposal_api_and_no_silent_strategy_change(client, db_session):
    user, exam, _donor, plan, _protected, _now = _stack(db_session)
    assert client.get("/api/v1/strategy/proposals").status_code == 401
    response = client.post(f"/api/v1/strategy/exams/{exam.id}/evaluate", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal"]["current_plan_id"] == plan.id
    assert db_session.get(Plan, plan.id).status == "current"
    listed = client.get("/api/v1/strategy/proposals", headers=AUTH_HEADERS).json()
    assert listed[0]["id"] == payload["proposal"]["id"]


def test_only_planning_runtime_constructs_plan_blocks_after_v17a():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    for source_path in app_dir.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        constructs = any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PlanBlock"
            for node in ast.walk(tree)
        )
        if constructs and "planning" not in source_path.relative_to(app_dir).parts:
            offenders.append(str(source_path))
    assert offenders == []
