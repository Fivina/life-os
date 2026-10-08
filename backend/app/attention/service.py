from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.attention.schemas import AttentionAction, AttentionDecision, AttentionItemStatus
from app.core.logging import get_logger
from app.database.models import AttentionItem, UserProfile
from app.events.service import append_event


logger = get_logger(__name__)
PENDING_STATUSES = (AttentionItemStatus.pending.value, AttentionItemStatus.eligible.value)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AttentionItemService:
    def enqueue(
        self,
        db: Session,
        user: UserProfile,
        decision: AttentionDecision,
        *,
        deduplication_key: str,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[AttentionItem, bool]:
        if decision.action in {AttentionAction.silent, AttentionAction.act_silently}:
            raise ValueError("This attention action does not represent a pending surfaceable item.")
        existing = db.scalar(
            select(AttentionItem).where(
                AttentionItem.user_id == user.id,
                AttentionItem.deduplication_key == deduplication_key,
            )
        )
        if existing is not None:
            logger.info("attention_item_deduplicated", extra={"user_id": user.id, "attention_item_id": existing.id})
            return existing, False
        row = AttentionItem(
            user_id=user.id,
            action=decision.action.value,
            reason_code=decision.reason_code,
            subject=decision.subject,
            payload_json=payload or {},
            priority=decision.priority,
            source_cognitive_event_id=decision.source_event_id,
            source_trace_id=decision.source_trace_id,
            workspace_id=decision.workspace_id,
            open_thread_id=decision.open_thread_id,
            prospective_thread_id=decision.prospective_thread_id,
            not_before=decision.not_before,
            expires_at=decision.expires_at,
            status=AttentionItemStatus.pending.value,
            deduplication_key=deduplication_key,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.flush()
        append_event(
            db,
            user,
            event_type="attention_item.created",
            aggregate_type="attention_item",
            aggregate_id=row.id,
            payload={"attention_item_id": row.id, "action": row.action, "reason_code": row.reason_code},
            outbox=False,
        )
        logger.info("attention_item_created", extra={"user_id": user.id, "attention_item_id": row.id, "action": row.action})
        return row, True

    def get(self, db: Session, user: UserProfile, item_id: str) -> AttentionItem | None:
        return db.scalar(select(AttentionItem).where(AttentionItem.id == item_id, AttentionItem.user_id == user.id))

    def list_pending(
        self, db: Session, user: UserProfile, *, now: datetime | None = None, limit: int = 20
    ) -> list[AttentionItem]:
        when = now or utcnow()
        return list(db.scalars(
            select(AttentionItem)
            .where(
                AttentionItem.user_id == user.id,
                AttentionItem.status.in_(PENDING_STATUSES),
                or_(AttentionItem.not_before.is_(None), AttentionItem.not_before <= when),
                or_(AttentionItem.expires_at.is_(None), AttentionItem.expires_at >= when),
            )
            .order_by(AttentionItem.priority.desc(), AttentionItem.created_at.asc())
            .limit(max(1, min(limit, 100)))
        ))

    def refresh_eligibility(
        self, db: Session, user: UserProfile, *, now: datetime | None = None, limit: int = 100
    ) -> tuple[list[AttentionItem], list[AttentionItem]]:
        when = now or utcnow()
        rows = list(db.scalars(
            select(AttentionItem)
            .where(AttentionItem.user_id == user.id, AttentionItem.status.in_(PENDING_STATUSES))
            .order_by(AttentionItem.created_at.asc())
            .limit(max(1, min(limit, 500)))
            .with_for_update()
        ))
        eligible: list[AttentionItem] = []
        expired: list[AttentionItem] = []
        for row in rows:
            if row.expires_at and _aware(row.expires_at) < _aware(when):
                row.status = AttentionItemStatus.expired.value
                expired.append(row)
            elif not row.not_before or _aware(row.not_before) <= _aware(when):
                row.status = AttentionItemStatus.eligible.value
                eligible.append(row)
        return eligible, expired

    def mark_surfaced(self, db: Session, user: UserProfile, item_id: str, *, now: datetime | None = None) -> AttentionItem:
        return self._transition(db, user, item_id, AttentionItemStatus.surfaced, now=now)

    def resolve(self, db: Session, user: UserProfile, item_id: str, *, now: datetime | None = None) -> AttentionItem:
        return self._transition(db, user, item_id, AttentionItemStatus.resolved, now=now)

    def dismiss(self, db: Session, user: UserProfile, item_id: str, *, now: datetime | None = None) -> AttentionItem:
        return self._transition(db, user, item_id, AttentionItemStatus.dismissed, now=now)

    def _transition(
        self,
        db: Session,
        user: UserProfile,
        item_id: str,
        status: AttentionItemStatus,
        *,
        now: datetime | None,
    ) -> AttentionItem:
        row = db.scalar(
            select(AttentionItem).where(AttentionItem.id == item_id, AttentionItem.user_id == user.id).with_for_update()
        )
        if row is None:
            raise LookupError("Attention item not found.")
        if row.status == status.value:
            return row
        if row.status in {AttentionItemStatus.resolved.value, AttentionItemStatus.dismissed.value, AttentionItemStatus.expired.value}:
            raise ValueError("Closed attention items cannot transition.")
        row.status = status.value
        when = now or utcnow()
        if status == AttentionItemStatus.surfaced:
            row.surfaced_at = when
        if status == AttentionItemStatus.resolved:
            row.resolved_at = when
        return row
