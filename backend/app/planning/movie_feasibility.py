from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.database.models import Commitment, PlanBlock, UserProfile
from app.movies.schemas import Showtime, ShowtimeOptionRead


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def evaluate_movie_showtime(db: Session, user: UserProfile, showtime: Showtime, *, default_runtime_minutes: int = 150) -> ShowtimeOptionRead:
    starts_at = _aware(showtime.starts_at)
    ends_at = _aware(showtime.ends_at) if showtime.ends_at else starts_at + timedelta(minutes=default_runtime_minutes)
    commitments = list(db.scalars(select(Commitment).where(
        Commitment.user_id == user.id,
        Commitment.status.in_(["active", "confirmed", "scheduled"]),
        Commitment.starts_at.is_not(None),
        Commitment.ends_at.is_not(None),
        Commitment.starts_at < ends_at,
        Commitment.ends_at > starts_at,
    )))
    blocks = list(db.scalars(select(PlanBlock).where(
        PlanBlock.user_id == user.id,
        PlanBlock.status.in_(["planned", "active"]),
        PlanBlock.starts_at < ends_at,
        PlanBlock.ends_at > starts_at,
    )))
    conflict_labels = [f"Commitment: {row.title}" for row in commitments] + [f"Plan: {row.title}" for row in blocks]
    protected = any(row.level == "hard" or row.commitment_type == "hard" for row in commitments) or any(row.user_locked or not row.movable for row in blocks)
    reasons = [] if not conflict_labels else ["schedule_conflict"]
    if protected:
        reasons.append("protected_calendar_change_required")
    return ShowtimeOptionRead(
        showtime=showtime,
        feasible=not conflict_labels,
        reason_codes=reasons or ["available_window"],
        conflicts=conflict_labels,
        requires_plan_proposal=protected,
    )
