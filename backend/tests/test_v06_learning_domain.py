from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models import Action, Event, OutboxEvent, PlanBlock, StudySession
from tests.conftest import AUTH_HEADERS

BASE = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def create_learning_stack(client, *, target_hours: int = 200, exam_days: int = 90) -> dict:
    course = client.post("/api/v1/learning/courses", headers=AUTH_HEADERS, json={"name": "Macroeconomics", "code": "MACRO"}).json()
    exam = client.post(
        "/api/v1/learning/exams",
        headers=AUTH_HEADERS,
        json={
            "course_id": course["id"],
            "title": "Macroeconomics Final",
            "exam_at": iso(BASE + timedelta(days=exam_days, hours=1)),
            "target_preparation_minutes": target_hours * 60,
            "importance": "goal_critical",
        },
    ).json()
    national = client.post(
        f"/api/v1/learning/exams/{exam['id']}/topics",
        headers=AUTH_HEADERS,
        json={"title": "National Accounting", "order_index": 0, "importance_weight": 1.2, "estimated_required_minutes": 240},
    ).json()
    islm = client.post(
        f"/api/v1/learning/exams/{exam['id']}/topics",
        headers=AUTH_HEADERS,
        json={
            "title": "IS-LM",
            "order_index": 1,
            "importance_weight": 1.5,
            "estimated_required_minutes": 360,
            "prerequisite_topic_id": national["id"],
        },
    ).json()
    return {"course": course, "exam": exam, "national": national, "islm": islm}


def test_course_exam_topic_management_and_stale_update(client):
    setup = create_learning_stack(client)

    courses = client.get("/api/v1/learning/courses", headers=AUTH_HEADERS).json()
    exams = client.get("/api/v1/learning/exams", headers=AUTH_HEADERS).json()
    topics = client.get(f"/api/v1/learning/exams/{setup['exam']['id']}/topics", headers=AUTH_HEADERS).json()

    assert courses[0]["name"] == "Macroeconomics"
    assert exams[0]["target_preparation_minutes"] == 12000
    assert exams[0]["trajectory"]["strategy_version"] == "learning-trajectory-v1"
    assert topics[1]["prerequisite_topic_id"] == setup["national"]["id"]

    ok = client.patch(
        f"/api/v1/learning/courses/{setup['course']['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": setup["course"]["version"], "name": "Macroeconomics II"},
    )
    assert ok.status_code == 200
    conflict = client.patch(
        f"/api/v1/learning/courses/{setup['course']['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": setup["course"]["version"], "name": "stale"},
    )
    assert conflict.status_code == 409

    invalid = client.patch(
        f"/api/v1/learning/topics/{setup['national']['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": setup["national"]["version"], "prerequisite_topic_id": setup["national"]["id"]},
    )
    assert invalid.status_code == 422


def test_quality_adjusted_study_session_updates_trajectory_and_events(client, db_session):
    setup = create_learning_stack(client)
    logged = client.post(
        "/api/v1/learning/study-sessions",
        headers={**AUTH_HEADERS, "Idempotency-Key": "study-quality-4"},
        json={
            "exam_id": setup["exam"]["id"],
            "topic_id": setup["national"]["id"],
            "duration_minutes": 60,
            "quality_rating": 4,
            "occurred_at": iso(BASE),
        },
    ).json()
    retry = client.post(
        "/api/v1/learning/study-sessions",
        headers={**AUTH_HEADERS, "Idempotency-Key": "study-quality-4"},
        json={"exam_id": setup["exam"]["id"], "duration_minutes": 60, "quality_rating": 4},
    ).json()

    trajectory = client.get(f"/api/v1/learning/exams/{setup['exam']['id']}/trajectory", headers=AUTH_HEADERS).json()

    assert retry["id"] == logged["id"]
    assert logged["duration_minutes"] == 60
    assert logged["quality_adjusted_minutes"] == 66
    assert trajectory["raw_completed_minutes"] == 60
    assert trajectory["quality_adjusted_completed_minutes"] == 66
    assert trajectory["remaining_quality_adjusted_minutes"] == 12000 - 66
    assert trajectory["readiness_score"] > 0
    assert db_session.query(Event).filter(Event.event_type == "learning.study_session.completed").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "learning.study_session.completed").count() == 1


