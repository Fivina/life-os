import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.commitments.schemas import CommitmentCreate, CommitmentRead, CommitmentUpdate, StatusCommand
from app.commitments.service import create_commitment as create_commitment_service
from app.commitments.service import get_commitment, list_commitments, transition_commitment, update_commitment as update_commitment_service
from app.database.models import UserProfile
from app.database.session import get_db
from app.events.idempotency import get_replay_or_conflict, store_idempotent_response

router = APIRouter(prefix="/commitments", tags=["commitments"])


def _payload_json(payload) -> str:
    return json.dumps(payload.model_dump(mode="json", exclude_none=True), sort_keys=True)


def _read_response(commitment, world_revision: int | None = None) -> dict:
    body = CommitmentRead.model_validate(commitment).model_dump(mode="json")
    body["world_revision"] = world_revision
    return body


@router.post("", response_model=CommitmentRead)
def create_commitment(
    payload: CommitmentCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    payload_json = _payload_json(payload)
    replay = get_replay_or_conflict(db, user, mutation_key=idempotency_key, endpoint="/api/v1/commitments", payload_json=payload_json)
    if replay is not None:
        return replay.response_body

    commitment = create_commitment_service(db, user, payload)
    response = _read_response(commitment, user.world_revision)
    store_idempotent_response(db, user, mutation_key=idempotency_key, endpoint="/api/v1/commitments", payload_json=payload_json, response_body=response)
    db.commit()
    return response


@router.get("", response_model=list[CommitmentRead])
def get_commitments(
    status: str | None = None,
    level: str | None = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return list_commitments(db, user, status_filter=status, level=level, starts_from=starts_from, starts_to=starts_to)


@router.get("/{commitment_id}", response_model=CommitmentRead)
def get_commitment_endpoint(
    commitment_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return get_commitment(db, user, commitment_id)


@router.patch("/{commitment_id}", response_model=CommitmentRead)
def update_commitment(
    commitment_id: str,
    payload: CommitmentUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    commitment = update_commitment_service(db, user, commitment_id, payload)
    response = _read_response(commitment, user.world_revision)
    db.commit()
    return response


def _status_command(
    *,
    commitment_id: str,
    target_status: str,
    payload: StatusCommand,
    idempotency_key: str | None,
    db: Session,
    user: UserProfile,
) -> dict:
    endpoint = f"/api/v1/commitments/{commitment_id}/{target_status}"
    payload_json = _payload_json(payload)
    replay = get_replay_or_conflict(db, user, mutation_key=idempotency_key, endpoint=endpoint, payload_json=payload_json)
    if replay is not None:
        return replay.response_body
    commitment = transition_commitment(db, user, commitment_id, target_status, payload.expected_version)
    response = _read_response(commitment, user.world_revision)
    store_idempotent_response(db, user, mutation_key=idempotency_key, endpoint=endpoint, payload_json=payload_json, response_body=response)
    db.commit()
    return response


@router.post("/{commitment_id}/complete", response_model=CommitmentRead)
def complete_commitment(
    commitment_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(commitment_id=commitment_id, target_status="completed", payload=payload, idempotency_key=idempotency_key, db=db, user=user)


@router.post("/{commitment_id}/cancel", response_model=CommitmentRead)
def cancel_commitment(
    commitment_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(commitment_id=commitment_id, target_status="cancelled", payload=payload, idempotency_key=idempotency_key, db=db, user=user)


@router.post("/{commitment_id}/miss", response_model=CommitmentRead)
def miss_commitment(
    commitment_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(commitment_id=commitment_id, target_status="missed", payload=payload, idempotency_key=idempotency_key, db=db, user=user)
