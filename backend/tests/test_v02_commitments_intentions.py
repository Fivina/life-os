import pytest

from app.database.models import Action, Commitment, Event, OutboxEvent, UserProfile
from tests.conftest import AUTH_HEADERS


def commitment_payload(**overrides):
    payload = {
        "title": "University",
        "level": "hard",
        "commitment_type": "hard",
        "starts_at": "2026-09-16T11:00:00+02:00",
        "ends_at": "2026-09-16T16:00:00+02:00",
        "location": "University",
        "recurrence": {"frequency": "none"},
    }
    payload.update(overrides)
    return payload


def action_payload(**overrides):
    payload = {
        "title": "Study Macroeconomics",
        "domain": "learning",
        "level": "goal_critical",
        "estimated_minutes": 120,
        "deadline": "2026-09-20T23:59:00+02:00",
    }
    payload.update(overrides)
    return payload


def test_create_retrieve_list_edit_and_complete_commitment(client, db_session):
    created = client.post("/api/v1/commitments", headers={**AUTH_HEADERS, "Idempotency-Key": "commitment-create"}, json=commitment_payload())
    assert created.status_code == 200
    body = created.json()
    assert body["location"] == "University"
    assert body["level"] == "hard"
    assert db_session.query(Event).filter(Event.event_type == "commitment.created").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "commitment.created").count() == 1

    retrieved = client.get(f"/api/v1/commitments/{body['id']}", headers=AUTH_HEADERS)
    assert retrieved.status_code == 200
    listed = client.get("/api/v1/commitments", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    edited = client.patch(
        f"/api/v1/commitments/{body['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": body["version"], "starts_at": "2026-09-16T12:00:00+02:00"},
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == body["version"] + 1
    assert edited.json()["starts_at"].startswith("2026-09-16T12:00:00")

    completed = client.post(
        f"/api/v1/commitments/{body['id']}/complete",
        headers={**AUTH_HEADERS, "Idempotency-Key": "commitment-complete"},
        json={"expected_version": edited.json()["version"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert db_session.query(Event).filter(Event.event_type == "commitment.completed").count() == 1
    assert db_session.query(UserProfile).one().world_revision == 3


def test_commitment_hard_overlap_policy(client):
    first = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload())
    assert first.status_code == 200

    overlap = client.post(
        "/api/v1/commitments",
        headers=AUTH_HEADERS,
        json=commitment_payload(title="Doctor", starts_at="2026-09-16T14:00:00+02:00", ends_at="2026-09-16T15:00:00+02:00"),
    )
    assert overlap.status_code == 409
    assert "conflicts" in overlap.json()["detail"]


def test_commitment_boundary_touching_is_allowed(client):
    first = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload(ends_at="2026-09-16T11:00:00+02:00", starts_at="2026-09-16T10:00:00+02:00"))
    second = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload(title="Lecture", starts_at="2026-09-16T11:00:00+02:00", ends_at="2026-09-16T12:00:00+02:00"))

    assert first.status_code == 200
    assert second.status_code == 200


def test_commitment_stale_edit_does_not_mutate_or_increment_revision(client, db_session):
    created = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload())
    body = created.json()
    stale = client.patch(
        f"/api/v1/commitments/{body['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": body["version"] - 1, "title": "Stale"},
    )

    assert stale.status_code == 409
    commitment = db_session.query(Commitment).one()
    assert commitment.title == "University"
    assert db_session.query(UserProfile).one().world_revision == 1


def test_commitment_idempotent_create_does_not_duplicate(client, db_session):
    headers = {**AUTH_HEADERS, "Idempotency-Key": "same-commitment"}
    first = client.post("/api/v1/commitments", headers=headers, json=commitment_payload())
    second = client.post("/api/v1/commitments", headers=headers, json=commitment_payload())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert db_session.query(Commitment).count() == 1
    assert db_session.query(Event).filter(Event.event_type == "commitment.created").count() == 1


def test_create_edit_status_and_list_action(client, db_session):
    created = client.post("/api/v1/actions", headers={**AUTH_HEADERS, "Idempotency-Key": "action-create"}, json=action_payload())
    assert created.status_code == 200
    body = created.json()
    assert body["domain"] == "learning"
    assert body["level"] == "goal_critical"
    assert body["scheduled_start"] is None
    assert db_session.query(Event).filter(Event.event_type == "action.created").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "action.created").count() == 1

    listed = client.get("/api/v1/actions?planning_pool=true", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Study Macroeconomics"

    edited = client.patch(
        f"/api/v1/actions/{body['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": body["version"], "estimated_minutes": 90},
    )
    assert edited.status_code == 200
    assert edited.json()["estimated_minutes"] == 90

    completed = client.post(
        f"/api/v1/actions/{body['id']}/complete",
        headers={**AUTH_HEADERS, "Idempotency-Key": "action-complete"},
        json={"expected_version": edited.json()["version"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert db_session.query(Event).filter(Event.event_type == "action.completed").count() == 1


def test_action_stale_edit_returns_409(client, db_session):
    created = client.post("/api/v1/actions", headers=AUTH_HEADERS, json=action_payload())
    body = created.json()
    stale = client.patch(
        f"/api/v1/actions/{body['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": body["version"] - 1, "title": "Stale"},
    )

    assert stale.status_code == 409
    assert db_session.query(Action).one().title == "Study Macroeconomics"


def test_calendar_projection_is_derived_and_excludes_unscheduled_actions_from_timeline(client):
    commitment = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload())
    action = client.post("/api/v1/actions", headers=AUTH_HEADERS, json=action_payload())
    assert commitment.status_code == 200
    assert action.status_code == 200

    projection = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS)
    assert projection.status_code == 200
    body = projection.json()
    assert body["commitments"][0]["canonical_id"] == commitment.json()["id"]
    assert body["commitments"][0]["canonical_type"] == "commitment"
    assert body["planning_pool"][0]["id"] == action.json()["id"]
    assert body["planning_pool"][0]["scheduled_start"] is None


def test_canonical_edit_changes_calendar_projection(client):
    commitment = client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload())
    body = commitment.json()
    edited = client.patch(
        f"/api/v1/commitments/{body['id']}",
        headers=AUTH_HEADERS,
        json={"expected_version": body["version"], "starts_at": "2026-09-16T12:00:00+02:00"},
    )
    projection = client.get("/api/v1/calendar-projection", headers=AUTH_HEADERS)

    assert edited.status_code == 200
    assert projection.json()["commitments"][0]["starts_at"].startswith("2026-09-16T12:00:00")


def test_failed_commitment_event_rolls_back_canonical_change(client, db_session, monkeypatch):
    import app.commitments.service as commitment_service

    def fail_event(*args, **kwargs):
        raise RuntimeError("event failed")

    monkeypatch.setattr(commitment_service, "append_event", fail_event)
    with pytest.raises(RuntimeError, match="event failed"):
        client.post("/api/v1/commitments", headers=AUTH_HEADERS, json=commitment_payload())

    db_session.rollback()
    assert db_session.query(Commitment).count() == 0
    assert db_session.query(Event).count() == 0
    assert db_session.query(UserProfile).count() == 1
    assert db_session.query(UserProfile).one().world_revision == 0
