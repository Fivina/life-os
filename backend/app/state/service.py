from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import StateObservation, UserProfile
from app.events.service import append_event
from app.state.schemas import LatestCheckInRead, StateObservationCreate


OBSERVATION_FIELDS = {
    "energy": "energy",
    "mental_state": "mental_state",
    "stress": "stress",
    "sleep_quality": "sleep_quality",
    "physical_readiness": "physical_readiness",
}


def create_observations(db: Session, user: UserProfile, payload: StateObservationCreate) -> list[StateObservation]:
    observed_at = payload.observed_at or datetime.now(UTC)
    observations: list[StateObservation] = []

    for field_name, observation_type in OBSERVATION_FIELDS.items():
        value = getattr(payload, field_name)
        if value is None:
            continue
        observation = StateObservation(
            user_id=user.id,
            observation_type=observation_type,
            value=value,
            observed_at=observed_at,
            source="manual",
            notes=payload.notes,
        )
        db.add(observation)
        observations.append(observation)

    if not observations:
        return []

    db.flush()
    append_event(
        db,
        user,
        event_type="state.observed",
        aggregate_type="state_observation_batch",
        aggregate_id=observations[0].id,
        payload={
            "observation_ids": [item.id for item in observations],
            "types": [item.observation_type for item in observations],
            "observed_at": observed_at.isoformat(),
        },
        outbox=True,
    )
    return observations


def latest_state(db: Session, user: UserProfile) -> dict[str, StateObservation]:
    values: dict[str, StateObservation] = {}
    rows = db.scalars(
        select(StateObservation)
        .where(StateObservation.user_id == user.id)
        .order_by(StateObservation.observed_at.desc(), StateObservation.created_at.desc())
    ).all()
    for observation in rows:
        values.setdefault(observation.observation_type, observation)
    return values


def latest_check_in(values: dict[str, StateObservation]) -> LatestCheckInRead | None:
    energy = values.get("energy")
    mental_state = values.get("mental_state")
    if energy is None and mental_state is None:
        return None

    observed_at_values = [
        observation.observed_at
        for observation in (energy, mental_state)
        if observation is not None
    ]
    observed_at = max(observed_at_values) if observed_at_values else None

    return LatestCheckInRead(
        energy=round(energy.value) if energy is not None else None,
        mental_state=round(mental_state.value) if mental_state is not None else None,
        observed_at=observed_at,
        observation_ids={
            observation_type: observation.id
            for observation_type, observation in (("energy", energy), ("mental_state", mental_state))
            if observation is not None
        },
    )
