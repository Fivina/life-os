from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.review.schemas import ReviewItemRead, ReviewResolve, ReviewResolutionRead
from app.review.service import ReviewQueueService


router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_model=list[ReviewItemRead])
def list_review_items(
    status: str = Query(default="PENDING"), limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
):
    result = ReviewQueueService().list(db, user, status_filter=status, limit=limit)
    db.commit()
    return result


@router.get("/{item_id}", response_model=ReviewItemRead)
def get_review_item(item_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return ReviewQueueService().get(db, user, item_id)


@router.post("/{item_id}/resolve", response_model=ReviewResolutionRead)
def resolve_review_item(
    item_id: str, payload: ReviewResolve, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
):
    result = ReviewQueueService().resolve(
        db, user, item_id, action=payload.action, edited_values=payload.edited_values, expected_version=payload.expected_version,
    )
    db.commit()
    return result
