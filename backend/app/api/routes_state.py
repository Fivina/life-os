import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.events.idempotency import get_replay_or_conflict, store_idempotent_response
from app.state.schemas import LatestStateRead, StateObservationBatchRead, StateObservationCreate
from app.state.service import create_observations, latest_check_in, latest_state

router = APIRouter(prefix="/state", tags=["state"])


def _stable_payload_json(payload: StateObservationCreate) -> str:
    return json.dumps(payload.model_dump(mode="json", exclude_none=True), sort_keys=True)


@router.post("/observations", response_model=StateObservationBatchRead)
def create_state_observation_endpoint(
    payload: StateObservationCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    payload_json = _stable_payload_json(payload)
    replay = get_replay_or_conflict(
        db,
        user,
        mutation_key=idempotency_key,
        endpoint="/api/v1/state/observations",
        payload_json=payload_json,
    )
    if replay is not None:
        return replay.response_body

    observations = create_observations(db, user, payload)
    if not observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one observation value is required.",
        )

    response = StateObservationBatchRead(observations=observations, world_revision=user.world_revision)
    response_body = response.model_dump(mode="json")
    store_idempotent_response(
        db,
        user,
        mutation_key=idempotency_key,
        endpoint="/api/v1/state/observations",
        payload_json=payload_json,
        response_body=response_body,
    )
    db.commit()
    return response_body


@router.get("/latest", response_model=LatestStateRead)
def get_latest_state_endpoint(
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> LatestStateRead:
    values = latest_state(db, user)
    return LatestStateRead(values=values, check_in=latest_check_in(values), world_revision=user.world_revision)
