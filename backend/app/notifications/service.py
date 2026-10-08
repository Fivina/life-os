from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.models import NotificationIntent, OutboxEvent, PushDelivery, PushSubscription, UserProfile
from app.events.service import append_event
from app.notifications.schemas import PushSubscriptionCreate, TestNotificationCreate


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def upsert_subscription(db: Session, user: UserProfile, payload: PushSubscriptionCreate, *, user_agent: str | None = None) -> PushSubscription:
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint))
    if existing is not None and existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Push subscription belongs to another user.")
    subscription = existing or PushSubscription(user_id=user.id, endpoint=payload.endpoint)
    subscription.p256dh_key = payload.keys.p256dh
    subscription.auth_key = payload.keys.auth
    subscription.user_agent = user_agent
    subscription.device_label = payload.device_label
    subscription.status = "active"
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def unsubscribe(db: Session, user: UserProfile, subscription_id: str) -> None:
    subscription = db.get(PushSubscription, subscription_id)
    if subscription is None or subscription.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push subscription not found.")
    subscription.status = "revoked"
    subscription.version += 1
    db.commit()


def create_test_notification(db: Session, user: UserProfile, payload: TestNotificationCreate) -> NotificationIntent:
    dedupe_key = payload.dedupe_key or f"manual-test:{uuid4()}"
    existing = db.scalar(select(NotificationIntent).where(NotificationIntent.user_id == user.id, NotificationIntent.dedupe_key == dedupe_key))
    if existing is not None:
        return existing
    intent = NotificationIntent(
        user_id=user.id,
        intent_type="manual_test",
        priority="normal",
        title=payload.title,
        body=payload.body,
        payload={"source": "manual_test"},
        status="pending",
        scheduled_for=_now(),
        expires_at=_now() + timedelta(minutes=payload.expires_in_minutes),
        dedupe_key=dedupe_key,
    )
    db.add(intent)
    db.flush()
    append_event(
        db,
        user,
        event_type="notification.intent.created",
        aggregate_type="notification_intent",
        aggregate_id=intent.id,
        payload={"notification_intent_id": intent.id, "dedupe_key": dedupe_key},
        outbox=True,
    )
    db.commit()
    db.refresh(intent)
    return intent


class PushOutboxHandler:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def publish(self, event: OutboxEvent) -> None:
        if event.event_type != "notification.intent.created":
            return
        intent_id = event.payload.get("notification_intent_id")
        if not intent_id:
            return
        intent = self.db.get(NotificationIntent, intent_id)
        if intent is None or intent.user_id != event.user_id:
            return
        deliver_notification_intent(self.db, intent, self.settings)


def deliver_notification_intent(db: Session, intent: NotificationIntent, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    now = _now()
    if intent.status in {"delivered", "suppressed"}:
        return
    if intent.expires_at is not None and _aware(intent.expires_at) < now:
        intent.status = "suppressed"
        intent.suppressed_reason = "expired"
        return
    subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == intent.user_id, PushSubscription.status == "active")).all())
    if not subscriptions:
        intent.status = "suppressed"
        intent.suppressed_reason = "no_active_subscription"
        return

    errors: list[str] = []
    delivered = 0
    dedupe_key = intent.dedupe_key or intent.id
    for subscription in subscriptions:
        delivery = db.scalar(select(PushDelivery).where(PushDelivery.push_subscription_id == subscription.id, PushDelivery.dedupe_key == dedupe_key))
        if delivery is not None and delivery.status == "delivered":
            delivered += 1
            continue
        if delivery is None:
            delivery = PushDelivery(user_id=intent.user_id, notification_intent_id=intent.id, push_subscription_id=subscription.id, dedupe_key=dedupe_key)
            db.add(delivery)
            db.flush()
        delivery.attempts += 1
        try:
            _send_push(subscription, intent, settings)
            delivery.status = "delivered"
            delivery.delivered_at = now
            delivery.last_error = None
            subscription.last_success_at = now
            subscription.failure_count = 0
            delivered += 1
        except Exception as exc:
            delivery.status = "failed"
            delivery.last_error = str(exc)[:4000]
            subscription.last_failure_at = now
            subscription.failure_count += 1
            if subscription.failure_count >= 5:
                subscription.status = "dead"
            errors.append(str(exc))

    if delivered:
        intent.status = "delivered"
        intent.delivered_at = now
        intent.suppressed_reason = None
        return
    if errors:
        raise RuntimeError("; ".join(errors[:3]))


def _send_push(subscription: PushSubscription, intent: NotificationIntent, settings: Settings) -> None:
    if settings.push_delivery_mode == "mock":
        return
    if settings.push_delivery_mode != "webpush":
        raise RuntimeError(f"Unsupported push delivery mode: {settings.push_delivery_mode}")
    try:
        from pywebpush import webpush  # type: ignore
    except Exception as exc:  # pragma: no cover - optional production dependency path
        raise RuntimeError("pywebpush is not installed.") from exc
    if not (settings.vapid_private_key and settings.push_subject):
        raise RuntimeError("VAPID configuration is missing.")
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
        },
        data=json.dumps({"title": intent.title or "Life OS", "body": intent.body or "", "intent_id": intent.id}),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.push_subject},
    )
