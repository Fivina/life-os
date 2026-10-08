from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.memory.schemas import RecommendationCreate, RecommendationOutcomeCreate, RecommendationOutcomeRead, RecommendationRead
from app.recommendations import service


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationRead)
def create_recommendation(
    payload: RecommendationCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    data = payload if payload.idempotency_key or not idempotency_key else payload.model_copy(update={"idempotency_key": idempotency_key})
    result = service.create_recommendation(db, user, data)
    db.commit()
    return result


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_recommendations(db, user, limit=limit)


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(recommendation_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_recommendation(db, user, recommendation_id)


@router.post("/{recommendation_id}/outcomes", response_model=RecommendationOutcomeRead)
def record_outcome(recommendation_id: str, payload: RecommendationOutcomeCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    data = payload.model_copy(update={"recommendation_id": recommendation_id})
    result = service.record_outcome(db, user, data)
    db.commit()
    return result
