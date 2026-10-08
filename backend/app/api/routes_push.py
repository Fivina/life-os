from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.notifications import service
from app.notifications.schemas import PushSubscriptionCreate, PushSubscriptionRead

router = APIRouter(prefix="/push", tags=["push"])


@router.post("/subscriptions", response_model=PushSubscriptionRead)
def create_push_subscription(
    payload: PushSubscriptionCreate,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return service.upsert_subscription(db, user, payload, user_agent=user_agent)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    service.unsubscribe(db, user, subscription_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
