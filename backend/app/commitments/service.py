from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commitments.schemas import CommitmentCreate, CommitmentUpdate
from app.core.lifecycle import COMMITMENT_LEVELS, COMMITMENT_TYPES, validate_choice, validate_status_transition
from app.database.models import Commitment, UserProfile
from app.events.service import append_event


def _read_commitment(db: Session, user: UserProfile, commitment_id: str) -> Commitment:
    commitment = db.scalar(
        select(Commitment).where(Commitment.id == commitment_id, Commitment.user_id == user.id)
    )
    if commitment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found.")
    return commitment


def _validate_timing(starts_at: datetime | None, ends_at: datetime | None) -> None:
    if starts_at is None or ends_at is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Commitment requires start and end.")
    left, right = _comparison_pair(starts_at, ends_at)
    if left >= right:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="starts_at must be before ends_at.")


def _comparison_pair(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    if (left.tzinfo is None) != (right.tzinfo is None):
        return left.replace(tzinfo=None), right.replace(tzinfo=None)
    return left, right


def _hard_overlap_conflicts(
    db: Session,
    user: UserProfile,
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_id: str | None = None,
) -> list[Commitment]:
    query = (
        select(Commitment)
        .where(Commitment.user_id == user.id)
        .where(Commitment.status == "active")
        .where(Commitment.level == "hard")
        .where(Commitment.starts_at < ends_at)
        .where(Commitment.ends_at > starts_at)
    )
    if exclude_id is not None:
        query = query.where(Commitment.id != exclude_id)
    return list(db.scalars(query).all())


def ensure_no_hard_overlap(
    db: Session,
    user: UserProfile,
    *,
    level: str,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: str | None = None,
) -> None:
    if level != "hard":
        return
    conflicts = _hard_overlap_conflicts(db, user, starts_at, ends_at, exclude_id=exclude_id)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Hard commitment overlaps an existing active hard commitment.",
                "conflicts": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "starts_at": item.starts_at.isoformat() if item.starts_at else None,
                        "ends_at": item.ends_at.isoformat() if item.ends_at else None,
                    }
                    for item in conflicts
                ],
            },
        )


def create_commitment(db: Session, user: UserProfile, payload: CommitmentCreate) -> Commitment:
    level = validate_choice(payload.level, COMMITMENT_LEVELS, "level")
    commitment_type = validate_choice(payload.commitment_type, COMMITMENT_TYPES, "commitment_type")
    _validate_timing(payload.starts_at, payload.ends_at)
    ensure_no_hard_overlap(db, user, level=level, starts_at=payload.starts_at, ends_at=payload.ends_at)

    commitment = Commitment(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        level=level,
        commitment_type=commitment_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        timezone=payload.timezone,
        all_day=payload.all_day,
        location=payload.location,
        recurrence=payload.recurrence,
        source=payload.source,
        notes=payload.notes,
    )
    db.add(commitment)
    db.flush()
    append_event(
        db,
        user,
        event_type="commitment.created",
        aggregate_type="commitment",
        aggregate_id=commitment.id,
        payload={"commitment_id": commitment.id, "title": commitment.title, "level": commitment.level},
        outbox=True,
    )
    return commitment


def list_commitments(
    db: Session,
    user: UserProfile,
    *,
    status_filter: str | None = None,
    level: str | None = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
) -> list[Commitment]:
    query = select(Commitment).where(Commitment.user_id == user.id)
    if status_filter:
        query = query.where(Commitment.status == status_filter)
    if level:
        query = query.where(Commitment.level == level)
    if starts_from:
        query = query.where(Commitment.ends_at >= starts_from)
    if starts_to:
        query = query.where(Commitment.starts_at <= starts_to)
    return list(db.scalars(query.order_by(Commitment.starts_at.asc(), Commitment.created_at.asc())).all())


def get_commitment(db: Session, user: UserProfile, commitment_id: str) -> Commitment:
    return _read_commitment(db, user, commitment_id)


def update_commitment(db: Session, user: UserProfile, commitment_id: str, payload: CommitmentUpdate) -> Commitment:
    commitment = _read_commitment(db, user, commitment_id)
    if commitment.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Commitment version conflict. Current version is {commitment.version}.",
        )

    update_data = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    next_level = validate_choice(update_data.get("level", commitment.level), COMMITMENT_LEVELS, "level")
    if "commitment_type" in update_data:
        update_data["commitment_type"] = validate_choice(update_data["commitment_type"], COMMITMENT_TYPES, "commitment_type")
    next_start = update_data.get("starts_at", commitment.starts_at)
    next_end = update_data.get("ends_at", commitment.ends_at)
    _validate_timing(next_start, next_end)
    ensure_no_hard_overlap(db, user, level=next_level, starts_at=next_start, ends_at=next_end, exclude_id=commitment.id)

    if "level" in update_data:
        update_data["level"] = next_level
    for key, value in update_data.items():
        setattr(commitment, key, value)
    commitment.version += 1

    append_event(
        db,
        user,
        event_type="commitment.updated",
        aggregate_type="commitment",
        aggregate_id=commitment.id,
        payload={"commitment_id": commitment.id, "fields": sorted(update_data.keys())},
        outbox=True,
    )
    return commitment


def transition_commitment(db: Session, user: UserProfile, commitment_id: str, target_status: str, expected_version: int) -> Commitment:
    commitment = _read_commitment(db, user, commitment_id)
    if commitment.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Commitment version conflict. Current version is {commitment.version}.",
        )
    next_status = validate_status_transition(commitment.status, target_status)
    commitment.status = next_status
    commitment.version += 1
    append_event(
        db,
        user,
        event_type=f"commitment.{next_status}",
        aggregate_type="commitment",
        aggregate_id=commitment.id,
        payload={"commitment_id": commitment.id, "status": next_status},
        outbox=True,
    )
    return commitment
