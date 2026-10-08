from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.models import OutboxEvent, OutboxStatus


class OutboxHandler(Protocol):
    def publish(self, event: OutboxEvent) -> None:
        """Publish an outbox event to the future integration boundary."""


@dataclass
class NoopOutboxHandler:
    """Default handler for outbox events with no external integration."""

    def publish(self, event: OutboxEvent) -> None:
        return None


def process_pending_outbox(db: Session, handler: OutboxHandler | None = None, limit: int = 25) -> int:
    settings = get_settings()
    handler = handler or NoopOutboxHandler()
    events = claim_pending_outbox(db, limit=limit)

    for event in events:
        try:
            handler.publish(event)
            event.status = OutboxStatus.published.value
            event.last_error = None
            event.processed_at = datetime.now(UTC)
            event.locked_at = None
        except Exception as exc:  # pragma: no cover - defensive foundation hook
            _mark_failed_or_retry(event, exc, settings)

    db.commit()
    return len(events)


def claim_pending_outbox(db: Session, limit: int = 25) -> list[OutboxEvent]:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("select set_config('app.worker', 'true', true)"))
    now = datetime.now(UTC)
    query = (
        select(OutboxEvent)
        .where(
            OutboxEvent.available_at <= now,
            or_(
                OutboxEvent.status == OutboxStatus.pending.value,
                OutboxEvent.status == OutboxStatus.retry.value,
                OutboxEvent.status == OutboxStatus.failed.value,
            ),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    events = list(db.scalars(query).all())

    for event in events:
        event.status = OutboxStatus.processing.value
        event.attempts += 1
        event.locked_at = now

    db.commit()
    return events


def _mark_failed_or_retry(event: OutboxEvent, exc: Exception, settings: Settings) -> None:
    event.last_error = str(exc)[:4000]
    event.locked_at = None
    if event.attempts >= settings.outbox_max_attempts:
        event.status = OutboxStatus.dead_letter.value
        event.processed_at = datetime.now(UTC)
        return
    backoff = min(settings.outbox_base_backoff_seconds * (2 ** max(event.attempts - 1, 0)), settings.outbox_max_backoff_seconds)
    event.status = OutboxStatus.retry.value
    event.available_at = datetime.now(UTC) + timedelta(seconds=backoff)
