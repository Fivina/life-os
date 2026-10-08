from datetime import UTC, date, datetime, timedelta

from app.api.deps import get_or_create_user
from app.database.models import Action, Commitment, MemoryItem, PatternEvidence, PlanningAllocation, PlanningDebt
from app.planning.automation import MorningPlanner
from app.planning.constraints import PlanningConstraintResolver
from app.planning.engine import BLOCK_GENERATED_ACTION, CorePlannerV03
from app.planning.rolling import RollingPlanner
from app.planning.types import CandidateAction, PlanningContext

from .conftest import AUTH_HEADERS


BASE = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _state(client, value: int) -> None:
    response = client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"energy": value, "mental_state": value, "observed_at": iso(BASE - timedelta(minutes=15))})
    assert response.status_code == 200


def _variant(client, group: str, kind: str, minutes: int, rank: int, *, deadline: datetime | None = None) -> dict:
    response = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"variant-{group}-{kind}"},
        json={
            "title": f"Algorithms ({kind})",
            "domain": "learning",
            "level": "goal_critical",
            "estimated_minutes": minutes,
            "duration_min_minutes": minutes,
            "duration_max_minutes": minutes,
            "deadline": iso(deadline) if deadline else None,
            "candidate_group_id": group,
            "variant_type": kind,
            "variant_rank": rank,
            "mutually_exclusive": True,
            "variant_quality": rank / 5,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _generate(client, start: datetime, end: datetime) -> dict:
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    response = client.post(
        "/api/v1/plans/generate",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"plan-{start.hour}-{end.hour}"},
        json={"planning_date": start.date().isoformat(), "timezone": "UTC", "horizon_start": iso(start), "horizon_end": iso(end), "expected_world_revision": revision},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_variants_are_mutually_exclusive_and_full_wins_when_feasible(client):
    _state(client, 85)
    group = "learning:algorithms:week"
    for kind, minutes, rank in [("full", 90, 5), ("standard", 60, 4), ("reduced", 45, 3), ("minimum", 25, 2), ("activation", 10, 1)]:
        _variant(client, group, kind, minutes, rank)
    plan = _generate(client, BASE, BASE + timedelta(hours=4))
    blocks = [item for item in plan["blocks"] if item["block_type"] == BLOCK_GENERATED_ACTION and item.get("action_group_id") == group]
    assert len(blocks) == 1
    assert blocks[0]["variant_type"] == "full"
    assert blocks[0]["duration_minutes"] == 90


def test_reduced_and_activation_variants_are_selected_only_when_capacity_requires_them(client):
    group = "learning:algorithms:capacity"
    for kind, minutes, rank in [("full", 90, 5), ("reduced", 60, 3), ("minimum", 25, 2), ("activation", 10, 1)]:
        _variant(client, group, kind, minutes, rank)
    _state(client, 35)
    reduced = _generate(client, BASE, BASE + timedelta(hours=3))
    block = next(item for item in reduced["blocks"] if item.get("action_group_id") == group)
    assert block["variant_type"] == "reduced"


def test_minimum_variant_is_selected_when_reduced_work_no_longer_fits(client):
    group = "learning:algorithms:minimum"
    for kind, minutes, rank in [("full", 90, 5), ("reduced", 60, 3), ("minimum", 25, 2), ("activation", 10, 1)]:
        _variant(client, group, kind, minutes, rank)
    _state(client, 35)
    plan = _generate(client, BASE, BASE + timedelta(minutes=150))
    block = next(item for item in plan["blocks"] if item.get("action_group_id") == group)
    assert block["variant_type"] == "minimum"


def test_activation_variant_is_last_resort_and_requires_activation_context(client):
    group = "learning:algorithms:activation"
    for kind, minutes, rank in [("full", 90, 5), ("minimum", 25, 2), ("activation", 10, 1)]:
        _variant(client, group, kind, minutes, rank)
    _state(client, 35)
    plan = _generate(client, BASE, BASE + timedelta(minutes=130))
    block = next(item for item in plan["blocks"] if item.get("action_group_id") == group)
    assert block["variant_type"] == "activation"


def test_future_slot_behavior_not_generation_time_drives_score():
    candidate = CandidateAction("a", "learning", "Algorithms", "maintenance", 60, 30, 60)
    snapshot = {
        "parameters": {"routine": {"patterns": {"learning|afternoon": {"ranking_adjustment": 6, "evidence_n": 20}, "learning|evening": {"ranking_adjustment": 0, "evidence_n": 20}}}},
        "confidence": {"routine": 0.9},
        "active_model_ids": {"routine": "routine-1"},
    }
    context = PlanningContext("u", BASE.date(), "UTC", BASE, 1, BASE, BASE + timedelta(hours=14), 70, 70, candidate_actions=[candidate], personal_model_snapshot=snapshot)
    planner = CorePlannerV03()
    afternoon = planner.score_candidate(context, candidate, BASE.replace(hour=14))
    evening = planner.score_candidate(context, candidate, BASE.replace(hour=20))
    assert afternoon.score > evening.score
    assert any(item.factor == "future_slot_weekday" and "afternoon" in (item.notes or "") for item in afternoon.factors)


def test_low_confidence_is_bounded_and_invalidated_pattern_removes_routine_influence():
    candidate = CandidateAction("a", "learning", "Algorithms", "maintenance", 60, 30, 60)
    snapshot = {"parameters": {"routine": {"patterns": {"learning|afternoon": {"ranking_adjustment": 6}}}}, "confidence": {"routine": 0.1}, "active_model_ids": {}}
    base = dict(user_id="u", planning_date=BASE.date(), timezone="UTC", generated_at=BASE, generated_from_world_revision=1, horizon_start=BASE, horizon_end=BASE + timedelta(hours=12), energy=70, mental_state=70, candidate_actions=[candidate], personal_model_snapshot=snapshot)
    active = PlanningContext(**base)
    active_factor = next(item for item in CorePlannerV03().score_candidate(active, candidate, BASE.replace(hour=14)).factors if item.factor == "learned_routine_fit")
    assert 0 < active_factor.contribution <= 0.6
    corrected = PlanningContext(**base, behavior_patterns=[{"scope": {"key": "learning|afternoon"}, "status": "INVALIDATED", "confidence": 1}])
    assert not any(item.factor == "learned_routine_fit" for item in CorePlannerV03().score_candidate(corrected, candidate, BASE.replace(hour=14)).factors)


def test_pinned_planning_memory_is_typed_and_irrelevant_memory_is_ignored(db_session):
    user = get_or_create_user(db_session)
    db_session.add_all([
        MemoryItem(user_id=user.id, memory_type="preference", domain="planning", content="Monday evening is personal time.", normalized_key="monday evening personal time", confidence=1, importance=1, status="confirmed", pinned=True, user_confirmed=True, source_kind="user_explicit"),
        MemoryItem(user_id=user.id, memory_type="preference", domain="food", content="I like spicy food.", normalized_key="likes spicy food", confidence=1, importance=1, status="confirmed", pinned=True, user_confirmed=True, source_kind="user_explicit"),
    ])
    db_session.flush()
    resolved = PlanningConstraintResolver().resolve(db_session, user, planning_day=BASE.date(), timezone_name="UTC")
    assert len(resolved) == 1
    assert resolved[0].strength == "hard"
    assert resolved[0].provenance == "pinned_memory"


def test_soft_pinned_preference_can_be_violated_but_remains_explainable(client, db_session):
    _state(client, 80)
    _variant(client, "learning:soft-preference", "full", 60, 5)
    user = get_or_create_user(db_session)
    db_session.add(MemoryItem(user_id=user.id, memory_type="preference", domain="learning", content="I prefer afternoon learning.", normalized_key="prefer afternoon learning", confidence=1, importance=1, status="confirmed", pinned=True, user_confirmed=True, source_kind="user_explicit"))
    db_session.flush()
    plan = _generate(client, BASE, BASE + timedelta(hours=3))
    block = next(item for item in plan["blocks"] if item.get("action_group_id") == "learning:soft-preference")
    factor = next(item for item in block["decision_factors"] if item["factor"] == "preferred_slot")
    assert factor["contribution"] < 0
    assert "pinned_memory" in (factor["notes"] or "")


def test_hard_pinned_constraint_prevents_invalid_placement(client, db_session):
    _state(client, 80)
    _variant(client, "learning:hard-memory", "full", 60, 5)
    user = get_or_create_user(db_session)
    db_session.add(MemoryItem(user_id=user.id, memory_type="constraint", domain="planning", content="Never schedule work after 9.", normalized_key="never schedule work after 9", confidence=1, importance=1, status="confirmed", pinned=True, user_confirmed=True, source_kind="user_explicit"))
    db_session.flush()
    plan = _generate(client, BASE + timedelta(hours=2), BASE + timedelta(hours=5))
    assert not any(item.get("action_group_id") == "learning:hard-memory" for item in plan["blocks"])
    assert plan["unscheduled_actions"]


def test_hard_commitment_wins_over_behavioral_preference(client):
    _state(client, 80)
    _variant(client, "learning:fixed", "full", 60, 5)
    client.post("/api/v1/commitments", headers={**AUTH_HEADERS, "Idempotency-Key": "fixed-university"}, json={"title": "University", "level": "hard", "commitment_type": "hard", "starts_at": iso(BASE), "ends_at": iso(BASE + timedelta(hours=3)), "timezone": "UTC"})
    plan = _generate(client, BASE, BASE + timedelta(hours=6))
    generated = next(item for item in plan["blocks"] if item.get("action_group_id") == "learning:fixed")
    generated_start = datetime.fromisoformat(generated["starts_at"])
    generated_start = generated_start.replace(tzinfo=UTC) if generated_start.tzinfo is None else generated_start
    assert generated_start >= BASE + timedelta(hours=3)


def test_rolling_allocator_reports_real_shortfall_and_keeps_unscheduled_work(db_session):
    user = get_or_create_user(db_session)
    deadline = BASE + timedelta(hours=12)
    db_session.add(Action(user_id=user.id, domain="learning", title="Exam sprint", level="goal_critical", estimated_minutes=900, completed_minutes=0, deadline=deadline, status="active", candidate_group_id="exam:sprint", variant_type="full", variant_rank=5, mutually_exclusive=True))
    db_session.flush()
    result = RollingPlanner().refresh(db_session, user, start_day=BASE.date(), timezone_name="UTC")
    assert result.status == "impossible_before_deadline"
    assert result.shortfall_minutes > 0
    allocations = RollingPlanner().allocations(db_session, user, start_day=BASE.date(), end_day=BASE.date())
    assert allocations
    assert sum(item.allocated_minutes for item in allocations) < 900


def test_partial_completion_creates_residual_debt_and_miss_replans(client, db_session):
    _state(client, 70)
    _variant(client, "learning:debt", "full", 60, 5)
    plan = _generate(client, BASE, BASE + timedelta(hours=5))
    block = next(item for item in plan["blocks"] if item.get("action_group_id") == "learning:debt")
    response = client.post(f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/partial", headers=AUTH_HEADERS, json={"expected_version": block["version"], "actual_duration_minutes": 25})
    assert response.status_code == 200, response.text
    updated = next(item for item in response.json()["blocks"] if item["id"] == block["id"])
    assert updated["status"] == "partially_completed"
    assert updated["residual_minutes"] == 35
    debt = db_session.query(PlanningDebt).filter_by(source_plan_block_id=block["id"]).one()
    assert debt.residual_minutes == 35
    allocation = db_session.query(PlanningAllocation).filter_by(action_group_id="learning:debt", planning_date=BASE.date()).one()
    assert allocation.completed_minutes == 25
    assert allocation.status == "in_progress"


def test_manual_move_is_user_locked_and_survives_replan(client):
    _state(client, 75)
    _variant(client, "learning:move", "full", 60, 5)
    plan = _generate(client, BASE, BASE + timedelta(hours=8))
    block = next(item for item in plan["blocks"] if item.get("action_group_id") == "learning:move")
    moved_start = BASE + timedelta(hours=5)
    moved = client.post(f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/move", headers=AUTH_HEADERS, json={"expected_version": block["version"], "starts_at": iso(moved_start), "ends_at": iso(moved_start + timedelta(hours=1))})
    assert moved.status_code == 200, moved.text
    moved_block = next(item for item in moved.json()["blocks"] if item["id"] == block["id"])
    assert moved_block["user_locked"] is True
    replanned = client.post("/api/v1/plans/replan", headers=AUTH_HEADERS, json={"planning_date": BASE.date().isoformat(), "reason": "USER_REQUESTED", "force": True, "now": iso(BASE + timedelta(hours=1))}).json()
    expected_start = datetime.fromisoformat(moved_block["starts_at"].replace("Z", "+00:00")).replace(tzinfo=None)
    assert any(item.get("user_locked") and datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00")).replace(tzinfo=None) == expected_start for item in replanned["plan"]["blocks"])


def test_morning_generation_is_user_date_scoped_and_idempotent(db_session):
    user = get_or_create_user(db_session)
    db_session.add(Action(user_id=user.id, domain="personal", title="Morning action", level="maintenance", estimated_minutes=30, completed_minutes=0, status="active"))
    db_session.flush()
    first, created_first = MorningPlanner().ensure(db_session, user, timezone_name="UTC", now=BASE)
    second, created_second = MorningPlanner().ensure(db_session, user, timezone_name="UTC", now=BASE)
    assert created_first is True
    assert created_second is False
    assert first.id == second.id


def test_morning_worker_waits_until_configured_hour(db_session):
    user = get_or_create_user(db_session)
    db_session.add(Action(user_id=user.id, domain="personal", title="Later morning action", level="maintenance", estimated_minutes=30, completed_minutes=0, status="active"))
    db_session.flush()
    assert MorningPlanner().run_due(db_session, timezone_name="UTC", now=BASE.replace(hour=2)) == 0
    assert MorningPlanner().run_due(db_session, timezone_name="UTC", now=BASE) == 1


def test_planner_runs_with_ai_disabled_by_construction(client, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    _state(client, 70)
    _variant(client, "learning:no-ai", "minimum", 25, 2)
    plan = _generate(client, BASE, BASE + timedelta(hours=3))
    assert any(item.get("action_group_id") == "learning:no-ai" for item in plan["blocks"])
