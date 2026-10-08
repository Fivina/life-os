from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import timedelta

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.home.schemas import HouseholdCompleteRequest, HouseholdOverview, HouseholdTaskCreate, HouseholdTaskRead, HouseholdTaskUpdate
from app.domains.home.service import complete_task, create_task, list_tasks, local_planning_date, overview, refresh_actions, update_task


router = APIRouter(prefix="/home", tags=["home"])


@router.get("/overview", response_model=HouseholdOverview)
def household_overview(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return overview(db, user)


@router.get("/tasks", response_model=list[HouseholdTaskRead])
def household_tasks(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    current = overview(db, user)
    by_id = {item.id: item for item in current.due + current.upcoming + current.recently_completed}
    return [by_id.get(item.id) or HouseholdTaskRead.model_validate(item) for item in list_tasks(db, user)]


@router.post("/tasks", response_model=HouseholdTaskRead, status_code=201)
def add_household_task(payload: HouseholdTaskCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    task = create_task(db, user, payload)
    due_day = local_planning_date(task.next_due_at)
    refresh_actions(db, user, horizon_start=due_day, horizon_end=due_day)
    db.commit()
    db.refresh(task)
    return HouseholdTaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=HouseholdTaskRead)
def patch_household_task(task_id: str, payload: HouseholdTaskUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    task = update_task(db, user, task_id, payload)
    today = local_planning_date()
    refresh_actions(db, user, horizon_start=today, horizon_end=today + timedelta(days=14))
    db.commit()
    db.refresh(task)
    return HouseholdTaskRead.model_validate(task)


@router.post("/tasks/{task_id}/complete", response_model=HouseholdTaskRead)
def finish_household_task(task_id: str, payload: HouseholdCompleteRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    task = next(item for item in list_tasks(db, user) if item.id == task_id)
    if task.version != payload.expected_version:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"Household task version conflict. Current version is {task.version}.")
    task = complete_task(db, user, task_id, occurred_at=payload.completed_at)
    today = local_planning_date()
    refresh_actions(db, user, horizon_start=today, horizon_end=today + timedelta(days=14))
    db.commit()
    db.refresh(task)
    return HouseholdTaskRead.model_validate(task)


@router.post("/requirements/refresh")
def refresh_household_requirements(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    today = local_planning_date()
    result = refresh_actions(db, user, horizon_start=today, horizon_end=today + timedelta(days=14))
    db.commit()
    return result
