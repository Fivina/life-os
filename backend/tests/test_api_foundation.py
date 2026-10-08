from app.database.models import Event, OutboxEvent, StateObservation, UserProfile, WorldRevision
from tests.conftest import AUTH_HEADERS


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_route_requires_token(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_me_with_development_token(client):
    response = client.get("/api/v1/me", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["email"] == "user@life-os.local"


def test_state_observation_creates_revision_event_and_outbox(client, db_session):
    response = client.post(
        "/api/v1/state/observations",
        headers={**AUTH_HEADERS, "Idempotency-Key": "state-001"},
        json={"energy": 42, "mental_state": 58},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world_revision"] == 1
    assert len(body["observations"]) == 2
    assert {item["observation_type"] for item in body["observations"]} == {"energy", "mental_state"}
    assert db_session.query(StateObservation).count() == 2
    event = db_session.query(Event).one()
    assert event.event_type == "state.observed"
    assert event.world_revision == 1
    assert event.payload["types"] == ["energy", "mental_state"]
    assert db_session.query(OutboxEvent).count() == 1
    assert db_session.query(WorldRevision).count() == 1

    user = db_session.query(UserProfile).one()
    assert user.world_revision == 1


def test_state_observation_rejects_energy_lower_bound(client, db_session):
    response = client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"energy": -1})

    assert response.status_code == 422
    assert db_session.query(StateObservation).count() == 0
    assert db_session.query(Event).count() == 0
    assert db_session.query(OutboxEvent).count() == 0


def test_state_observation_rejects_energy_upper_bound(client, db_session):
    response = client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"energy": 101})

    assert response.status_code == 422
    assert db_session.query(StateObservation).count() == 0
    assert db_session.query(Event).count() == 0
    assert db_session.query(OutboxEvent).count() == 0


def test_state_observation_rejects_mental_state_lower_bound(client, db_session):
    response = client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"mental_state": -1})

    assert response.status_code == 422
    assert db_session.query(StateObservation).count() == 0
    assert db_session.query(Event).count() == 0
    assert db_session.query(OutboxEvent).count() == 0


def test_state_observation_rejects_mental_state_upper_bound(client, db_session):
    response = client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"mental_state": 101})

    assert response.status_code == 422
    assert db_session.query(StateObservation).count() == 0
    assert db_session.query(Event).count() == 0
    assert db_session.query(OutboxEvent).count() == 0


def test_latest_state_returns_empty_check_in_when_no_observation(client):
    response = client.get("/api/v1/state/latest", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["values"] == {}
    assert response.json()["check_in"] is None


def test_latest_state_returns_newest_check_in(client):
    first = client.post(
        "/api/v1/state/observations",
        headers=AUTH_HEADERS,
        json={"energy": 10, "mental_state": 20, "observed_at": "2026-09-14T06:00:00Z"},
    )
    second = client.post(
        "/api/v1/state/observations",
        headers=AUTH_HEADERS,
        json={"energy": 65, "mental_state": 72, "observed_at": "2026-09-14T08:00:00Z"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    latest = client.get("/api/v1/state/latest", headers=AUTH_HEADERS)

    assert latest.status_code == 200
    body = latest.json()
    assert body["check_in"]["energy"] == 65
    assert body["check_in"]["mental_state"] == 72
    assert body["check_in"]["observed_at"].startswith("2026-09-14T08:00:00")
    assert body["values"]["energy"]["value"] == 65
    assert body["values"]["mental_state"]["value"] == 72
    assert body["world_revision"] == 2


def test_state_observation_idempotency_replays_without_duplicates(client, db_session):
    headers = {**AUTH_HEADERS, "Idempotency-Key": "state-duplicate"}
    first = client.post("/api/v1/state/observations", headers=headers, json={"energy": 75})
    second = client.post("/api/v1/state/observations", headers=headers, json={"energy": 75})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert db_session.query(StateObservation).count() == 1
    assert db_session.query(Event).count() == 1
    assert db_session.query(OutboxEvent).count() == 1


def test_idempotency_key_conflict(client):
    headers = {**AUTH_HEADERS, "Idempotency-Key": "state-conflict"}
    client.post("/api/v1/state/observations", headers=headers, json={"energy": 75})
    response = client.post("/api/v1/state/observations", headers=headers, json={"energy": 76})

    assert response.status_code == 409


def test_commitment_optimistic_concurrency_conflict(client):
    created = client.post(
        "/api/v1/commitments",
        headers=AUTH_HEADERS,
        json={
            "title": "University",
            "level": "hard",
            "commitment_type": "hard",
            "starts_at": "2026-09-16T11:00:00+02:00",
            "ends_at": "2026-09-16T16:00:00+02:00",
        },
    )
    assert created.status_code == 200
    commitment = created.json()

    ok = client.patch(
        f"/api/v1/commitments/{commitment['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": commitment["version"], "title": "University lecture"},
    )
    assert ok.status_code == 200
    assert ok.json()["version"] == commitment["version"] + 1

    conflict = client.patch(
        f"/api/v1/commitments/{commitment['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": commitment["version"], "title": "Outdated edit"},
    )
    assert conflict.status_code == 409


def test_fitness_crud_flow(client):
    created = client.post(
        "/api/v1/fitness/body-measurements",
        headers=AUTH_HEADERS,
        json={"body_weight_kg": 82.4, "body_fat_percentage": 17.2},
    )
    assert created.status_code == 200

    latest = client.get("/api/v1/fitness/body-measurements/latest", headers=AUTH_HEADERS)
    assert latest.status_code == 200
    assert latest.json()["body_weight_kg"] == 82.4

    listed = client.get("/api/v1/fitness/body-measurements", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_learning_crud_flow(client):
    created = client.post(
        "/api/v1/learning/exams",
        headers=AUTH_HEADERS,
        json={"title": "Analysis Exam", "exam_date": "2026-10-10", "estimated_required_hours": 30},
    )
    assert created.status_code == 200

    listed = client.get("/api/v1/learning/exams", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Analysis Exam"


def test_kitchen_inventory_crud_flow(client):
    created = client.post(
        "/api/v1/kitchen/inventory",
        headers=AUTH_HEADERS,
        json={"ingredient_name": "Greek yogurt", "quantity": 2, "unit": "tub"},
    )
    assert created.status_code == 200

    listed = client.get("/api/v1/kitchen/inventory", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert listed.json()[0]["ingredient_name"] == "Greek yogurt"
