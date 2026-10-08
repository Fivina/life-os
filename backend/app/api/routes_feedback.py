from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.feedback.quality import IntelligenceQualityService
from app.feedback.schemas import (
    FeedbackClarificationInput,
    FeedbackResponseInput,
    FeedbackSessionState,
    FeedbackStartRequest,
    IntelligenceQualitySummary,
    QualityFilter,
)
from app.feedback.service import FeedbackService


router = APIRouter(prefix="/feedback", tags=["feedback"])


def get_feedback_service(settings: Settings = Depends(get_settings)) -> FeedbackService:
    return FeedbackService(settings)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.post("/start", response_model=FeedbackSessionState)
def start_feedback(
    payload: FeedbackStartRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        result = service.start_from_command(
            db,
            user,
            command=payload.command,
            parent_conversation_id=payload.parent_conversation_id,
            attention_item_id=payload.attention_item_id,
        )
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return result


@router.get("/active", response_model=FeedbackSessionState)
def active_feedback(
    conversation_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    session = service.get_active(db, user, conversation_id=conversation_id)
    return service.state(db, user, session) if session else FeedbackSessionState(result_code="NO_ACTIVE_SESSION")


@router.get("/sessions/{session_id}", response_model=FeedbackSessionState)
def get_feedback_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        return service.state(db, user, service.get(db, user, session_id))
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc


@router.get("/sessions/{session_id}/next-question", response_model=FeedbackSessionState)
def next_feedback_question(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        return service.state(db, user, service.get(db, user, session_id))
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc


@router.post("/sessions/{session_id}/clarification", response_model=FeedbackSessionState)
def submit_feedback_clarification(
    session_id: str,
    payload: FeedbackClarificationInput,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        result = service.submit_clarification(db, user, session_id, answer=payload.answer)
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return result


@router.post("/sessions/{session_id}/responses", response_model=FeedbackSessionState)
def submit_feedback_response(
    session_id: str,
    payload: FeedbackResponseInput,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        result = service.submit_response(db, user, session_id, payload)
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return result


@router.post("/sessions/{session_id}/complete", response_model=FeedbackSessionState)
def complete_feedback(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        result = service.complete(db, user, session_id)
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return result


@router.post("/sessions/{session_id}/cancel", response_model=FeedbackSessionState)
def cancel_feedback(
    session_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackSessionState:
    try:
        result = service.cancel(db, user, session_id)
    except (LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return result


@router.get("/quality", response_model=IntelligenceQualitySummary)
def feedback_quality(
    days: int | None = Query(default=None, ge=1, le=3650),
    provider: str | None = Query(default=None),
    model_version: str | None = Query(default=None),
    policy_version: str | None = Query(default=None),
    decision_family: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> IntelligenceQualitySummary:
    return IntelligenceQualityService().summarize(
        db,
        user,
        filters=QualityFilter(
            days=days,
            provider=provider,
            model_version=model_version,
            policy_version=policy_version,
            decision_family=decision_family,
        ),
    )
