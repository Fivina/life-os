from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models import Action, Event, ExerciseSet, OutboxEvent, ProgressionState, WorkoutSession
from tests.conftest import AUTH_HEADERS

BASE = datetime(2026, 9, 20, 8, 0, tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def create_program_stack(client):
    program = client.post(
        "/api/v1/fitness/programs",
        headers=AUTH_HEADERS,
        json={"name": "Hypertrophy 4-Day", "goal_type": "hypertrophy", "active": True},
    ).json()
    template = client.post(
        "/api/v1/fitness/templates",
        headers=AUTH_HEADERS,
        json={"program_id": program["id"], "name": "Upper A", "sequence_order": 0, "estimated_duration_minutes": 75},
    ).json()
    bench = client.post(
        "/api/v1/fitness/exercises",
        headers=AUTH_HEADERS,
        json={"name": "Bench Press", "category": "push", "primary_muscle_group": "chest", "default_rest_seconds": 120},
    ).json()
    row = client.post(
        "/api/v1/fitness/exercises",
        headers=AUTH_HEADERS,
        json={"name": "Row", "category": "pull", "primary_muscle_group": "back", "default_rest_seconds": 90},
    ).json()
    bench_item = client.post(
        f"/api/v1/fitness/templates/{template['id']}/exercises",
        headers=AUTH_HEADERS,
        json={
            "exercise_id": bench["id"],
            "order_index": 0,
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "target_load_kg": 70,
            "target_rpe": 8.5,
            "rest_seconds": 120,
            "load_increment_kg": 2.5,
        },
    ).json()
    row_item = client.post(
        f"/api/v1/fitness/templates/{template['id']}/exercises",
        headers=AUTH_HEADERS,
        json={
            "exercise_id": row["id"],
            "order_index": 1,
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 12,
            "target_load_kg": 60,
            "rest_seconds": 90,
        },
    ).json()
    return {"program": program, "template": template, "bench": bench, "row": row, "bench_item": bench_item, "row_item": row_item}


def test_program_template_and_exercise_management(client):
    setup = create_program_stack(client)

    programs = client.get("/api/v1/fitness/programs", headers=AUTH_HEADERS).json()
    templates = client.get("/api/v1/fitness/templates", headers=AUTH_HEADERS).json()
    exercises = client.get("/api/v1/fitness/exercises", headers=AUTH_HEADERS).json()

    assert programs[0]["name"] == "Hypertrophy 4-Day"
    assert templates[0]["exercises"][0]["exercise"]["name"] == "Bench Press"
    assert templates[0]["exercises"][1]["exercise"]["name"] == "Row"
    assert {item["name"] for item in exercises} == {"Bench Press", "Row"}

    ok = client.patch(
        f"/api/v1/fitness/programs/{setup['program']['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": setup["program"]["version"], "name": "Hypertrophy 4-Day V2"},
    )
    assert ok.status_code == 200
    conflict = client.patch(
        f"/api/v1/fitness/programs/{setup['program']['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": setup["program"]["version"], "name": "stale"},
    )
    assert conflict.status_code == 409


def test_workout_resume_log_complete_and_progression(client, db_session):
    setup = create_program_stack(client)
    started = client.post(
        "/api/v1/fitness/sessions/start",
        headers=AUTH_HEADERS,
        json={"workout_template_id": setup["template"]["id"], "started_at": iso(BASE)},
    ).json()
    duplicate = client.post(
        "/api/v1/fitness/sessions/start",
        headers=AUTH_HEADERS,
        json={"workout_template_id": setup["template"]["id"], "started_at": iso(BASE + timedelta(minutes=1))},
    ).json()
    assert duplicate["id"] == started["id"]

    active = client.get("/api/v1/fitness/sessions/active", headers=AUTH_HEADERS).json()
    assert active["id"] == started["id"]

    for index in range(3):
        logged = client.post(
            f"/api/v1/fitness/sessions/{started['id']}/sets",
            headers={**AUTH_HEADERS, "Idempotency-Key": f"bench-{index}"},
            json={
                "template_exercise_id": setup["bench_item"]["id"],
                "reps": 10,
                "load_kg": 70,
                "rpe": 8,
                "completed_at": iso(BASE + timedelta(minutes=10 + index * 4)),
            },
        ).json()
        assert logged["sequence"] == index + 1
        assert logged["load_kg"] == 70
        assert logged["rpe"] == 8

    retry = client.post(
        f"/api/v1/fitness/sessions/{started['id']}/sets",
        headers={**AUTH_HEADERS, "Idempotency-Key": "bench-1"},
        json={
            "template_exercise_id": setup["bench_item"]["id"],
            "reps": 10,
            "load_kg": 70,
            "rpe": 8,
            "completed_at": iso(BASE + timedelta(minutes=14)),
        },
    ).json()
    assert retry["sequence"] == 2
    assert db_session.query(ExerciseSet).count() == 3

    completed = client.post(
        f"/api/v1/fitness/sessions/{started['id']}/complete",
        headers=AUTH_HEADERS,
        json={"perceived_session_difficulty": 8, "completed_at": iso(BASE + timedelta(hours=1))},
    ).json()

    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
    progression = db_session.query(ProgressionState).filter(ProgressionState.template_exercise_id == setup["bench_item"]["id"]).one()
    assert progression.recommendation == "increase"
    assert progression.recommended_load_kg == 72.5
    assert "All required working sets" in progression.explanation_json["reason"]
    assert db_session.query(Event).filter(Event.event_type == "fitness.workout.started").count() == 1
    assert db_session.query(Event).filter(Event.event_type == "fitness.set.logged").count() == 3
    assert db_session.query(Event).filter(Event.event_type == "fitness.workout.completed").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "fitness.workout.completed").count() == 1


