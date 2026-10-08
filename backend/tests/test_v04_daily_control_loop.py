from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models import Action, Event, OutboxEvent, Plan, PlanBlock
from app.planning.engine import BLOCK_GENERATED_ACTION

AUTH_HEADERS = {"Authorization": "Bearer dev-local-token"}
BASE = datetime(2026, 9, 16, 8, 0, tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def setup_day(client, *, energy: int = 72, mental_state: int = 70, action_minutes: int = 120) -> dict:
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"v04-state-{energy}-{mental_state}-{action_minutes}"},
        json={"energy": energy, "mental_state": mental_state, "observed_at": iso(BASE - timedelta(minutes=30))},
    )
    commitment = client.post(
        "/api/v1/commitments",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"v04-university-{energy}-{mental_state}-{action_minutes}"},
        json={
            "title": "University",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(BASE + timedelta(hours=3)),
            "ends_at": iso(BASE + timedelta(hours=8)),
            "timezone": "UTC",
        },
    ).json()
    study = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"v04-study-{energy}-{mental_state}-{action_minutes}"},
        json={
            "title": "Study Macroeconomics",
            "domain": "learning",
            "level": "goal_critical",
            "estimated_minutes": action_minutes,
            "duration_min_minutes": 25,
            "deadline": iso(BASE + timedelta(days=1, hours=12)),
        },
    ).json()
    optional = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"v04-optional-{energy}-{mental_state}-{action_minutes}"},
        json={
            "title": "Read optional article",
            "domain": "learning",
            "level": "optional",
            "estimated_minutes": 60,
            "duration_min_minutes": 25,
        },
    ).json()
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    plan = client.post(
        "/api/v1/plans/generate",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"v04-plan-{energy}-{mental_state}-{action_minutes}"},
        json={
            "planning_date": BASE.date().isoformat(),
            "timezone": "UTC",
            "horizon_start": iso(BASE),
            "horizon_end": iso(BASE + timedelta(hours=14)),
            "expected_world_revision": revision,
        },
    ).json()
    return {"commitment": commitment, "study": study, "optional": optional, "plan": plan}


def generated_block(plan: dict, title: str = "Study Macroeconomics") -> dict:
    return next(block for block in plan["blocks"] if block["block_type"] == BLOCK_GENERATED_ACTION and block["title"] == title)


def test_start_and_complete_partial_block_records_execution_without_completing_action(client, db_session):
    setup = setup_day(client, energy=60, mental_state=65, action_minutes=120)
    block = generated_block(setup["plan"])

    started = client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/start",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "occurred_at": iso(BASE + timedelta(minutes=5))},
    ).json()
    started_block = generated_block(started)
    assert started_block["status"] == "in_progress"
    assert started_block["started_at"] is not None

    completed = client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={
            "expected_version": started_block["version"],
            "actual_duration_minutes": started_block["duration_minutes"],
            "occurred_at": iso(BASE + timedelta(minutes=95)),
        },
    ).json()

    completed_block = generated_block(completed)
    action = db_session.query(Action).filter(Action.id == setup["study"]["id"]).one()
    assert completed_block["status"] == "completed"
    assert completed_block["finished_at"] is not None
    assert completed_block["actual_duration_minutes"] == started_block["duration_minutes"]
    assert action.completed_minutes == started_block["duration_minutes"]
    assert action.status == "active"
    assert db_session.query(Event).filter(Event.event_type == "plan.block.started").count() == 1
    assert db_session.query(Event).filter(Event.event_type == "plan.block.completed").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "plan.block.completed").count() == 1


def test_full_final_block_can_complete_source_action(client, db_session):
    setup = setup_day(client, energy=75, mental_state=75, action_minutes=30)
    block = generated_block(setup["plan"])

    client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "actual_duration_minutes": 30, "occurred_at": iso(BASE + timedelta(minutes=40))},
    )

    action = db_session.query(Action).filter(Action.id == setup["study"]["id"]).one()
    assert action.status == "completed"
    assert action.completed_minutes == 30


def test_skip_leaves_action_active_and_does_not_clone_backlog(client, db_session):
    setup = setup_day(client)
    block = generated_block(setup["plan"])

    skipped = client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/skip",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "reason": "activation_difficulty", "occurred_at": iso(BASE + timedelta(minutes=10))},
    ).json()

    assert generated_block(skipped)["status"] == "skipped"
    assert db_session.query(Action).filter(Action.title == "Study Macroeconomics").count() == 1
    assert db_session.query(Action).filter(Action.id == setup["study"]["id"]).one().status == "active"
    assert db_session.query(Event).filter(Event.event_type == "plan.block.skipped").count() == 1


def test_invalid_execution_transition_rejected(client):
    setup = setup_day(client)
    block = generated_block(setup["plan"])
    client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "occurred_at": iso(BASE + timedelta(minutes=30))},
    )

    response = client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/start",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"] + 1, "occurred_at": iso(BASE + timedelta(minutes=35))},
    )
    assert response.status_code == 409


