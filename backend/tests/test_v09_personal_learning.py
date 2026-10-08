from datetime import UTC, datetime, timedelta

from app.api.deps import get_or_create_user
from app.database.models import Action, PatternEvidence, PersonalModelVersion, Plan, PlanBlock, StateObservation, TrainingExample

from .conftest import AUTH_HEADERS


BASE = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _user(db_session):
    return get_or_create_user(db_session)


def _history_block(db, user, index: int, *, domain="learning", status="completed", level="maintenance", hour=9, duration=30, actual=30, delay=3):
    action = Action(
        user_id=user.id,
        title=f"{domain} action {index}",
        domain=domain,
        level=level,
        estimated_minutes=duration,
        duration_min_minutes=25,
        duration_max_minutes=60,
        metadata_json={"activation_difficulty": 30, "cognitive_load": 70 if domain == "learning" else 35, "physical_load": 25},
        status="completed" if status == "completed" else "cancelled",
        completed_minutes=duration if status == "completed" else 0,
    )
    db.add(action)
    db.flush()
    day = BASE + timedelta(days=index)
    start = day.replace(hour=hour)
    plan = Plan(
        user_id=user.id,
        planner_version="v0.9-test",
        generated_from_world_revision=user.world_revision,
        status="superseded",
        planning_day=start.date(),
        horizon_start=start.replace(hour=8),
        horizon_end=start.replace(hour=22),
        generated_at=start - timedelta(hours=2),
        summary_metrics={"energy": 70, "mental_state": 70, "state_band": "high", "usable_flexible_minutes": 300, "required_slack_minutes": 45},
        decision_factors={"items": []},
        personal_model_snapshot={},
        personal_model_revision=0,
    )
    db.add(plan)
    db.flush()
    started_at = start + timedelta(minutes=delay) if status in {"completed", "skipped"} else None
    finished_at = start + timedelta(minutes=actual + delay) if status in {"completed", "skipped", "missed"} else None
    block = PlanBlock(
        user_id=user.id,
        plan_id=plan.id,
        action_id=action.id,
        source_type="action",
        source_id=action.id,
        domain=domain,
        title=action.title,
        starts_at=start,
        ends_at=start + timedelta(minutes=duration),
        duration_minutes=duration,
        block_type="generated_action",
        commitment_level=level,
        movable=True,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        actual_duration_minutes=actual if status == "completed" else None,
        outcome_reason=None if status == "completed" else "activation_difficulty",
        decision_factors={"items": []},
    )
    db.add(block)
    db.flush()
    db.add(StateObservation(user_id=user.id, observation_type="energy", value=70, observed_at=start - timedelta(minutes=15), source="test"))
    db.add(StateObservation(user_id=user.id, observation_type="mental_state", value=70, observed_at=start - timedelta(minutes=15), source="test"))
    db.add(StateObservation(user_id=user.id, observation_type="energy", value=72, observed_at=(finished_at or start) + timedelta(minutes=45), source="test"))
    db.add(StateObservation(user_id=user.id, observation_type="mental_state", value=74, observed_at=(finished_at or start) + timedelta(minutes=45), source="test"))
    db.flush()
    return block


