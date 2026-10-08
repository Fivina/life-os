from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.strategy.schemas import PlanProposalRead, ProposalModificationRequest, StrategicEvaluationRead
from app.strategy.service import PlanProposalService


router = APIRouter(prefix="/strategy", tags=["strategy"])


def get_service(settings: Settings = Depends(get_settings)) -> PlanProposalService:
    return PlanProposalService(settings)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    message = str(exc)
    code = status.HTTP_409_CONFLICT if "stale" in message.lower() or "expired" in message.lower() else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=message)


@router.post("/exams/{exam_id}/evaluate", response_model=StrategicEvaluationRead)
def evaluate_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> StrategicEvaluationRead:
    try:
        result = service.evaluate_exam(db, user, exam_id, trigger="manual")
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    db.commit()
    return result


@router.get("/proposals", response_model=list[PlanProposalRead])
def list_proposals(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> list[PlanProposalRead]:
    rows = service.list_active(db, user, limit=limit)
    db.commit()
    return [service.to_read(row) for row in rows]


@router.get("/proposals/{proposal_id}", response_model=PlanProposalRead)
def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> PlanProposalRead:
    try:
        row = service.get(db, user, proposal_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    db.commit()
    return service.to_read(row)


@router.get("/proposals/{proposal_id}/diff", response_model=dict)
def proposal_diff(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> dict:
    try:
        row = service.get(db, user, proposal_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return {
        "proposal_id": row.id,
        "current_plan_id": row.current_plan_id,
        "current_plan_version": row.current_plan_version,
        "changes": row.changes_json,
        "expected_effects": row.expected_effects_json,
        "tradeoffs": row.tradeoffs_json,
    }


@router.post("/proposals/{proposal_id}/present", response_model=PlanProposalRead)
def present_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> PlanProposalRead:
    try:
        row = service.present(db, user, proposal_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    db.commit()
    return service.to_read(row)


@router.post("/proposals/{proposal_id}/accept", response_model=PlanProposalRead)
def accept_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> PlanProposalRead:
    try:
        row = service.accept(db, user, proposal_id)
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _error(exc) from exc
    db.commit()
    return service.to_read(row)


@router.post("/proposals/{proposal_id}/modify", response_model=PlanProposalRead)
def modify_proposal(
    proposal_id: str,
    payload: ProposalModificationRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> PlanProposalRead:
    try:
        row = service.modify(db, user, proposal_id, payload)
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _error(exc) from exc
    db.commit()
    return service.to_read(row)


@router.post("/proposals/{proposal_id}/reject", response_model=PlanProposalRead)
def reject_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: PlanProposalService = Depends(get_service),
) -> PlanProposalRead:
    try:
        row = service.reject(db, user, proposal_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    db.commit()
    return service.to_read(row)
