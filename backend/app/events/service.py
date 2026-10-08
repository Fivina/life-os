from sqlalchemy.orm import Session

from app.database.models import Event, OutboxEvent, UserProfile, WorldRevision


def append_event(
    db: Session,
    user: UserProfile,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    outbox: bool = True,
    increment_world_revision: bool = True,
) -> Event:
    if increment_world_revision:
        user.world_revision += 1
        user.version += 1

    event = Event(
        user_id=user.id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        world_revision=user.world_revision,
        payload=payload,
    )
    db.add(event)
    db.flush()

    if increment_world_revision:
        revision = WorldRevision(
            user_id=user.id,
            revision=user.world_revision,
            event_id=event.id,
            reason=event_type,
        )
        db.add(revision)

    if outbox:
        db.add(
            OutboxEvent(
                user_id=user.id,
                event_id=event.id,
                event_type=event_type,
                payload=payload,
            )
        )

    return event
