from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.database.models import UserProfile
from app.database.session import get_db
from app.self_core.morning import MorningBriefingBuilder
from app.self_core.schemas import MorningBriefingResponse


router = APIRouter(prefix="/self-core", tags=["self-core"])
logger = get_logger(__name__)


@router.post("/morning", response_model=MorningBriefingResponse)
def morning_briefing(
    timezone: str = "Europe/Berlin",
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> MorningBriefingResponse:
    result = MorningBriefingBuilder().build(db, user, timezone=timezone)
    db.commit()
    logger.info(
        "morning_briefing_reused" if result.reused else "morning_briefing_generated",
        extra={"user_id": user.id, "fingerprint": result.context.fingerprint, "plan_id": result.context.plan_id},
    )
    return result
