from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionUpdate
from app.core.lifecycle import ACTION_LEVELS, DOMAINS, validate_choice, validate_status_transition
from app.database.models import Action, UserProfile
from app.events.service import append_event


def _read_action(db: Session, user: UserProfile, action_id: str) -> Action:
    action = db.scalar(select(Action).where(Action.id == action_id, Action.user_id == user.id))
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")
    return action


def _validate_windows(
    earliest_start: datetime | None,
    latest_start: datetime | None,
    deadline: datetime | None,
    duration_min_minutes: int | None,
    duration_max_minutes: int | None,
) -> None:
    if earliest_start and latest_start and earliest_start > latest_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="earliest_start must be before latest_start.")
    if latest_start and deadline and latest_start > deadline:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="latest_start must be before deadline.")
    if duration_min_minutes and duration_max_minutes and duration_min_minutes > duration_max_minutes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="duration_min_minutes must be <= duration_max_minutes.")


def create_action(db: Session, user: UserProfile, payload: ActionCreate) -> Action:
    domain = validate_choice(payload.domain, DOMAINS, "domain")
    level = validate_choice(payload.level, ACTION_LEVELS, "level")
    _validate_windows(payload.earliest_start, payload.latest_start, payload.deadline, payload.duration_min_minutes, payload.duration_max_minutes)

    action = Action(
        user_id=user.id,
        title=payload.title,
        domain=domain,
        level=level,
        description=payload.description,
        earliest_start=payload.earliest_start,
        latest_start=payload.latest_start,
        deadline=payload.deadline,
        estimated_minutes=payload.estimated_minutes,
        duration_min_minutes=payload.duration_min_minutes,
        duration_max_minutes=payload.duration_max_minutes,
        location=payload.location,
        context=payload.context,
        metadata_json=payload.metadata_json,
        candidate_group_id=payload.candidate_group_id,
        variant_type=payload.variant_type,
        variant_rank=payload.variant_rank,
        mutually_exclusive=payload.mutually_exclusive,
        variant_quality=payload.variant_quality,
        requirement_key=payload.requirement_key,
        source_entity_type=payload.source_entity_type,
        source_entity_id=payload.source_entity_id,
        goal_id=payload.goal_id,
        trajectory_id=payload.trajectory_id,
        generated_reason=payload.generated_reason,
        generation_version=payload.generation_version,
        planning_priority=payload.planning_priority,
        status="active",
    )
    db.add(action)
    db.flush()
    append_event(
        db,
        user,
        event_type="action.created",
        aggregate_type="action",
        aggregate_id=action.id,
        payload={"action_id": action.id, "title": action.title, "domain": action.domain, "level": action.level},
        outbox=True,
    )
    return action


def list_actions(
    db: Session,
    user: UserProfile,
    *,
    status_filter: str | None = None,
    domain: str | None = None,
    level: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    planning_pool: bool = False,
) -> list[Action]:
    query = select(Action).where(Action.user_id == user.id)
    if status_filter:
        query = query.where(Action.status == status_filter)
    if domain:
        query = query.where(Action.domain == domain)
    if level:
        query = query.where(Action.level == level)
    if deadline_from:
        query = query.where(Action.deadline >= deadline_from)
    if deadline_to:
        query = query.where(Action.deadline <= deadline_to)
    if planning_pool:
        query = query.where(Action.status == "active", Action.scheduled_start.is_(None), Action.scheduled_end.is_(None))
    return list(db.scalars(query.order_by(Action.deadline.asc().nulls_last(), Action.created_at.desc())).all())


def get_action(db: Session, user: UserProfile, action_id: str) -> Action:
    return _read_action(db, user, action_id)


def update_action(db: Session, user: UserProfile, action_id: str, payload: ActionUpdate) -> Action:
    action = _read_action(db, user, action_id)
    if action.version != payload.expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Action version conflict. Current version is {action.version}.")

    update_data = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if "domain" in update_data:
        update_data["domain"] = validate_choice(update_data["domain"], DOMAINS, "domain")
    if "level" in update_data:
        update_data["level"] = validate_choice(update_data["level"], ACTION_LEVELS, "level")

    next_earliest = update_data.get("earliest_start", action.earliest_start)
    next_latest = update_data.get("latest_start", action.latest_start)
    next_deadline = update_data.get("deadline", action.deadline)
    next_min = update_data.get("duration_min_minutes", action.duration_min_minutes)
    next_max = update_data.get("duration_max_minutes", action.duration_max_minutes)
    _validate_windows(next_earliest, next_latest, next_deadline, next_min, next_max)

    for key, value in update_data.items():
        setattr(action, key, value)
    action.version += 1

    append_event(
        db,
        user,
        event_type="action.updated",
        aggregate_type="action",
        aggregate_id=action.id,
        payload={"action_id": action.id, "fields": sorted(update_data.keys())},
        outbox=True,
    )
    return action


def transition_action(db: Session, user: UserProfile, action_id: str, target_status: str, expected_version: int) -> Action:
    action = _read_action(db, user, action_id)
    if action.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Action version conflict. Current version is {action.version}.")
    next_status = validate_status_transition(action.status, target_status)
    action.status = next_status
    action.version += 1
    append_event(
        db,
        user,
        event_type=f"action.{next_status}",
        aggregate_type="action",
        aggregate_id=action.id,
        payload={"action_id": action.id, "status": next_status},
        outbox=True,
    )
    return action
