from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.database.models import Action, Event, OutboxEvent, Plan, PlanBlock, UserProfile
from app.planning.engine import BLOCK_GENERATED_ACTION, BLOCK_HARD_COMMITMENT, BLOCK_SLACK, CorePlannerV03
from app.planning.schemas import PlanGenerateRequest
from app.planning.service import assemble_planning_context, generate_plan
from app.planning.simulator import scenario_contexts

AUTH_HEADERS = {"Authorization": "Bearer dev-local-token"}


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


BASE_DAY = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)
HORIZON_START = BASE_DAY
HORIZON_END = datetime(2026, 9, 15, 22, 0, tzinfo=UTC)


def setup_planning_world(client, *, energy: int = 65, mental_state: int = 65) -> dict:
    client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"state-{energy}-{mental_state}"},
        json={"energy": energy, "mental_state": mental_state, "observed_at": iso(BASE_DAY - timedelta(hours=1))},
    )
    commitment = client.post(
        "/api/v1/commitments",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"commitment-{energy}-{mental_state}"},
        json={
            "title": "University",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(datetime(2026, 9, 15, 11, 0, tzinfo=UTC)),
            "ends_at": iso(datetime(2026, 9, 15, 16, 0, tzinfo=UTC)),
            "timezone": "UTC",
            "location": "University",
        },
    ).json()
    study = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"study-{energy}-{mental_state}"},
        json={
            "title": "Study Macroeconomics",
            "domain": "learning",
            "level": "goal_critical",
            "estimated_minutes": 120,
            "duration_min_minutes": 25,
            "deadline": iso(datetime(2026, 9, 17, 18, 0, tzinfo=UTC)),
        },
    ).json()
    groceries = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"groceries-{energy}-{mental_state}"},
        json={
            "title": "Buy groceries",
            "domain": "kitchen",
            "level": "maintenance",
            "estimated_minutes": 30,
            "duration_min_minutes": 20,
        },
    ).json()
    optional = client.post(
        "/api/v1/actions",
        headers={**AUTH_HEADERS, "Idempotency-Key": f"optional-{energy}-{mental_state}"},
        json={
            "title": "Read optional article",
            "domain": "learning",
            "level": "optional",
            "estimated_minutes": 60,
            "duration_min_minutes": 25,
        },
    ).json()
    revision = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS).json()["world_revision"]
    return {"commitment": commitment, "study": study, "groceries": groceries, "optional": optional, "world_revision": revision}


def generate_payload(expected_world_revision: int | None = None) -> dict:
    payload = {
        "planning_date": "2026-09-15",
        "timezone": "UTC",
        "horizon_start": iso(HORIZON_START),
        "horizon_end": iso(HORIZON_END),
    }
    if expected_world_revision is not None:
        payload["expected_world_revision"] = expected_world_revision
    return payload


def test_planning_context_consumes_canonical_state_commitments_actions(client, db_session):
    setup = setup_planning_world(client)
    user = db_session.query(UserProfile).one()
    context = assemble_planning_context(db_session, user, PlanGenerateRequest(**generate_payload()))

    assert context.energy == 65
    assert context.mental_state == 65
    assert context.generated_from_world_revision == setup["world_revision"]
    assert [item.title for item in context.hard_commitments] == ["University"]
    assert {item.title for item in context.candidate_actions} == {
        "Study Macroeconomics",
        "Buy groceries",
        "Read optional article",
    }

    client.post(
        f"/api/v1/actions/{setup['optional']['id']}/complete",
        headers={**AUTH_HEADERS, "Idempotency-Key": "complete-optional-before-plan"},
        json={"expected_version": setup["optional"]["version"]},
    )
    context = assemble_planning_context(db_session, user, PlanGenerateRequest(**generate_payload()))
    assert "Read optional article" not in {item.title for item in context.candidate_actions}


