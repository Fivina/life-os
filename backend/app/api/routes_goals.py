from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.goals.schemas import GoalCreate, GoalRead, GoalUpdate, GoalsOverview, MilestoneCreate, MilestoneRead, WeeklyFocusCreate, WeeklyFocusRead
from app.domains.goals.service import add_weekly_focus, complete_milestone, create_goal, create_milestone, goal_to_read, overview, update_goal


router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/overview", response_model=GoalsOverview)
def goals_overview(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return overview(db, user)


@router.post("", response_model=GoalRead, status_code=201)
def add_goal(payload: GoalCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    goal = create_goal(db, user, payload)
    from app.domains.orchestration import DomainRefreshService
    DomainRefreshService().refresh_user(db, user)
    db.commit()
    return goal_to_read(db, user, goal)


@router.patch("/{goal_id}", response_model=GoalRead)
def patch_goal(goal_id: str, payload: GoalUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    goal = update_goal(db, user, goal_id, payload)
    from app.domains.orchestration import DomainRefreshService
    DomainRefreshService().refresh_user(db, user)
    db.commit()
    return goal_to_read(db, user, goal)


@router.post("/{goal_id}/milestones", response_model=MilestoneRead, status_code=201)
def add_milestone(goal_id: str, payload: MilestoneCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    milestone = create_milestone(db, user, goal_id, payload)
    db.commit()
    return milestone


@router.post("/milestones/{milestone_id}/complete", response_model=MilestoneRead)
def finish_milestone(milestone_id: str, expected_version: int, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    milestone = complete_milestone(db, user, milestone_id, expected_version)
    db.commit()
    return milestone


@router.post("/weekly-focus", response_model=WeeklyFocusRead, status_code=201)
def create_weekly_focus(payload: WeeklyFocusCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    focus = add_weekly_focus(db, user, payload)
    from app.domains.orchestration import DomainRefreshService
    DomainRefreshService().refresh_user(db, user)
    db.commit()
    return focus
