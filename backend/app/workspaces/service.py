from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import ActiveWorkspace, UserProfile
from app.events.service import append_event
from app.workspaces.schemas import WorkspacePayload, WorkspaceStatus, WorkspaceType, validate_workspace_payload


logger = get_logger(__name__)
OPEN_STATUSES = (WorkspaceStatus.active.value, WorkspaceStatus.paused.value)


def utcnow() -> datetime:
    return datetime.now(UTC)


class ActiveWorkspaceService:
    """Owns persisted activity continuity without owning the referenced domain state."""

    def start_workspace(
        self,
        db: Session,
        user: UserProfile,
        *,
        workspace_type: WorkspaceType,
        payload: WorkspacePayload | dict,
        foreground: bool = True,
        conversation_thread_id: str | None = None,
        primary_entity_type: str | None = None,
        primary_entity_id: str | None = None,
        current_phase: str | None = None,
        current_step: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ActiveWorkspace:
        when = now or utcnow()
        self._lock_user(db, user)
        if idempotency_key:
            existing = db.scalar(
                select(ActiveWorkspace).where(
                    ActiveWorkspace.user_id == user.id,
                    ActiveWorkspace.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing

        validated = validate_workspace_payload(workspace_type, payload)
        row = ActiveWorkspace(
            user_id=user.id,
            workspace_type=workspace_type.value,
            status=WorkspaceStatus.active.value,
            is_foreground=False,
            payload_version=validated.payload_version,
            payload_json=validated.model_dump(mode="json"),
            conversation_thread_id=conversation_thread_id,
            primary_entity_type=primary_entity_type,
            primary_entity_id=primary_entity_id,
            current_phase=current_phase,
            current_step=current_step,
            started_at=when,
            last_meaningful_activity_at=when,
            state_revision=1,
            idempotency_key=idempotency_key,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.flush()
        previous_foreground = self._set_foreground(db, user, row) if foreground else []
        self._emit(
            db,
            user,
            row,
            "workspace.started",
            {"workspace_type": row.workspace_type, "foreground": foreground},
        )
        if foreground:
            self._emit(
                db,
                user,
                row,
                "workspace.foreground_changed",
                {"previous_workspace_ids": previous_foreground, "foreground_workspace_id": row.id},
            )
        logger.info("workspace_started", extra={"user_id": user.id, "workspace_id": row.id, "workspace_type": row.workspace_type})
        return row

    def get_workspace(self, db: Session, user: UserProfile, workspace_id: str) -> ActiveWorkspace | None:
        return db.scalar(
            select(ActiveWorkspace).where(ActiveWorkspace.id == workspace_id, ActiveWorkspace.user_id == user.id)
        )

    def get_foreground_workspace(self, db: Session, user: UserProfile) -> ActiveWorkspace | None:
        return db.scalar(
            select(ActiveWorkspace).where(
                ActiveWorkspace.user_id == user.id,
                ActiveWorkspace.is_foreground.is_(True),
                ActiveWorkspace.status.in_(OPEN_STATUSES),
            )
        )

    def list_active(self, db: Session, user: UserProfile, *, limit: int = 20) -> list[ActiveWorkspace]:
        return list(
            db.scalars(
                select(ActiveWorkspace)
                .where(ActiveWorkspace.user_id == user.id, ActiveWorkspace.status.in_(OPEN_STATUSES))
                .order_by(ActiveWorkspace.is_foreground.desc(), ActiveWorkspace.last_meaningful_activity_at.desc())
                .limit(max(1, min(limit, 50)))
            )
        )

    def reconstruct_payload(self, row: ActiveWorkspace) -> WorkspacePayload:
        if row.payload_version != 1:
            raise ValueError(f"Unsupported workspace payload version {row.payload_version}.")
        return validate_workspace_payload(WorkspaceType(row.workspace_type), row.payload_json)

    def update_workspace(
        self,
        db: Session,
        user: UserProfile,
        workspace_id: str,
        *,
        payload: WorkspacePayload | dict,
        current_phase: str | None = None,
        current_step: str | None = None,
        canonical_change_refs: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> ActiveWorkspace:
        row = self._require_locked(db, user, workspace_id)
        self._require_open(row)
        if len(canonical_change_refs) > 32:
            raise ValueError("A workspace update may reference at most 32 canonical changes.")
        validated = validate_workspace_payload(WorkspaceType(row.workspace_type), payload)
        row.payload_version = validated.payload_version
        row.payload_json = validated.model_dump(mode="json")
        row.current_phase = current_phase
        row.current_step = current_step
        row.canonical_change_refs_json = list(canonical_change_refs)
        row.last_meaningful_activity_at = now or utcnow()
        row.state_revision += 1
        self._emit(
            db,
            user,
            row,
            "workspace.updated",
            {"state_revision": row.state_revision, "canonical_change_refs": list(canonical_change_refs)},
        )
        logger.info("workspace_updated", extra={"user_id": user.id, "workspace_id": row.id, "state_revision": row.state_revision})
        return row

    def pause_workspace(
        self, db: Session, user: UserProfile, workspace_id: str, *, now: datetime | None = None
    ) -> ActiveWorkspace:
        row = self._require_locked(db, user, workspace_id)
        if row.status == WorkspaceStatus.paused.value:
            return row
        if row.status != WorkspaceStatus.active.value:
            raise ValueError("Only an active workspace can be paused.")
        row.status = WorkspaceStatus.paused.value
        row.is_foreground = False
        row.paused_at = now or utcnow()
        row.last_meaningful_activity_at = row.paused_at
        row.state_revision += 1
        self._emit(db, user, row, "workspace.paused", {"state_revision": row.state_revision})
        return row

    def resume_workspace(
        self,
        db: Session,
        user: UserProfile,
        workspace_id: str,
        *,
        foreground: bool = True,
        now: datetime | None = None,
    ) -> ActiveWorkspace:
        row = self._require_locked(db, user, workspace_id)
        if row.status == WorkspaceStatus.active.value:
            if foreground and not row.is_foreground:
                self.set_foreground_workspace(db, user, row.id)
            return row
        if row.status != WorkspaceStatus.paused.value:
            raise ValueError("Only a paused workspace can be resumed.")
        row.status = WorkspaceStatus.active.value
        row.resumed_at = now or utcnow()
        row.last_meaningful_activity_at = row.resumed_at
        row.state_revision += 1
        previous = self._set_foreground(db, user, row) if foreground else []
        self._emit(db, user, row, "workspace.resumed", {"state_revision": row.state_revision})
        if foreground:
            self._emit(
                db,
                user,
                row,
                "workspace.foreground_changed",
                {"previous_workspace_ids": previous, "foreground_workspace_id": row.id},
            )
        return row

    def set_foreground_workspace(
        self, db: Session, user: UserProfile, workspace_id: str
    ) -> ActiveWorkspace:
        row = self._require_locked(db, user, workspace_id)
        self._require_open(row)
        if row.is_foreground:
            return row
        previous = self._set_foreground(db, user, row)
        row.state_revision += 1
        self._emit(
            db,
            user,
            row,
            "workspace.foreground_changed",
            {"previous_workspace_ids": previous, "foreground_workspace_id": row.id},
        )
        return row

    def complete_workspace(
        self, db: Session, user: UserProfile, workspace_id: str, *, now: datetime | None = None
    ) -> ActiveWorkspace:
        return self._close(db, user, workspace_id, WorkspaceStatus.completed, now=now)

    def abandon_workspace(
        self, db: Session, user: UserProfile, workspace_id: str, *, now: datetime | None = None
    ) -> ActiveWorkspace:
        return self._close(db, user, workspace_id, WorkspaceStatus.abandoned, now=now)

    def _close(
        self,
        db: Session,
        user: UserProfile,
        workspace_id: str,
        status: WorkspaceStatus,
        *,
        now: datetime | None,
    ) -> ActiveWorkspace:
        row = self._require_locked(db, user, workspace_id)
        if row.status == status.value:
            return row
        self._require_open(row)
        when = now or utcnow()
        row.status = status.value
        row.is_foreground = False
        if status == WorkspaceStatus.completed:
            row.completed_at = when
        else:
            row.abandoned_at = when
        row.last_meaningful_activity_at = when
        row.state_revision += 1
        self._emit(db, user, row, f"workspace.{status.value.lower()}", {"state_revision": row.state_revision})
        return row

    @staticmethod
    def _lock_user(db: Session, user: UserProfile) -> None:
        db.execute(select(UserProfile.id).where(UserProfile.id == user.id).with_for_update()).scalar_one()

    def _require_locked(self, db: Session, user: UserProfile, workspace_id: str) -> ActiveWorkspace:
        self._lock_user(db, user)
        row = db.scalar(
            select(ActiveWorkspace)
            .where(ActiveWorkspace.id == workspace_id, ActiveWorkspace.user_id == user.id)
            .with_for_update()
        )
        if row is None:
            raise LookupError("Workspace not found.")
        return row

    @staticmethod
    def _require_open(row: ActiveWorkspace) -> None:
        if row.status not in OPEN_STATUSES:
            raise ValueError("Closed workspaces cannot be changed.")

    def _set_foreground(
        self, db: Session, user: UserProfile, row: ActiveWorkspace
    ) -> list[str]:
        previous = list(
            db.scalars(
                select(ActiveWorkspace.id)
                .where(
                    ActiveWorkspace.user_id == user.id,
                    ActiveWorkspace.is_foreground.is_(True),
                    ActiveWorkspace.id != row.id,
                )
                .with_for_update()
            )
        )
        if previous:
            db.execute(
                update(ActiveWorkspace)
                .where(ActiveWorkspace.id.in_(previous))
                .values(is_foreground=False)
            )
            db.flush()
        row.is_foreground = True
        db.flush()
        return previous

    @staticmethod
    def _emit(
        db: Session,
        user: UserProfile,
        row: ActiveWorkspace,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        append_event(
            db,
            user,
            event_type=event_type,
            aggregate_type="active_workspace",
            aggregate_id=row.id,
            payload={"workspace_id": row.id, **payload},
            outbox=True,
        )
