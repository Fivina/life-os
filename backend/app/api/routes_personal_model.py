from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.personal_model import service
from app.personal_model.retrieval import PatternRetrievalService
from app.personal_model.schemas import (
    PatternCorrectionRequest,
    PatternEvidenceRead,
    PersonalModelRefreshRead,
    PersonalModelSummaryRead,
    PersonalModelVersionRead,
    TrainingExampleRead,
)

router = APIRouter(prefix="/personal-model", tags=["personal-model"])


@router.get("/summary", response_model=PersonalModelSummaryRead)
def personal_model_summary(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.summary(db, user)


@router.get("/models", response_model=list[PersonalModelVersionRead])
def personal_models(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_models(db, user)


@router.get("/models/{model_id}", response_model=PersonalModelVersionRead)
def personal_model(model_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_model(db, user, model_id)


@router.get("/patterns", response_model=list[PatternEvidenceRead])
def personal_patterns(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_patterns(db, user)


@router.get("/patterns/relevant", response_model=list[PatternEvidenceRead])
def relevant_personal_patterns(
    domain: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return PatternRetrievalService().relevant(db, user, domain=domain, limit=limit)


@router.post("/patterns/{pattern_id}/correct", response_model=PatternEvidenceRead)
def correct_personal_pattern(
    pattern_id: str,
    payload: PatternCorrectionRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    result = service.correct_pattern(db, user, pattern_id, payload)
    db.commit()
    return result


@router.post("/refresh", response_model=PersonalModelRefreshRead)
def refresh_personal_models(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.refresh_personal_models(db, user)
    db.commit()
    return result


@router.get("/examples", response_model=list[TrainingExampleRead])
def personal_examples(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_examples(db, user, limit=limit)
