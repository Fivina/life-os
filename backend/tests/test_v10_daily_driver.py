from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from app.api.deps import get_settings
from app.core.config import Settings
from app.database.models import NotificationIntent, OutboxEvent, OutboxStatus, PushDelivery, PushSubscription, StateObservation, UserProfile
from app.events.outbox import process_pending_outbox
from app.notifications.service import PushOutboxHandler
from app.main import app

from .conftest import AUTH_HEADERS


SECRET = "supabase-test-secret"
ISSUER = "https://life-os-test.supabase.co/auth/v1"


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def jwt_token(*, subject="allowed-subject", email="user@example.com", exp_delta=timedelta(hours=1), secret=SECRET, issuer=ISSUER, audience="authenticated") -> str:
    header = _b64({"alg": "HS256", "typ": "JWT"})
    payload = _b64(
        {
            "sub": subject,
            "email": email,
            "iss": issuer,
            "aud": audience,
            "exp": int((datetime.now(UTC) + exp_delta).timestamp()),
        }
    )
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def override_prod_auth_settings():
    return Settings(
        app_env="test",
        development_auth_enabled=False,
        supabase_jwt_secret=SECRET,
        supabase_jwt_issuer=ISSUER,
        supabase_jwt_audience="authenticated",
        authorized_auth_subjects="allowed-subject",
        push_delivery_mode="mock",
        outbox_base_backoff_seconds=0,
        outbox_max_attempts=2,
    )


def auth_headers(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or jwt_token()}"}


def test_supabase_jwt_allowlist_and_profile_mapping(client, db_session):
    app.dependency_overrides[get_settings] = override_prod_auth_settings

    response = client.get("/api/v1/me", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    user = db_session.query(UserProfile).one()
    assert user.auth_subject == "allowed-subject"


def test_supabase_jwt_rejects_missing_malformed_expired_and_unauthorized(client):
    app.dependency_overrides[get_settings] = override_prod_auth_settings

    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers=auth_headers("not-a-jwt")).status_code == 401
    assert client.get("/api/v1/me", headers=auth_headers(jwt_token(exp_delta=timedelta(seconds=-1)))).status_code == 401
    assert client.get("/api/v1/me", headers=auth_headers(jwt_token(subject="other-subject"))).status_code == 403


def test_frontend_user_id_payload_is_ignored_under_authenticated_subject(client, db_session):
    app.dependency_overrides[get_settings] = override_prod_auth_settings
    other = UserProfile(email="other@example.com", auth_subject="other-subject")
    db_session.add(other)
    db_session.flush()

    response = client.post("/api/v1/state/observations", headers=auth_headers(), json={"energy": 70, "user_id": other.id})

    assert response.status_code == 200
    observation = db_session.query(StateObservation).one()
    assert observation.user_id != other.id


def test_export_requires_auth_and_contains_canonical_tables(client):
    denied = client.get("/api/v1/export")
    allowed = client.get("/api/v1/export", headers=AUTH_HEADERS)

    assert denied.status_code == 401
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["manifest"]["export_schema_version"] == "life-os-export-v1"
    assert "state_observations" in body["tables"]
    assert "auth_subject" not in body["user_profile"]


def test_push_subscription_notification_pipeline_and_dedupe(client, db_session):
    created = client.post(
        "/api/v1/push/subscriptions",
        headers=AUTH_HEADERS,
        json={"endpoint": "https://push.example/device-1", "keys": {"p256dh": "p256dh-key-material", "auth": "auth-key-material"}},
    )
    duplicate = client.post(
        "/api/v1/push/subscriptions",
        headers=AUTH_HEADERS,
        json={"endpoint": "https://push.example/device-1", "keys": {"p256dh": "p256dh-key-material-2", "auth": "auth-key-material-2"}},
    )
    intent = client.post(
        "/api/v1/notifications/test",
        headers=AUTH_HEADERS,
        json={"title": "Life OS", "body": "Test", "dedupe_key": "test-dedupe"},
    )

    assert created.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == created.json()["id"]
    assert intent.status_code == 200

    processed = process_pending_outbox(db_session, PushOutboxHandler(db_session))
    processed_again = process_pending_outbox(db_session, PushOutboxHandler(db_session))

    assert processed >= 1
    assert processed_again == 0
    assert db_session.query(PushSubscription).count() == 1
    assert db_session.query(NotificationIntent).filter_by(status="delivered").count() == 1
    assert db_session.query(PushDelivery).filter_by(status="delivered").count() == 1
    assert db_session.query(OutboxEvent).filter(OutboxEvent.event_type == "notification.intent.created").one().status == OutboxStatus.published.value


def test_outbox_retry_and_dead_letter(client, db_session):
    client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"energy": 55})
    event = db_session.query(OutboxEvent).one()

    class FailingHandler:
        def publish(self, event):
            raise RuntimeError("temporary failure")

    process_pending_outbox(db_session, FailingHandler())
    db_session.refresh(event)
    assert event.status == OutboxStatus.retry.value
    for _ in range(4):
        event.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        process_pending_outbox(db_session, FailingHandler())
        db_session.refresh(event)
    assert event.status == OutboxStatus.dead_letter.value
