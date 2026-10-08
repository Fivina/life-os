from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.planning.control_loop import evaluate_day
from app.planning.schemas import ControlStatusRead, DayEvaluateRequest

router = APIRouter(prefix="/day", tags=["day"])


@router.post("/evaluate", response_model=ControlStatusRead)
def evaluate(
    payload: DayEvaluateRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    response = evaluate_day(db, user, planning_day=payload.planning_date, now=payload.now, trigger_reason=payload.trigger_reason)
    db.commit()
    return response
