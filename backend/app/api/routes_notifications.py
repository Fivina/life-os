from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.notifications import service
from app.notifications.schemas import NotificationIntentRead, TestNotificationCreate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test", response_model=NotificationIntentRead)
def create_test_notification(
    payload: TestNotificationCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return service.create_test_notification(db, user, payload)
