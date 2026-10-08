from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.schemas import ActionRead
from app.actions.service import list_actions
from app.api.deps import get_current_user
from app.commitments.service import list_commitments
from app.database.models import UserProfile
from app.database.session import get_db
from app.planning.schemas import PlanRead
from app.planning.service import get_current_plan, plan_to_read

router = APIRouter(prefix="/calendar-projection", tags=["calendar"])


class CalendarCommitmentProjection(BaseModel):
    canonical_id: str
    canonical_type: str = "commitment"
    title: str
    starts_at: datetime
    ends_at: datetime
    status: str
    level: str
    commitment_type: str
    location: str | None
    source: str
    version: int


class CalendarProjectionRead(BaseModel):
    commitments: list[CalendarCommitmentProjection]
    planning_pool: list[ActionRead]
    world_revision: int
    current_plan: PlanRead | None = None


@router.get("", response_model=CalendarProjectionRead)
def get_calendar_projection(
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> CalendarProjectionRead:
    commitments = list_commitments(db, user, status_filter="active", starts_from=starts_from, starts_to=starts_to)
    planning_pool = list_actions(db, user, planning_pool=True)
    plan = get_current_plan(db, user)
    return CalendarProjectionRead(
        commitments=[
            CalendarCommitmentProjection(
                canonical_id=item.id,
                title=item.title,
                starts_at=item.starts_at,
                ends_at=item.ends_at,
                status=item.status,
                level=item.level,
                commitment_type=item.commitment_type,
                location=item.location,
                source=item.source,
                version=item.version,
            )
            for item in commitments
            if item.starts_at is not None and item.ends_at is not None
        ],
        planning_pool=planning_pool,
        world_revision=user.world_revision,
        current_plan=plan_to_read(plan, user.world_revision) if plan is not None else None,
    )