def test_generate_plan_persists_projection_without_mutating_canonical_actions(client, db_session):
    setup = setup_planning_world(client)
    response = client.post(
        "/api/v1/plans/generate",
        headers={**AUTH_HEADERS, "Idempotency-Key": "generate-normal-plan"},
        json=generate_payload(setup["world_revision"]),
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["generated_from_world_revision"] == setup["world_revision"]
    assert plan["status"] == "current"
    assert plan["summary_metrics"]["stress_estimate"] <= plan["summary_metrics"]["stress_threshold"]
    assert plan["summary_metrics"]["slack_minutes"] >= plan["summary_metrics"]["required_slack_minutes"]

    hard = [block for block in plan["blocks"] if block["block_type"] == BLOCK_HARD_COMMITMENT]
    assert len(hard) == 1
    assert hard[0]["title"] == "University"
    assert hard[0]["movable"] is False
    assert hard[0]["source_type"] == "commitment"
    assert hard[0]["commitment_id"] == setup["commitment"]["id"]

    generated = [block for block in plan["blocks"] if block["block_type"] == BLOCK_GENERATED_ACTION]
    assert any(block["title"] == "Study Macroeconomics" for block in generated)
    assert all(block["source_type"] == "action" and block["action_id"] for block in generated)
    assert any(block["block_type"] == BLOCK_SLACK for block in plan["blocks"])

    university_start = datetime.fromisoformat(hard[0]["starts_at"])
    university_end = datetime.fromisoformat(hard[0]["ends_at"])
    for block in generated:
        start = datetime.fromisoformat(block["starts_at"])
        end = datetime.fromisoformat(block["ends_at"])
        assert end <= university_start or start >= university_end
        assert block["duration_minutes"] > 0
        assert any(factor["factor"] == "deadline_urgency" for factor in block["decision_factors"])

    assert db_session.query(Plan).count() == 1
    assert db_session.query(PlanBlock).count() == len(plan["blocks"])
    assert db_session.query(Event).filter(Event.event_type == "plan.generated").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "plan.generated").count() == 1
    assert db_session.query(Action).filter(Action.title == "Study Macroeconomics").one().status == "active"
    assert db_session.query(Action).count() == 3


def test_low_state_reduces_flexible_load_and_increases_slack(client):
    planner = CorePlannerV03()
    contexts = scenario_contexts()
    high = planner.run(contexts["normal_day"])
    low = planner.run(contexts["low_state"])

    high_flexible = sum(block.duration_minutes for block in high.blocks if block.block_type == BLOCK_GENERATED_ACTION)
    low_flexible = sum(block.duration_minutes for block in low.blocks if block.block_type == BLOCK_GENERATED_ACTION)
    low_study = next(block for block in low.blocks if block.title == "Macroeconomics study")

    assert low_flexible < high_flexible
    assert low.capacity.required_slack_minutes > high.capacity.required_slack_minutes
    assert 25 <= low_study.duration_minutes <= 45
    assert low.capacity.state_band in {"very_low", "low"}


def test_stale_revision_rejected_and_not_published(client, db_session):
    setup = setup_planning_world(client)
    client.post(
        "/api/v1/commitments",
        headers={**AUTH_HEADERS, "Idempotency-Key": "world-change-before-stale-generate"},
        json={
            "title": "Doctor",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": iso(datetime(2026, 9, 15, 17, 0, tzinfo=UTC)),
            "ends_at": iso(datetime(2026, 9, 15, 18, 0, tzinfo=UTC)),
            "timezone": "UTC",
        },
    )

    response = client.post(
        "/api/v1/plans/generate",
        headers={**AUTH_HEADERS, "Idempotency-Key": "generate-stale-plan"},
        json=generate_payload(setup["world_revision"]),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_world_revision"
    assert db_session.query(Plan).count() == 0


def test_world_change_during_generation_discards_unpublished_plan(client, db_session):
    setup_planning_world(client)
    user = db_session.query(UserProfile).one()

    def mutate_world() -> None:
        user.world_revision += 1

    with pytest.raises(Exception) as exc_info:
        generate_plan(db_session, user, PlanGenerateRequest(**generate_payload()), before_publish_hook=mutate_world)
    assert getattr(exc_info.value, "status_code", None) == 409

    assert db_session.query(Plan).count() == 0
    assert db_session.query(Event).filter(Event.event_type == "plan.generated").count() == 0


def test_engine_scenarios_are_deterministic_and_respect_capacity():
    planner = CorePlannerV03()
    contexts = scenario_contexts()
    normal = planner.run(contexts["normal_day"])
    low = planner.run(contexts["low_state"])
    overloaded = planner.run(contexts["overloaded_day"])
    no_work = planner.run(contexts["no_flexible_work"])
    first = planner.run(contexts["determinism"])
    second = planner.run(contexts["determinism"])

    assert any(block.block_type == BLOCK_HARD_COMMITMENT and block.title == "University" for block in normal.blocks)
    assert any(block.block_type == BLOCK_SLACK for block in normal.blocks)
    assert low.capacity.usable_flexible_minutes < normal.capacity.usable_flexible_minutes
    assert low.capacity.required_slack_minutes > normal.capacity.required_slack_minutes
    assert overloaded.unscheduled_actions
    assert all(block.block_type != BLOCK_GENERATED_ACTION for block in no_work.blocks)
    assert [(block.title, block.starts_at, block.ends_at) for block in first.blocks] == [
        (block.title, block.starts_at, block.ends_at) for block in second.blocks
    ]
