from hashlib import sha256

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import IdempotencyRecord, UserProfile


def request_hash(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


def get_replay_or_conflict(
    db: Session,
    user: UserProfile,
    *,
    mutation_key: str | None,
    endpoint: str,
    payload_json: str,
) -> IdempotencyRecord | None:
    if not mutation_key:
        return None

    existing = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.user_id == user.id, IdempotencyRecord.mutation_key == mutation_key)
        .one_or_none()
    )
    if existing is None:
        return None

    if existing.endpoint != endpoint or existing.request_hash != request_hash(payload_json):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different mutation.",
        )
    return existing


def store_idempotent_response(
    db: Session,
    user: UserProfile,
    *,
    mutation_key: str | None,
    endpoint: str,
    payload_json: str,
    response_body: dict,
    status_code: int = 200,
) -> None:
    if not mutation_key:
        return

    db.add(
        IdempotencyRecord(
            user_id=user.id,
            mutation_key=mutation_key,
            endpoint=endpoint,
            request_hash=request_hash(payload_json),
            response_body=response_body,
            status_code=status_code,
        )
    )
