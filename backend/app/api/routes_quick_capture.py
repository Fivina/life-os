from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.capture.schemas import QuickCaptureApply, QuickCaptureCreate, QuickCaptureRead
from app.capture.service import QuickCaptureService
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db


router = APIRouter(prefix="/quick-capture", tags=["quick-capture"])


@router.post("", response_model=QuickCaptureRead)
def create_quick_capture(
    payload: QuickCaptureCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = QuickCaptureService(settings).capture(db, user, payload, idempotency_key=idempotency_key)
    db.commit()
    return result


@router.get("", response_model=list[QuickCaptureRead])
def list_quick_captures(
    limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    return QuickCaptureService(settings).list(db, user, limit=limit)


@router.get("/{capture_id}", response_model=QuickCaptureRead)
def get_quick_capture(
    capture_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    return QuickCaptureService(settings).get(db, user, capture_id)


@router.post("/{capture_id}/apply", response_model=QuickCaptureRead)
def apply_quick_capture(
    capture_id: str, payload: QuickCaptureApply, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = QuickCaptureService(settings).apply(
        db, user, capture_id, edited_payload=payload.edited_payload, expected_version=payload.expected_version,
    )
    db.commit()
    return result


@router.post("/{capture_id}/reject", response_model=QuickCaptureRead)
def reject_quick_capture(
    capture_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    result = QuickCaptureService(settings).reject(db, user, capture_id)
    db.commit()
    return result
