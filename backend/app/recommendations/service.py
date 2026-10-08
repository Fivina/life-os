from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Recommendation, RecommendationOption, RecommendationOutcome, UserProfile
from app.events.service import append_event
from app.memory.schemas import (
    RecommendationCreate,
    RecommendationOptionRead,
    RecommendationOutcomeCreate,
    RecommendationOutcomeRead,
    RecommendationRead,
)


def _read(db: Session, row: Recommendation) -> RecommendationRead:
    options = list(
        db.scalars(
            select(RecommendationOption)
            .where(RecommendationOption.recommendation_id == row.id, RecommendationOption.user_id == row.user_id)
            .order_by(RecommendationOption.rank.asc())
        ).all()
    )
    return RecommendationRead(
        id=row.id,
        domain=row.domain,
        kind=row.kind,
        title=row.title,
        reason=row.reason,
        context_snapshot=row.context_snapshot or {},
        status=row.status,
        created_at=row.created_at,
        options=[RecommendationOptionRead.model_validate(item) for item in options],
    )


def create_recommendation(db: Session, user: UserProfile, payload: RecommendationCreate) -> RecommendationRead:
    if payload.idempotency_key:
        existing = db.scalar(
            select(Recommendation).where(
                Recommendation.user_id == user.id,
                Recommendation.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            return _read(db, existing)
    ranks = [item.rank for item in payload.options]
    if len(ranks) != len(set(ranks)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Recommendation option ranks must be unique.")
    row = Recommendation(
        user_id=user.id,
        domain=payload.domain,
        kind=payload.kind,
        title=payload.title,
        reason=payload.reason,
        context_snapshot=payload.context_snapshot,
        status="created",
        idempotency_key=payload.idempotency_key,
    )
    db.add(row)
    db.flush()
    for option in payload.options:
        db.add(RecommendationOption(user_id=user.id, recommendation_id=row.id, **option.model_dump()))
    append_event(
        db,
        user,
        event_type="recommendation.created",
        aggregate_type="recommendation",
        aggregate_id=row.id,
        payload={"recommendation_id": row.id, "domain": row.domain, "kind": row.kind, "option_count": len(payload.options)},
        outbox=False,
        increment_world_revision=False,
    )
    db.flush()
    return _read(db, row)


def get_recommendation(db: Session, user: UserProfile, recommendation_id: str) -> RecommendationRead:
    row = db.scalar(select(Recommendation).where(Recommendation.id == recommendation_id, Recommendation.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
    return _read(db, row)


def list_recommendations(db: Session, user: UserProfile, *, limit: int = 50) -> list[RecommendationRead]:
    rows = list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.user_id == user.id)
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [_read(db, row) for row in rows]


def record_outcome(db: Session, user: UserProfile, payload: RecommendationOutcomeCreate) -> RecommendationOutcomeRead:
    if payload.idempotency_key:
        existing = db.scalar(
            select(RecommendationOutcome).where(
                RecommendationOutcome.user_id == user.id,
                RecommendationOutcome.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            return RecommendationOutcomeRead.model_validate(existing)
    recommendation = None
    if payload.recommendation_id:
        recommendation = db.scalar(
            select(Recommendation).where(Recommendation.id == payload.recommendation_id, Recommendation.user_id == user.id)
        )
        if recommendation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
    if payload.option_id:
        option = db.scalar(
            select(RecommendationOption).where(RecommendationOption.id == payload.option_id, RecommendationOption.user_id == user.id)
        )
        if option is None or (recommendation is not None and option.recommendation_id != recommendation.id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation option not found.")
    accepted = payload.accepted
    if accepted is None:
        accepted = True if payload.outcome in {"accepted", "completed"} else False if payload.outcome in {"rejected", "abandoned"} else None
    row = RecommendationOutcome(**(payload.model_dump(exclude={"accepted"}) | {"accepted": accepted}), user_id=user.id, observed_at=datetime.now(UTC))
    db.add(row)
    if recommendation is not None:
        recommendation.status = payload.outcome
        recommendation.version += 1
    db.flush()
    event_type = f"recommendation.{payload.outcome}" if payload.outcome in {"shown", "opened", "accepted", "rejected", "modified", "completed", "abandoned"} else "recommendation.outcome_recorded"
    append_event(
        db,
        user,
        event_type=event_type,
        aggregate_type="recommendation_outcome",
        aggregate_id=row.id,
        payload={
            "outcome_id": row.id,
            "recommendation_id": row.recommendation_id,
            "option_id": row.option_id,
            "domain": row.domain,
            "outcome": row.outcome,
            "accepted": row.accepted,
        },
        outbox=False,
        increment_world_revision=False,
    )
    from app.memory.jobs import enqueue

    enqueue(
        db,
        user,
        job_type="recommendation_outcome.process",
        source_type="recommendation_outcome",
        source_id=row.id,
        payload={"recommendation_id": row.recommendation_id, "domain": row.domain},
    )
    db.flush()
    return RecommendationOutcomeRead.model_validate(row)


def list_outcomes(db: Session, user: UserProfile, *, limit: int = 50) -> list[RecommendationOutcomeRead]:
    rows = list(
        db.scalars(
            select(RecommendationOutcome)
            .where(RecommendationOutcome.user_id == user.id)
            .order_by(RecommendationOutcome.observed_at.desc())
            .limit(limit)
        ).all()
    )
    return [RecommendationOutcomeRead.model_validate(row) for row in rows]