def test_incomplete_progression_maintains_load(client, db_session):
    setup = create_program_stack(client)
    started = client.post("/api/v1/fitness/sessions/start", headers=AUTH_HEADERS, json={"workout_template_id": setup["template"]["id"]}).json()
    for index, reps in enumerate([10, 8, 7]):
        client.post(
            f"/api/v1/fitness/sessions/{started['id']}/sets",
            headers={**AUTH_HEADERS, "Idempotency-Key": f"incomplete-{index}"},
            json={"template_exercise_id": setup["bench_item"]["id"], "reps": reps, "load_kg": 70, "rpe": 8},
        )

    client.post(f"/api/v1/fitness/sessions/{started['id']}/complete", headers=AUTH_HEADERS, json={"perceived_session_difficulty": 8})

    progression = db_session.query(ProgressionState).filter(ProgressionState.template_exercise_id == setup["bench_item"]["id"]).one()
    assert progression.recommendation == "maintain"
    assert progression.recommended_load_kg == 70


def test_abandon_preserves_logged_sets(client, db_session):
    setup = create_program_stack(client)
    started = client.post("/api/v1/fitness/sessions/start", headers=AUTH_HEADERS, json={"workout_template_id": setup["template"]["id"]}).json()
    client.post(
        f"/api/v1/fitness/sessions/{started['id']}/sets",
        headers=AUTH_HEADERS,
        json={"template_exercise_id": setup["bench_item"]["id"], "reps": 8, "load_kg": 70, "rpe": 9},
    )

    abandoned = client.post(f"/api/v1/fitness/sessions/{started['id']}/abandon", headers=AUTH_HEADERS, json={"notes": "interrupted"}).json()

    assert abandoned["status"] == "abandoned"
    assert db_session.query(WorkoutSession).one().status == "abandoned"
    assert db_session.query(ExerciseSet).count() == 1


def test_body_trend_uses_rolling_average_not_latest_noise(client):
    values = [78.0, 78.8, 78.2, 79.0, 78.4, 78.6, 78.3]
    for index, value in enumerate(values):
        response = client.post(
            "/api/v1/fitness/body-measurements",
            headers=AUTH_HEADERS,
            json={
                "measured_at": iso(BASE + timedelta(days=index)),
                "body_weight_kg": value,
                "body_fat_percentage": 17 + index * 0.1,
                "source": "etekcity_scale",
            },
        )
        assert response.status_code == 200

    trend = client.get("/api/v1/fitness/body-trends", headers=AUTH_HEADERS).json()

    assert trend["weight"]["latest"] == 78.3
    assert trend["weight"]["rolling_average"] == round(sum(values) / len(values), 2)
    assert trend["weight"]["sample_count"] == 7
    assert "rolling 7-day average" in trend["weight"]["label"]


def test_recovery_changes_candidate_characteristics_and_syncs_actions(client, db_session):
    setup = create_program_stack(client)
    good_candidates = client.get("/api/v1/fitness/candidates", headers=AUTH_HEADERS).json()
    assert len(good_candidates) == 3

    client.post("/api/v1/fitness/recovery", headers=AUTH_HEADERS, json={"soreness": 90, "sleep_quality": 30, "stress": 80})
    low_candidates = client.get("/api/v1/fitness/candidates", headers=AUTH_HEADERS).json()

    assert low_candidates[0]["physical_load"] < good_candidates[0]["physical_load"]
    assert low_candidates[-1]["duration_minutes"] <= 45
    assert low_candidates[0]["expected_state_effect"]["readiness_score"] < 45

    synced = client.post("/api/v1/fitness/candidates/sync-actions", headers=AUTH_HEADERS).json()
    assert len(synced) == 3
    assert db_session.query(Action).filter(Action.domain == "fitness").count() == 3
    assert all(action["metadata_json"]["template_id"] == setup["template"]["id"] for action in synced)


def test_planner_consumes_fitness_candidate_variants_without_fitness_writing_planblocks(client, db_session):
    create_program_stack(client)
    client.post("/api/v1/fitness/candidates/sync-actions", headers=AUTH_HEADERS)
    client.post(
        "/api/v1/state/observations",
        headers=AUTH_HEADERS,
        json={"energy": 75, "mental_state": 75, "observed_at": iso(BASE - timedelta(minutes=15))},
    )
    client.post(
        "/api/v1/commitments",
        headers=AUTH_HEADERS,
        json={
            "title": "Long fixed day",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(BASE + timedelta(minutes=45)),
            "ends_at": iso(BASE + timedelta(hours=13)),
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

    fitness_blocks = [block for block in plan["blocks"] if block["domain"] == "fitness"]
    assert fitness_blocks
    assert fitness_blocks[0]["duration_minutes"] <= 45
    assert fitness_blocks[0]["source_type"] == "action"
    assert db_session.query(Action).filter(Action.domain == "fitness").count() == 3