def test_trajectory_risk_bands_and_infeasibility_are_explicit(client):
    healthy = create_learning_stack(client, target_hours=200, exam_days=140)
    for index in range(100):
        client.post(
            "/api/v1/learning/study-sessions",
            headers={**AUTH_HEADERS, "Idempotency-Key": f"healthy-{index}"},
            json={"exam_id": healthy["exam"]["id"], "duration_minutes": 60, "quality_rating": 3, "occurred_at": iso(BASE - timedelta(days=index))},
        )
    healthy_trajectory = client.get(f"/api/v1/learning/exams/{healthy['exam']['id']}/trajectory", headers=AUTH_HEADERS).json()
    assert healthy_trajectory["feasible"] is True
    assert healthy_trajectory["risk"] in {"low", "moderate"}

    pressure = create_learning_stack(client, target_hours=200, exam_days=18)
    for index in range(40):
        client.post(
            "/api/v1/learning/study-sessions",
            headers={**AUTH_HEADERS, "Idempotency-Key": f"pressure-{index}"},
            json={"exam_id": pressure["exam"]["id"], "duration_minutes": 60, "quality_rating": 3},
        )
    pressure_trajectory = client.get(f"/api/v1/learning/exams/{pressure['exam']['id']}/trajectory", headers=AUTH_HEADERS).json()
    assert pressure_trajectory["risk"] in {"high", "critical", "infeasible"}
    assert pressure_trajectory["required_daily_minutes"] > healthy_trajectory["required_daily_minutes"]

    infeasible = create_learning_stack(client, target_hours=120, exam_days=3)
    infeasible_trajectory = client.get(f"/api/v1/learning/exams/{infeasible['exam']['id']}/trajectory", headers=AUTH_HEADERS).json()
    assert infeasible_trajectory["feasible"] is False
    assert infeasible_trajectory["risk"] == "infeasible"
    assert infeasible_trajectory["shortfall_minutes"] > 0


def test_candidates_respect_prerequisites_and_sync_to_actions(client, db_session):
    setup = create_learning_stack(client, target_hours=200, exam_days=20)
    candidates = client.get("/api/v1/learning/candidates", headers=AUTH_HEADERS).json()

    assert {candidate["variant"] for candidate in candidates} >= {"full", "standard", "reduced", "minimum"}
    assert all(candidate["topic_id"] == setup["national"]["id"] for candidate in candidates)

    synced = client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS).json()
    assert len(synced) == len(candidates)
    assert db_session.query(Action).filter(Action.domain == "learning").count() == len(candidates)
    assert all(action["metadata_json"]["exam_id"] == setup["exam"]["id"] for action in synced)


