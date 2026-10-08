from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import OpenThread, ProspectiveThread, UserProfile
from app.decision.schemas import EntityReference
from app.events.service import append_event
from app.threads.schemas import (
    OpenThreadStatus,
    ProspectiveThreadStatus,
    ProspectiveTriggerType,
    TriggerConditions,
    validate_trigger_conditions,
)


logger = get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _entities_json(entities: tuple[EntityReference, ...]) -> list[dict]:
    if len(entities) > 16:
        raise ValueError("Threads may reference at most 16 entities.")
    return [entity.model_dump(mode="json") for entity in entities]


class OpenThreadService:
    def create(
        self,
        db: Session,
        user: UserProfile,
        *,
        subject: str,
        intent: str,
        entities: tuple[EntityReference, ...] = (),
        domain: str | None = None,
        category: str | None = None,
        source: str = "manual",
        source_ref: str | None = None,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> OpenThread:
        row = OpenThread(
            user_id=user.id,
            subject=subject,
            intent=intent,
            entities_json=_entities_json(entities),
            domain=domain,
            category=category,
            status=OpenThreadStatus.open.value,
            source=source,
            source_ref=source_ref,
            confidence=confidence,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.flush()
        self._emit(db, user, row, "open_thread.created")
        return row

    def get(self, db: Session, user: UserProfile, thread_id: str) -> OpenThread | None:
        return db.scalar(select(OpenThread).where(OpenThread.id == thread_id, OpenThread.user_id == user.id))

    def list_open(self, db: Session, user: UserProfile, *, limit: int = 20) -> list[OpenThread]:
        return list(db.scalars(
            select(OpenThread)
            .where(OpenThread.user_id == user.id, OpenThread.status == OpenThreadStatus.open.value)
            .order_by(OpenThread.updated_at.desc())
            .limit(max(1, min(limit, 50)))
        ))

    def resolve(self, db: Session, user: UserProfile, thread_id: str, *, now: datetime | None = None) -> OpenThread:
        return self._transition(db, user, thread_id, OpenThreadStatus.resolved, now=now)

    def dismiss(self, db: Session, user: UserProfile, thread_id: str, *, now: datetime | None = None) -> OpenThread:
        return self._transition(db, user, thread_id, OpenThreadStatus.dismissed, now=now)

    def archive(self, db: Session, user: UserProfile, thread_id: str, *, now: datetime | None = None) -> OpenThread:
        return self._transition(db, user, thread_id, OpenThreadStatus.archived, now=now)

    def _transition(
        self,
        db: Session,
        user: UserProfile,
        thread_id: str,
        status: OpenThreadStatus,
        *,
        now: datetime | None,
    ) -> OpenThread:
        row = db.scalar(
            select(OpenThread).where(OpenThread.id == thread_id, OpenThread.user_id == user.id).with_for_update()
        )
        if row is None:
            raise LookupError("Open thread not found.")
        if row.status == status.value:
            return row
        if row.status != OpenThreadStatus.open.value and status != OpenThreadStatus.archived:
            raise ValueError("A closed open thread cannot enter that lifecycle state.")
        row.status = status.value
        when = now or utcnow()
        if status == OpenThreadStatus.resolved:
            row.resolved_at = when
        if status == OpenThreadStatus.archived:
            row.archived_at = when
        self._emit(db, user, row, f"open_thread.{status.value.lower()}")
        return row

    @staticmethod
    def _emit(db: Session, user: UserProfile, row: OpenThread, event_type: str) -> None:
        append_event(
            db, user, event_type=event_type, aggregate_type="open_thread", aggregate_id=row.id,
            payload={"open_thread_id": row.id, "status": row.status}, outbox=True,
        )


class ProspectiveThreadService:
    def create(
        self,
        db: Session,
        user: UserProfile,
        *,
        subject: str,
        intent: str,
        trigger_type: ProspectiveTriggerType,
        trigger_conditions: TriggerConditions | dict,
        entities: tuple[EntityReference, ...] = (),
        domain: str | None = None,
        earliest_relevance: datetime | None = None,
        latest_relevance: datetime | None = None,
        check_policy: str = "ON_CONTEXT_CHANGE",
        attention_policy: str = "MENTION_WHEN_NATURAL",
        source: str = "manual",
        source_ref: str | None = None,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> ProspectiveThread:
        if earliest_relevance and latest_relevance and earliest_relevance > latest_relevance:
            raise ValueError("Earliest relevance must not be after latest relevance.")
        conditions = validate_trigger_conditions(trigger_type, trigger_conditions)
        row = ProspectiveThread(
            user_id=user.id,
            subject=subject,
            intent=intent,
            entities_json=_entities_json(entities),
            domain=domain,
            trigger_type=trigger_type.value,
            trigger_conditions_json=conditions.model_dump(mode="json"),
            earliest_relevance=earliest_relevance,
            latest_relevance=latest_relevance,
            check_policy=check_policy,
            attention_policy=attention_policy,
            status=ProspectiveThreadStatus.open.value,
            source=source,
            source_ref=source_ref,
            confidence=confidence,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.flush()
        self._emit(db, user, row, "prospective_thread.created")
        return row

    def get(self, db: Session, user: UserProfile, thread_id: str) -> ProspectiveThread | None:
        return db.scalar(
            select(ProspectiveThread).where(ProspectiveThread.id == thread_id, ProspectiveThread.user_id == user.id)
        )

    def list_open(self, db: Session, user: UserProfile, *, limit: int = 50) -> list[ProspectiveThread]:
        return list(db.scalars(
            select(ProspectiveThread)
            .where(ProspectiveThread.user_id == user.id, ProspectiveThread.status == ProspectiveThreadStatus.open.value)
            .order_by(ProspectiveThread.earliest_relevance.asc(), ProspectiveThread.created_at.asc())
            .limit(max(1, min(limit, 100)))
        ))

    def expire_due(
        self, db: Session, user: UserProfile, *, now: datetime | None = None, limit: int = 100
    ) -> list[ProspectiveThread]:
        when = now or utcnow()
        rows = list(db.scalars(
            select(ProspectiveThread)
            .where(
                ProspectiveThread.user_id == user.id,
                ProspectiveThread.status == ProspectiveThreadStatus.open.value,
                ProspectiveThread.latest_relevance.is_not(None),
                ProspectiveThread.latest_relevance < when,
            )
            .order_by(ProspectiveThread.latest_relevance.asc())
            .limit(max(1, min(limit, 500)))
            .with_for_update()
        ))
        for row in rows:
            row.status = ProspectiveThreadStatus.expired.value
            row.expired_at = when
            self._emit(db, user, row, "prospective_thread.expired")
        return rows

    def transition(
        self,
        db: Session,
        user: UserProfile,
        thread_id: str,
        status: ProspectiveThreadStatus,
        *,
        now: datetime | None = None,
    ) -> ProspectiveThread:
        if status in {ProspectiveThreadStatus.open, ProspectiveThreadStatus.expired}:
            raise ValueError("Use create or expire_due for this lifecycle state.")
        row = db.scalar(
            select(ProspectiveThread)
            .where(ProspectiveThread.id == thread_id, ProspectiveThread.user_id == user.id)
            .with_for_update()
        )
        if row is None:
            raise LookupError("Prospective thread not found.")
        if row.status == status.value:
            return row
        if row.status != ProspectiveThreadStatus.open.value and status != ProspectiveThreadStatus.archived:
            raise ValueError("A closed prospective thread cannot enter that lifecycle state.")
        row.status = status.value
        when = now or utcnow()
        if status == ProspectiveThreadStatus.resolved:
            row.resolved_at = when
        if status == ProspectiveThreadStatus.archived:
            row.archived_at = when
        self._emit(db, user, row, f"prospective_thread.{status.value.lower()}")
        return row

    @staticmethod
    def _emit(db: Session, user: UserProfile, row: ProspectiveThread, event_type: str) -> None:
        append_event(
            db, user, event_type=event_type, aggregate_type="prospective_thread", aggregate_id=row.id,
            payload={"prospective_thread_id": row.id, "status": row.status, "trigger_type": row.trigger_type},
            outbox=True,
        )
