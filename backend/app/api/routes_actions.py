import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionRead, ActionUpdate, StatusCommand
from app.actions.service import create_action as create_action_service
from app.actions.service import get_action, list_actions, transition_action, update_action as update_action_service
from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.events.idempotency import get_replay_or_conflict, store_idempotent_response

router = APIRouter(prefix="/actions", tags=["actions"])


def _payload_json(payload) -> str:
    return json.dumps(payload.model_dump(mode="json", exclude_none=True), sort_keys=True)


def _read_response(action, world_revision: int | None = None) -> dict:
    body = ActionRead.model_validate(action).model_dump(mode="json")
    body["world_revision"] = world_revision
    return body


@router.post("", response_model=ActionRead)
def create_action(
    payload: ActionCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    payload_json = _payload_json(payload)
    replay = get_replay_or_conflict(db, user, mutation_key=idempotency_key, endpoint="/api/v1/actions", payload_json=payload_json)
    if replay is not None:
        return replay.response_body
    action = create_action_service(db, user, payload)
    response = _read_response(action, user.world_revision)
    store_idempotent_response(db, user, mutation_key=idempotency_key, endpoint="/api/v1/actions", payload_json=payload_json, response_body=response)
    db.commit()
    return response


@router.get("", response_model=list[ActionRead])
def get_actions(
    status: str | None = None,
    domain: str | None = None,
    level: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    planning_pool: bool = False,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return list_actions(
        db,
        user,
        status_filter=status,
        domain=domain,
        level=level,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        planning_pool=planning_pool,
    )


@router.get("/{action_id}", response_model=ActionRead)
def get_action_endpoint(action_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return get_action(db, user, action_id)


@router.patch("/{action_id}", response_model=ActionRead)
def update_action(
    action_id: str,
    payload: ActionUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    action = update_action_service(db, user, action_id, payload)
    response = _read_response(action, user.world_revision)
    db.commit()
    return response


def _status_command(
    *,
    action_id: str,
    target_status: str,
    payload: StatusCommand,
    idempotency_key: str | None,
    db: Session,
    user: UserProfile,
) -> dict:
    endpoint = f"/api/v1/actions/{action_id}/{target_status}"
    payload_json = _payload_json(payload)
    replay = get_replay_or_conflict(db, user, mutation_key=idempotency_key, endpoint=endpoint, payload_json=payload_json)
    if replay is not None:
        return replay.response_body
    action = transition_action(db, user, action_id, target_status, payload.expected_version)
    response = _read_response(action, user.world_revision)
    store_idempotent_response(db, user, mutation_key=idempotency_key, endpoint=endpoint, payload_json=payload_json, response_body=response)
    db.commit()
    return response


@router.post("/{action_id}/complete", response_model=ActionRead)
def complete_action(
    action_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(action_id=action_id, target_status="completed", payload=payload, idempotency_key=idempotency_key, db=db, user=user)


@router.post("/{action_id}/cancel", response_model=ActionRead)
def cancel_action(
    action_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(action_id=action_id, target_status="cancelled", payload=payload, idempotency_key=idempotency_key, db=db, user=user)


@router.post("/{action_id}/miss", response_model=ActionRead)
def miss_action(
    action_id: str,
    payload: StatusCommand,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    return _status_command(action_id=action_id, target_status="missed", payload=payload, idempotency_key=idempotency_key, db=db, user=user)
