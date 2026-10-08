from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.attention.schemas import AttentionItemStatus
from app.core.logging import get_logger
from app.database.models import (
    ActiveWorkspace,
    AttentionItem,
    Commitment,
    Event,
    OpenThread,
    PlanBlock,
    PlanProposal,
    ProspectiveThread,
    UserProfile,
)
from app.threads.eligibility import ProspectiveThreadEligibilityService
from app.threads.schemas import OpenThreadStatus, ProspectiveEvaluationContext, ProspectiveThreadStatus
from app.workspaces.schemas import WorkspaceStatus


logger = get_logger(__name__)
MAX_WORKSPACE_REFS = 4
MAX_RECENT_EVENTS = 10
MAX_ATTENTION_REFS = 10
MAX_OPEN_THREAD_REFS = 8
MAX_PROSPECTIVE_REFS = 8
MAX_TEMPORARY_CONSTRAINTS = 8


class BroadContext(str, Enum):
    home = "HOME"
    university = "UNIVERSITY"
    gym = "GYM"
    commuting = "COMMUTING"
    social = "SOCIAL"
    unknown = "UNKNOWN"


class SituationReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_type: str = Field(min_length=1, max_length=80)
    ref_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=60)
    detail: str | None = Field(default=None, max_length=160)


class ExplicitSelfReportedState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    energy: float | None = Field(default=None, ge=0, le=1)
    mood: str | None = Field(default=None, max_length=120)
    availability: str | None = Field(default=None, max_length=160)
    temporary_limitations: tuple[str, ...] = Field(default=(), max_length=8)