def test_planner_arbitrates_learning_with_fitness_without_direct_planblock_write(client, db_session):
    setup = create_learning_stack(client, target_hours=200, exam_days=12)
    client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS)
    client.post("/api/v1/fitness/programs", headers=AUTH_HEADERS, json={"name": "Base", "active": True})
    program = client.get("/api/v1/fitness/programs", headers=AUTH_HEADERS).json()[0]
    template = client.post(
        "/api/v1/fitness/templates",
        headers=AUTH_HEADERS,
        json={"program_id": program["id"], "name": "Strength", "estimated_duration_minutes": 75},
    ).json()
    exercise = client.post("/api/v1/fitness/exercises", headers=AUTH_HEADERS, json={"name": "Squat"}).json()
    client.post(f"/api/v1/fitness/templates/{template['id']}/exercises", headers=AUTH_HEADERS, json={"exercise_id": exercise["id"]})
    client.post("/api/v1/fitness/candidates/sync-actions", headers=AUTH_HEADERS)
    client.post(
        "/api/v1/state/observations",
        headers=AUTH_HEADERS,
        json={"energy": 35, "mental_state": 35, "observed_at": iso(BASE - timedelta(minutes=30))},
    )
    client.post(
        "/api/v1/commitments",
        headers=AUTH_HEADERS,
        json={
            "title": "Seminar",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(BASE + timedelta(hours=3)),
            "ends_at": iso(BASE + timedelta(hours=8)),
            "timezone": "UTC",
        },
    )
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    plan = client.post(
        "/api/v1/plans/generate",
        headers=AUTH_HEADERS,
        json={
            "planning_date": BASE.date().isoformat(),
            "timezone": "UTC",
            "horizon_start": iso(BASE),
            "horizon_end": iso(BASE + timedelta(hours=14)),
            "expected_world_revision": revision,
        },
    ).json()

    learning_blocks = [block for block in plan["blocks"] if block["domain"] == "learning"]
    assert learning_blocks
    assert learning_blocks[0]["source_type"] == "action"
    assert learning_blocks[0]["duration_minutes"] <= 45
    assert db_session.query(PlanBlock).filter(PlanBlock.domain == "learning", PlanBlock.source_type != "action").count() == 0
    assert db_session.query(Action).filter(Action.domain == "fitness").count() > 0
    assert setup["exam"]["id"]


def test_planblock_completion_creates_one_study_session_and_missed_block_does_not(client, db_session):
    setup = create_learning_stack(client, target_hours=200, exam_days=10)
    client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS)
    client.post(
        "/api/v1/state/observations",
        headers=AUTH_HEADERS,
        json={"energy": 70, "mental_state": 70, "observed_at": iso(BASE - timedelta(minutes=30))},
    )
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    plan = client.post(
        "/api/v1/plans/generate",
        headers=AUTH_HEADERS,
        json={
            "planning_date": BASE.date().isoformat(),
            "timezone": "UTC",
            "horizon_start": iso(BASE),
            "horizon_end": iso(BASE + timedelta(hours=12)),
            "expected_world_revision": revision,
        },
    ).json()
    block = next(block for block in plan["blocks"] if block["domain"] == "learning")
    completed = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "actual_duration_minutes": 35, "occurred_at": iso(BASE + timedelta(minutes=45))},
    ).json()

    assert next(item for item in completed["blocks"] if item["id"] == block["id"])["actual_duration_minutes"] == 35
    assert db_session.query(StudySession).count() == 1
    assert db_session.query(StudySession).one().duration_minutes == 35
    assert db_session.query(StudySession).one().source_plan_block_id == block["id"]

    response = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"] + 1, "actual_duration_minutes": 35, "occurred_at": iso(BASE + timedelta(minutes=50))},
    )
    assert response.status_code == 409
    assert db_session.query(StudySession).count() == 1

    client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS)
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    next_plan = client.post(
        "/api/v1/plans/generate",
        headers=AUTH_HEADERS,
        json={
            "planning_date": (BASE + timedelta(days=1)).date().isoformat(),
            "timezone": "UTC",
            "horizon_start": iso(BASE + timedelta(days=1)),
            "horizon_end": iso(BASE + timedelta(days=1, hours=12)),
            "expected_world_revision": revision,
        },
    ).json()
    skipped_block = next(block for block in next_plan["blocks"] if block["domain"] == "learning")
    client.post(
        f"/api/v1/plans/{next_plan['id']}/blocks/{skipped_block['id']}/skip",
        headers=AUTH_HEADERS,
        json={"expected_version": skipped_block["version"], "reason": "other", "occurred_at": iso(BASE + timedelta(days=1, minutes=20))},
    )
    assert db_session.query(StudySession).count() == 1
    assert db_session.query(Action).filter(Action.domain == "learning").count() >= 1