def test_small_state_change_keeps_plan_stable(client):
    setup = setup_day(client, energy=70, mental_state=70)
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v04-small-state"},
        json={"energy": 66, "mental_state": 68, "observed_at": iso(BASE + timedelta(minutes=15))},
    )

    response = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE + timedelta(minutes=20))},
    ).json()

    assert response["control_status"] == "kept"
    assert response["plan"]["id"] == setup["plan"]["id"]
    assert response["plan_diff"]["kept_block_ids"]


def test_material_state_change_replans_with_lineage_and_diff(client, db_session):
    setup = setup_day(client, energy=75, mental_state=75)
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v04-large-state-drop"},
        json={"energy": 32, "mental_state": 38, "observed_at": iso(BASE + timedelta(minutes=20))},
    )

    response = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE + timedelta(minutes=25))},
    ).json()

    assert response["control_status"] == "replanned"
    assert response["replan_reason"] in {"STATE_MATERIAL_CHANGE", "CAPACITY_BAND_CHANGED"}
    assert response["plan"]["previous_plan_id"] == setup["plan"]["id"]
    assert response["plan"]["summary_metrics"]["flexible_work_minutes"] < setup["plan"]["summary_metrics"]["flexible_work_minutes"]
    assert response["plan"]["summary_metrics"]["slack_minutes"] > setup["plan"]["summary_metrics"]["slack_minutes"]
    assert response["plan_diff"]["previous_plan_id"] == setup["plan"]["id"]
    assert db_session.query(Plan).filter(Plan.status == "current").count() == 1
    assert db_session.query(Plan).filter(Plan.status == "superseded").count() == 1


def test_recent_state_replan_cooldown_prevents_repeated_churn(client):
    setup_day(client, energy=75, mental_state=75)
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v04-drop-once"},
        json={"energy": 32, "mental_state": 38, "observed_at": iso(BASE + timedelta(minutes=20))},
    )
    first = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE + timedelta(minutes=25))},
    ).json()
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v04-drop-twice"},
        json={"energy": 20, "mental_state": 25, "observed_at": iso(BASE + timedelta(minutes=28))},
    )

    second = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE + timedelta(minutes=30))},
    ).json()

    assert first["control_status"] == "replanned"
    assert second["control_status"] == "update_suggested"
    assert second["replan_reason"] == "STATE_REPLAN_COOLDOWN"


def test_evaluate_marks_overdue_block_missed_without_cloning_action(client, db_session):
    setup = setup_day(client, energy=60, mental_state=65)

    response = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE + timedelta(hours=10))},
    ).json()

    missed_blocks = [block for block in response["plan"]["blocks"] if block["status"] == "missed"]
    assert missed_blocks
    assert db_session.query(Action).filter(Action.id == setup["study"]["id"]).one().status == "active"
    assert db_session.query(Action).filter(Action.title == "Study Macroeconomics").count() == 1
    assert db_session.query(Event).filter(Event.event_type == "plan.block.missed").count() >= 1


def test_manual_replan_bypasses_cooldown_and_preserves_completed_block(client, db_session):
    setup = setup_day(client, energy=75, mental_state=75)
    block = generated_block(setup["plan"])
    client.post(
        f"/api/v1/plans/{setup['plan']['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "actual_duration_minutes": 30, "occurred_at": iso(BASE + timedelta(minutes=30))},
    )

    response = client.post(
        "/api/v1/plans/replan",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "reason": "USER_REQUESTED", "force": True, "now": iso(BASE + timedelta(minutes=35))},
    ).json()

    assert response["replan_mode"] == "FULL_REPLAN"
    assert response["plan"]["previous_plan_id"] == setup["plan"]["id"]
    assert any(block["status"] == "completed" for block in response["plan"]["blocks"])
    assert db_session.query(Plan).filter(Plan.status == "current").count() == 1


def test_new_hard_commitment_conflict_triggers_local_repair(client):
    setup = setup_day(client, energy=75, mental_state=75)
    study_block = generated_block(setup["plan"])
    starts_at = datetime.fromisoformat(study_block["starts_at"])
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    client.post(
        "/api/v1/commitments",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v04-new-hard-conflict"},
        json={
            "title": "Doctor",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(starts_at + timedelta(minutes=15)),
            "ends_at": iso(starts_at + timedelta(minutes=45)),
            "timezone": "UTC",
        },
    )

    response = client.post(
        "/api/v1/day/evaluate",
        headers=AUTH_HEADERS,
        json={"planning_date": BASE.date().isoformat(), "now": iso(BASE)},
    ).json()

    assert response["control_status"] == "repaired"
    assert response["replan_reason"] == "HARD_CONFLICT"
    assert response["plan"]["previous_plan_id"] == setup["plan"]["id"]
    assert any(block["title"] == "Doctor" and block["block_type"] == "hard_commitment" for block in response["plan"]["blocks"])
