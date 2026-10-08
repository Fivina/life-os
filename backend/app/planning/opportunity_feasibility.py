from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Action, Commitment, Opportunity, PlanBlock, UserProfile
from app.strategy.monitor import StrategicMonitor


class OpportunityFeasibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feasible: bool
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    conflict_refs: list[dict[str, str]] = Field(default_factory=list)
    flexible_study_minutes: int = 0
    strategic_safe: bool | None = None
    requires_plan_proposal: bool = False
    current_plan_mutated: Literal[False] = False


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def evaluate_opportunity(db: Session, user: UserProfile, opportunity: Opportunity) -> OpportunityFeasibility:
    starts_at = _aware(opportunity.starts_at)
    ends_at = _aware(opportunity.ends_at) if opportunity.ends_at else starts_at + timedelta(hours=2)
    commitments = list(db.scalars(select(Commitment).where(
        Commitment.user_id == user.id,
        Commitment.status.in_(["active", "confirmed", "scheduled"]),
        Commitment.starts_at.is_not(None), Commitment.ends_at.is_not(None),
        Commitment.starts_at < ends_at, Commitment.ends_at > starts_at,
    )))
    blocks = list(db.scalars(select(PlanBlock).where(
        PlanBlock.user_id == user.id,
        PlanBlock.status.in_(["planned", "active"]),
        PlanBlock.starts_at < ends_at, PlanBlock.ends_at > starts_at,
    )))
    conflicts = ([{"type": "commitment", "id": row.id, "title": row.title} for row in commitments]
                 + [{"type": "plan_block", "id": row.id, "title": row.title} for row in blocks])
    protected = any(row.level == "hard" or row.commitment_type == "hard" for row in commitments)
    protected = protected or any(row.user_locked or not row.movable or row.commitment_level == "goal_critical" for row in blocks)
    if protected:
        return OpportunityFeasibility(feasible=False, status="PROTECTED_CONFLICT", reason_codes=["protected_calendar_conflict"], conflict_refs=conflicts)
    if not conflicts:
        return OpportunityFeasibility(feasible=True, status="CLEAN_SLOT", reason_codes=["available_window"])

    flexible_study = [row for row in blocks if row.domain == "learning" and row.movable and not row.user_locked]
    if len(flexible_study) != len(blocks) or commitments:
        return OpportunityFeasibility(feasible=False, status="CONFLICT", reason_codes=["non_study_conflict"], conflict_refs=conflicts)
    safe = _study_reallocation_safe(db, user, flexible_study)
    return OpportunityFeasibility(
        feasible=False,
        status="PROPOSAL_ELIGIBLE" if safe else "TRAJECTORY_UNSAFE",
        reason_codes=["flexible_study_requires_plan_proposal" if safe else "study_trajectory_not_safe"],
        conflict_refs=conflicts,
        flexible_study_minutes=sum(row.duration_minutes for row in flexible_study),
        strategic_safe=safe,
        requires_plan_proposal=safe,
    )


def _study_reallocation_safe(db: Session, user: UserProfile, blocks: list[PlanBlock]) -> bool:
    monitor = StrategicMonitor()
    for block in blocks:
        action = db.get(Action, block.action_id) if block.action_id else None
        if action is None or action.source_entity_type != "exam" or not action.source_entity_id:
            return False
        from app.database.models import Exam
        exam = db.get(Exam, action.source_entity_id)
        if exam is None or exam.user_id != user.id:
            return False
        snapshot = monitor.assess_exam(db, user, exam)
        if snapshot.buffer_minutes is None or snapshot.buffer_minutes < block.duration_minutes:
            return False
        deviation = monitor.deviation(snapshot, trigger="opportunity.feasibility")
        if deviation is not None and deviation.severity.value in {"HIGH", "CRITICAL"}:
            return False
    return bool(blocks)