class GlobalWorkspace(BaseModel):
    """A small, non-authoritative, reconstructable situation snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_ref: str
    snapshot_version: int = 1
    created_at: datetime
    current_time: datetime
    broad_context: BroadContext
    foreground_workspace: SituationReference | None = None
    active_workspaces: tuple[SituationReference, ...] = Field(default=(), max_length=MAX_WORKSPACE_REFS)
    current_plan_block: SituationReference | None = None
    next_commitment: SituationReference | None = None
    recent_events: tuple[SituationReference, ...] = Field(default=(), max_length=MAX_RECENT_EVENTS)
    temporary_constraints: tuple[str, ...] = Field(default=(), max_length=MAX_TEMPORARY_CONSTRAINTS)
    self_reported_state: ExplicitSelfReportedState | None = None
    active_proposal_ref: str | None = None
    pending_attention: tuple[SituationReference, ...] = Field(default=(), max_length=MAX_ATTENTION_REFS)
    open_threads: tuple[SituationReference, ...] = Field(default=(), max_length=MAX_OPEN_THREAD_REFS)
    eligible_prospective_threads: tuple[SituationReference, ...] = Field(default=(), max_length=MAX_PROSPECTIVE_REFS)
    conversation_thread_ref: str | None = None
    world_revision: int = Field(ge=0)


class GlobalWorkspaceBuilder:
    def __init__(self, eligibility_service: ProspectiveThreadEligibilityService | None = None):
        self.eligibility_service = eligibility_service or ProspectiveThreadEligibilityService()

    def build(
        self,
        db: Session,
        user: UserProfile,
        *,
        now: datetime | None = None,
        broad_context: BroadContext = BroadContext.unknown,
        temporary_constraints: tuple[str, ...] = (),
        self_reported_state: ExplicitSelfReportedState | None = None,
        conversation_thread_ref: str | None = None,
        goal_states: dict[str, str] | None = None,
        trigger_observations: dict[str, str | bool | int | float | None] | None = None,
        manual_trigger: bool = False,
    ) -> GlobalWorkspace:
        when = now or datetime.now(UTC)
        if len(temporary_constraints) > MAX_TEMPORARY_CONSTRAINTS:
            raise ValueError(f"Situation snapshots allow at most {MAX_TEMPORARY_CONSTRAINTS} temporary constraints.")

        workspace_rows = list(db.scalars(
            select(ActiveWorkspace)
            .where(
                ActiveWorkspace.user_id == user.id,
                ActiveWorkspace.status.in_((WorkspaceStatus.active.value, WorkspaceStatus.paused.value)),
            )
            .order_by(ActiveWorkspace.is_foreground.desc(), ActiveWorkspace.last_meaningful_activity_at.desc())
            .limit(MAX_WORKSPACE_REFS)
        ))
        workspace_refs = tuple(
            SituationReference(
                ref_type="active_workspace",
                ref_id=row.id,
                label=row.workspace_type,
                status=row.status,
                detail=row.current_step or row.current_phase,
            )
            for row in workspace_rows
        )
        foreground = next((reference for row, reference in zip(workspace_rows, workspace_refs) if row.is_foreground), None)

        current_block = db.scalar(
            select(PlanBlock)
            .where(
                PlanBlock.user_id == user.id,
                PlanBlock.starts_at <= when,
                PlanBlock.ends_at > when,
                PlanBlock.status.not_in(("completed", "cancelled", "skipped")),
            )
            .order_by(PlanBlock.starts_at.desc())
            .limit(1)
        )
        next_commitment = db.scalar(
            select(Commitment)
            .where(
                Commitment.user_id == user.id,
                Commitment.status == "active",
                Commitment.starts_at.is_not(None),
                Commitment.starts_at > when,
            )
            .order_by(Commitment.starts_at.asc())
            .limit(1)
        )
        events = list(db.scalars(
            select(Event)
            .where(Event.user_id == user.id)
            .order_by(Event.occurred_at.desc(), Event.created_at.desc())
            .limit(MAX_RECENT_EVENTS)
        ))
        attention_rows = list(db.scalars(
            select(AttentionItem)
            .where(
                AttentionItem.user_id == user.id,
                AttentionItem.status.in_((AttentionItemStatus.pending.value, AttentionItemStatus.eligible.value)),
                or_(AttentionItem.expires_at.is_(None), AttentionItem.expires_at >= when),
            )
            .order_by(AttentionItem.priority.desc(), AttentionItem.created_at.asc())
            .limit(MAX_ATTENTION_REFS)
        ))
        active_proposal = db.scalar(
            select(PlanProposal)
            .where(
                PlanProposal.user_id == user.id,
                PlanProposal.status.in_(("DRAFT", "PRESENTED", "MODIFIED")),
                PlanProposal.expires_at >= when,
            )
            .order_by(PlanProposal.created_at.desc())
            .limit(1)
        )
        open_rows = list(db.scalars(
            select(OpenThread)
            .where(OpenThread.user_id == user.id, OpenThread.status == OpenThreadStatus.open.value)
            .order_by(OpenThread.updated_at.desc())
            .limit(MAX_OPEN_THREAD_REFS)
        ))

        evaluation_context = ProspectiveEvaluationContext(
            now=when,
            manual=manual_trigger,
            location=None if broad_context == BroadContext.unknown else broad_context.value,
            goal_states=goal_states or {},
            trigger_observations=trigger_observations or {},
        )
        prospective_rows = list(db.scalars(
            select(ProspectiveThread)
            .where(
                ProspectiveThread.user_id == user.id,
                ProspectiveThread.status == ProspectiveThreadStatus.open.value,
            )
            .order_by(ProspectiveThread.earliest_relevance.asc(), ProspectiveThread.created_at.asc())
            .limit(64)
        ))
        eligible_refs: list[SituationReference] = []
        for row in prospective_rows:
            eligibility = self.eligibility_service.evaluate(row, evaluation_context)
            if eligibility.eligible:
                eligible_refs.append(
                    SituationReference(
                        ref_type="prospective_thread",
                        ref_id=row.id,
                        label=row.subject,
                        status=row.status,
                        detail=eligibility.reason_code,
                    )
                )
                if len(eligible_refs) >= MAX_PROSPECTIVE_REFS:
                    break

        snapshot = GlobalWorkspace(
            snapshot_ref=f"situation:{uuid4()}",
            created_at=when,
            current_time=when,
            broad_context=broad_context,
            foreground_workspace=foreground,
            active_workspaces=workspace_refs,
            current_plan_block=(
                SituationReference(
                    ref_type="plan_block", ref_id=current_block.id, label=current_block.title,
                    status=current_block.status, detail=current_block.domain,
                ) if current_block else None
            ),
            next_commitment=(
                SituationReference(
                    ref_type="commitment", ref_id=next_commitment.id, label=next_commitment.title,
                    status=next_commitment.status, detail=next_commitment.location,
                ) if next_commitment else None
            ),
            recent_events=tuple(
                SituationReference(
                    ref_type="event", ref_id=row.id, label=row.event_type,
                    status=None, detail=f"{row.aggregate_type}:{row.aggregate_id}",
                )
                for row in events
            ),
            temporary_constraints=temporary_constraints,
            self_reported_state=self_reported_state,
            active_proposal_ref=active_proposal.id if active_proposal else None,
            pending_attention=tuple(
                SituationReference(
                    ref_type="attention_item", ref_id=row.id, label=row.subject,
                    status=row.status, detail=row.action,
                )
                for row in attention_rows
            ),
            open_threads=tuple(
                SituationReference(
                    ref_type="open_thread", ref_id=row.id, label=row.subject,
                    status=row.status, detail=row.domain,
                )
                for row in open_rows
            ),
            eligible_prospective_threads=tuple(eligible_refs),
            conversation_thread_ref=conversation_thread_ref,
            world_revision=user.world_revision,
        )
        logger.info(
            "global_workspace_built",
            extra={
                "user_id": user.id,
                "world_revision": user.world_revision,
                "workspace_count": len(workspace_refs),
                "event_count": len(events),
                "attention_count": len(attention_rows),
                "eligible_thread_count": len(eligible_refs),
            },
        )
        return snapshot