def _refresh(client):
    response = client.post("/api/v1/personal-model/refresh", headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def test_low_real_evidence_stays_baseline_and_rejects_candidates(client):
    refresh = _refresh(client)
    assert refresh["evidence_n"] == 0
    summary = client.get("/api/v1/personal-model/summary", headers=AUTH_HEADERS).json()
    assert summary["status"] == "BASELINE_INSUFFICIENT_EVIDENCE"
    assert summary["active_model_count"] == 0
    assert summary["fallback_rate"] == 1
    models = client.get("/api/v1/personal-model/models", headers=AUTH_HEADERS).json()
    assert all(model["status"] == "REJECTED" for model in models)
    assert any("INSUFFICIENT_EVIDENCE" in (model["promotion_reason"] or "") for model in models)


def test_feature_extraction_separates_labels_and_provenance(client, db_session):
    user = _user(db_session)
    block = _history_block(db_session, user, 0)
    _refresh(client)
    example = db_session.query(TrainingExample).filter_by(plan_block_id=block.id).one()
    assert example.feature_schema_version == "personal-features-v1"
    assert "completed" not in example.feature_json
    assert "actual_duration_minutes" not in example.feature_json
    assert example.label_json["completed"] is True
    assert example.provenance_json["plan_block_id"] == block.id
    assert example.provenance_json["feature_schema_version"] == "personal-features-v1"


def test_synthetic_history_promotes_models_and_planner_stores_snapshot(client, db_session):
    user = _user(db_session)
    for index in range(24):
        _history_block(db_session, user, index, domain="learning", status="completed", hour=9, duration=30, actual=28, delay=2)
    _refresh(client)
    summary = client.get("/api/v1/personal-model/summary", headers=AUTH_HEADERS).json()
    assert summary["active_model_count"] >= 1

    action = client.post(
        "/api/v1/actions",
        headers=AUTH_HEADERS | {"Idempotency-Key": "v09-plan-action"},
        json={"title": "Study personalized slot", "domain": "learning", "level": "maintenance", "estimated_minutes": 30},
    ).json()
    plan = client.post("/api/v1/plans/generate", headers=AUTH_HEADERS | {"Idempotency-Key": "v09-plan"}, json={}).json()
    assert plan["personal_model_snapshot"]["active_model_ids"]
    assert plan["personal_model_revision"] >= 1
    assert any(factor["factor"] == "personal_model_snapshot" for factor in plan["decision_factors"])
    block = next(item for item in plan["blocks"] if item.get("action_id") == action["id"])
    assert any(factor["factor"].startswith("learned_") for factor in block["decision_factors"])


def test_pattern_correction_invalidates_pattern_and_preserves_history(client, db_session):
    user = _user(db_session)
    for index in range(24):
        _history_block(db_session, user, index, domain="fitness", status="completed", hour=15, duration=35, actual=35, delay=1)
    _refresh(client)
    pattern = db_session.query(PatternEvidence).filter_by(user_id=user.id, status="ACTIVE").first()
    assert pattern is not None
    response = client.post(
        f"/api/v1/personal-model/patterns/{pattern.id}/correct",
        headers=AUTH_HEADERS,
        json={"reason": "user_says_wrong", "note": "Fixture correction"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INVALIDATED"
    assert body["correction_metadata"]["preserved_history"] is True
    assert db_session.query(TrainingExample).count() > 0


def test_goal_critical_work_not_suppressed_by_low_completion_model(client, db_session):
    user = _user(db_session)
    db_session.add(
        PersonalModelVersion(
            user_id=user.id,
            model_type="completion",
            model_stage="STAGE_1",
            version=1,
            feature_schema_version="personal-features-v1",
            status="ACTIVE",
            parameters={
                "formula": "(completions + 2) / (attempts + 2 + 2)",
                "bins": {"global": {"attempts": 24, "completions": 2, "completion_probability": 0.2}},
                "guard": "Low probability is a bounded ranking/variant signal only; it never suppresses goal-critical work.",
            },
            evidence_n=24,
            effective_evidence_n=24,
            confidence=0.9,
            metrics={"loss": 0.1},
            baseline_metrics={"loss": 0.2},
            promotion_reason="PROMOTED: fixture for planner guard.",
            promoted_at=BASE,
        )
    )
    db_session.flush()
    action = client.post(
        "/api/v1/actions",
        headers=AUTH_HEADERS | {"Idempotency-Key": "v09-critical-action"},
        json={"title": "Critical exam study", "domain": "learning", "level": "goal_critical", "estimated_minutes": 60, "duration_min_minutes": 25, "duration_max_minutes": 60},
    ).json()
    plan = client.post("/api/v1/plans/generate", headers=AUTH_HEADERS | {"Idempotency-Key": "v09-critical-plan"}, json={}).json()
    block = next((item for item in plan["blocks"] if item.get("action_id") == action["id"]), None)
    assert block is not None
    learned = [factor for factor in block["decision_factors"] if factor["factor"] == "learned_completion_fit"]
    assert learned
    assert learned[0]["contribution"] >= -1
    assert block["duration_minutes"] >= 25


def test_assistant_can_read_but_not_refresh_personal_models(client):
    read = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "What is my personal learning status?", "role": "GENERAL_ASSISTANT"},
    ).json()
    assert read["response_type"] == "INFORMATION"
    assert "Personal learning status" in read["message"]
    forbidden = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "refresh personal model now", "role": "GENERAL_ASSISTANT"},
    ).json()
    assert forbidden["response_type"] != "MUTATION_RESULT"
