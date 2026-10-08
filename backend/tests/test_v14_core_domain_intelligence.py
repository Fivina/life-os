from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.database.models import Action, HouseholdTask, PlanBlock, PlanningDebt, StudySession, WorkoutSession
from app.domains.orchestration import DomainRefreshService

from .conftest import AUTH_HEADERS


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _revision(client) -> int:
    return client.get("/api/v1/me", headers=AUTH_HEADERS).json()["world_revision"]


def _learning(client, *, days: int = 21, minutes: int = 1200):
    course = client.post("/api/v1/learning/courses", headers=AUTH_HEADERS, json={"name": "Algorithms"}).json()
    exam = client.post(
        "/api/v1/learning/exams",
        headers=AUTH_HEADERS,
        json={
            "course_id": course["id"],
            "title": "Algorithms Exam",
            "exam_at": _iso(datetime.now(UTC) + timedelta(days=days)),
            "target_preparation_minutes": minutes,
            "importance": "high",
        },
    ).json()
    return course, exam


def _fitness(client):
    program = client.post(
        "/api/v1/fitness/programs",
        headers=AUTH_HEADERS,
        json={"name": "Strength", "active": True, "weekly_frequency": 3, "minimum_recovery_hours": 24, "location": "gym"},
    ).json()
    template = client.post(
        "/api/v1/fitness/templates",
        headers=AUTH_HEADERS,
        json={"program_id": program["id"], "name": "Upper Body", "estimated_duration_minutes": 60, "active": True},
    ).json()
    exercise = client.post("/api/v1/fitness/exercises", headers=AUTH_HEADERS, json={"name": "Bench Press", "category": "strength"}).json()
    item = client.post(
        f"/api/v1/fitness/templates/{template['id']}/exercises",
        headers=AUTH_HEADERS,
        json={"exercise_id": exercise["id"], "target_sets": 1, "target_rep_min": 8, "target_rep_max": 10, "target_load_kg": 60, "target_rpe": 8},
    ).json()
    return program, template, item


def _generate(client):
    now = datetime.now(UTC)
    return client.post(
        "/api/v1/plans/generate",
        headers=AUTH_HEADERS,
        json={
            "planning_date": now.date().isoformat(),
            "timezone": "UTC",
            "horizon_start": _iso(now.replace(hour=8, minute=0, second=0, microsecond=0)),
            "horizon_end": _iso(now.replace(hour=22, minute=0, second=0, microsecond=0)),
            "expected_world_revision": _revision(client),
        },
    )


def test_learning_reconciles_actions_automatically_and_idempotently(client, db_session):
    _, exam = _learning(client)
    actions = db_session.query(Action).filter(Action.domain == "learning", Action.status == "active").all()
    assert actions
    assert len({item.requirement_key for item in actions}) == 1
    assert all(item.mutually_exclusive and item.source_entity_id == exam["id"] for item in actions)
    assert {item.variant_type for item in actions} >= {"full", "standard", "reduced", "activation"}

    before = db_session.query(Action).filter(Action.domain == "learning").count()
    client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS)
    client.post("/api/v1/learning/candidates/sync-actions", headers=AUTH_HEADERS)
    assert db_session.query(Action).filter(Action.domain == "learning").count() == before


def test_partial_learning_block_records_actual_session_and_residual(client, db_session):
    _learning(client)
    response = _generate(client)
    assert response.status_code == 200, response.text
    plan = response.json()
    block = next(item for item in plan["blocks"] if item["domain"] == "learning")
    actual = max(1, block["duration_minutes"] // 2)
    partial = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/partial",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "actual_duration_minutes": actual},
    )
    assert partial.status_code == 200, partial.text
    session = db_session.query(StudySession).filter(StudySession.source_plan_block_id == block["id"]).one()
    assert session.duration_minutes == actual
    assert session.planned_duration_minutes == block["duration_minutes"]
    assert session.completion_status == "partially_completed"
    debt = db_session.query(PlanningDebt).filter(PlanningDebt.source_plan_block_id == block["id"]).one()
    assert debt.residual_minutes == block["duration_minutes"] - actual


def test_fitness_requirement_and_calendar_execution_preserve_actual_sets(client, db_session):
    _, _, template_item = _fitness(client)
    actions = db_session.query(Action).filter(Action.domain == "fitness", Action.status == "active").all()
    assert len(actions) == 3
    assert len({item.requirement_key for item in actions}) == 1
    response = _generate(client)
    assert response.status_code == 200, response.text
    plan = response.json()
    block = next(item for item in plan["blocks"] if item["domain"] == "fitness")
    started_plan = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/start",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"]},
    ).json()
    started_block = next(item for item in started_plan["blocks"] if item["id"] == block["id"])
    session = db_session.query(WorkoutSession).filter(WorkoutSession.source_plan_block_id == block["id"]).one()
    client.post(
        f"/api/v1/fitness/sessions/{session.id}/sets",
        headers={**AUTH_HEADERS, "Idempotency-Key": "v14-calendar-set"},
        json={"template_exercise_id": template_item["id"], "reps": 9, "load_kg": 62.5, "rpe": 8},
    )
    completed = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/complete",
        headers=AUTH_HEADERS,
        json={"expected_version": started_block["version"], "actual_duration_minutes": block["duration_minutes"]},
    )
    assert completed.status_code == 200, completed.text
    db_session.refresh(session)
    assert session.status == "completed"
    assert session.planned_snapshot_json
    assert session.actual_duration_minutes == block["duration_minutes"]


def test_household_recurrence_skip_and_completion_cycle(client, db_session):
    overdue = datetime.now(UTC) - timedelta(days=8)
    created = client.post(
        "/api/v1/home/tasks",
        headers=AUTH_HEADERS,
        json={"title": "Laundry", "recurrence": {"type": "interval", "days": 7}, "estimated_duration_minutes": 45, "minimum_duration_minutes": 20, "next_due_at": _iso(overdue)},
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert db_session.query(Action).filter(Action.domain == "home", Action.status == "active").count() == 2
    before = db_session.query(Action).filter(Action.domain == "home").count()
    client.post("/api/v1/home/requirements/refresh", headers=AUTH_HEADERS)
    client.post("/api/v1/home/requirements/refresh", headers=AUTH_HEADERS)
    assert db_session.query(Action).filter(Action.domain == "home").count() == before

    plan_response = _generate(client)
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    block = next(item for item in plan["blocks"] if item["domain"] == "home")
    skipped = client.post(
        f"/api/v1/plans/{plan['id']}/blocks/{block['id']}/skip",
        headers=AUTH_HEADERS,
        json={"expected_version": block["version"], "reason": "other"},
    )
    assert skipped.status_code == 200, skipped.text
    canonical = db_session.get(HouseholdTask, task["id"])
    assert canonical.last_completed_at is None
    assert db_session.query(Action).filter(Action.domain == "home", Action.status == "active").count() >= 1

    completed = client.post(f"/api/v1/home/tasks/{task['id']}/complete", headers=AUTH_HEADERS, json={"expected_version": task["version"]})
    assert completed.status_code == 200, completed.text
    canonical = db_session.get(HouseholdTask, task["id"])
    assert canonical.last_completed_at is not None
    assert canonical.next_due_at > canonical.last_completed_at


def test_goal_priority_and_trajectory_bridge_to_actions(client, db_session):
    _, exam = _learning(client)
    response = client.post(
        "/api/v1/goals",
        headers=AUTH_HEADERS,
        json={"title": "Pass Algorithms", "domain": "learning", "priority": 92, "source_entity_type": "exam", "source_entity_id": exam["id"], "target_date": (datetime.now(UTC) + timedelta(days=21)).date().isoformat()},
    )
    assert response.status_code == 201, response.text
    goal = response.json()
    assert goal["trajectory"]["metric_name"] == "readiness"
    actions = db_session.query(Action).filter(Action.domain == "learning", Action.status == "active").all()
    assert actions and all(item.goal_id == goal["id"] and item.planning_priority >= 92 for item in actions)


def test_cross_domain_plan_is_compiled_only_by_planner(client, db_session):
    _learning(client, minutes=300)
    _fitness(client)
    client.post(
        "/api/v1/home/tasks",
        headers=AUTH_HEADERS,
        json={"title": "Kitchen reset", "recurrence": {"type": "daily"}, "estimated_duration_minutes": 20, "minimum_duration_minutes": 10},
    )
    assert db_session.query(PlanBlock).count() == 0
    response = _generate(client)
    assert response.status_code == 200, response.text
    domains = {item["domain"] for item in response.json()["blocks"] if item["block_type"] == "generated_action"}
    assert {"learning", "fitness", "home"}.issubset(domains)


def test_core_domain_refresh_does_not_require_ai(db_session):
    settings = Settings(ai_enabled=False, database_url="sqlite://")
    assert settings.ai_enabled is False
    from app.database.models import UserProfile

    user = UserProfile(email="offline@example.com", display_name="Offline")
    db_session.add(user)
    db_session.flush()
    results = DomainRefreshService().refresh_user(db_session, user)
    assert {item.domain for item in results} == {"learning", "fitness", "home", "goals"}
    assert all(not item.errors for item in results)
