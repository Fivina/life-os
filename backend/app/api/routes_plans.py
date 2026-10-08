import json
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import Action, Goal, UserProfile
from app.database.session import get_db
from app.events.idempotency import get_replay_or_conflict, store_idempotent_response
from app.planning.control_loop import complete_block as complete_block_service
from app.planning.control_loop import cancel_placement as cancel_placement_service
from app.planning.control_loop import manual_replan as manual_replan_service
from app.planning.control_loop import move_block as move_block_service
from app.planning.control_loop import partial_complete_block as partial_complete_block_service
from app.planning.control_loop import skip_block as skip_block_service
from app.planning.control_loop import start_block as start_block_service
from app.planning.automation import MorningPlanner
from app.planning.rolling import RollingPlanner
from app.planning.schemas import HorizonAllocationRead, PlanBlockExecutionCommand, PlanBlockMoveCommand, PlanGenerateRequest, PlanRead, ReplanRequest, ReplanResponse
from app.planning.service import generate_plan as generate_plan_service
from app.planning.service import get_current_plan, get_plan, plan_to_read

router = APIRouter(prefix="/plans", tags=["plans"])


def _payload_json(payload) -> str:
    return json.dumps(payload.model_dump(mode="json", exclude_none=True), sort_keys=True)


@router.post("/generate", response_model=PlanRead)
def generate_plan(
    payload: PlanGenerateRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    payload_json = _payload_json(payload)
    replay = get_replay_or_conflict(db, user, mutation_key=idempotency_key, endpoint="/api/v1/plans/generate", payload_json=payload_json)
    if replay is not None:
        return replay.response_body
    plan = generate_plan_service(db, user, payload)
    response = plan_to_read(plan, user.world_revision).model_dump(mode="json")
    store_idempotent_response(db, user, mutation_key=idempotency_key, endpoint="/api/v1/plans/generate", payload_json=payload_json, response_body=response)
    db.commit()
    return response


@router.get("/current", response_model=PlanRead | None)
def current_plan(
    response: Response,
    planning_date: date | None = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    plan = get_current_plan(db, user, planning_date)
    if plan is None:
        plan, _ = MorningPlanner().ensure(db, user)
        db.commit()
    return plan_to_read(plan, user.world_revision)


@router.get("/horizon", response_model=HorizonAllocationRead)
def horizon_allocations(
    starts_on: date | None = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> HorizonAllocationRead:
    planner = RollingPlanner()
    status_row = planner.refresh(db, user, start_day=starts_on)
    allocations = planner.allocations(db, user, start_day=status_row.horizon_start, end_day=status_row.horizon_end)
    db.commit()
    return HorizonAllocationRead(
        horizon_start=status_row.horizon_start,
        horizon_end=status_row.horizon_end,
        status=status_row.status,
        required_minutes=status_row.required_minutes,
        available_minutes=status_row.available_minutes,
        shortfall_minutes=status_row.shortfall_minutes,
        allocations=allocations,
    )


@router.get("/overload")
def overload_state(planning_date: date | None = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> dict:
    plan = get_current_plan(db, user, planning_date)
    if plan is None:
        plan, _ = MorningPlanner().ensure(db, user)
        db.commit()
    return {"plan_id": plan.id, "status": plan.overload_status, "shortfall_minutes": plan.shortfall_minutes, **(plan.overload_json or {})}


@router.post("/replan", response_model=ReplanResponse)
def replan(
    payload: ReplanRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    response = manual_replan_service(db, user, planning_day=payload.planning_date, reason=payload.reason, now=payload.now)
    db.commit()
    return response


@router.post("/{plan_id}/blocks/{block_id}/start", response_model=PlanRead)
def start_block(
    plan_id: str,
    block_id: str,
    payload: PlanBlockExecutionCommand,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> PlanRead:
    plan = start_block_service(db, user, plan_id, block_id, expected_version=payload.expected_version, occurred_at=payload.occurred_at)
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response


@router.get("/{plan_id}", response_model=PlanRead)
def read_plan(plan_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> PlanRead:
    return plan_to_read(get_plan(db, user, plan_id), user.world_revision)


@router.post("/{plan_id}/blocks/{block_id}/complete", response_model=PlanRead)
def complete_block(
    plan_id: str,
    block_id: str,
    payload: PlanBlockExecutionCommand,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> PlanRead:
    plan = complete_block_service(
        db,
        user,
        plan_id,
        block_id,
        expected_version=payload.expected_version,
        actual_duration_minutes=payload.actual_duration_minutes,
        reason=payload.reason,
        note=payload.note,
        occurred_at=payload.occurred_at,
    )
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response


@router.post("/{plan_id}/blocks/{block_id}/partial", response_model=PlanRead)
def partial_complete_block(
    plan_id: str,
    block_id: str,
    payload: PlanBlockExecutionCommand,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> PlanRead:
    if payload.actual_duration_minutes is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="actual_duration_minutes is required for partial completion.")
    plan = partial_complete_block_service(db, user, plan_id, block_id, expected_version=payload.expected_version, actual_duration_minutes=payload.actual_duration_minutes, reason=payload.reason, note=payload.note, occurred_at=payload.occurred_at)
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response


@router.post("/{plan_id}/blocks/{block_id}/move", response_model=PlanRead)
def move_block(plan_id: str, block_id: str, payload: PlanBlockMoveCommand, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> PlanRead:
    plan = move_block_service(db, user, plan_id, block_id, expected_version=payload.expected_version, starts_at=payload.starts_at, ends_at=payload.ends_at, note=payload.note)
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response


@router.post("/{plan_id}/blocks/{block_id}/cancel", response_model=PlanRead)
def cancel_placement(plan_id: str, block_id: str, payload: PlanBlockExecutionCommand, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> PlanRead:
    plan = cancel_placement_service(db, user, plan_id, block_id, expected_version=payload.expected_version, note=payload.note)
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response


@router.get("/{plan_id}/blocks/{block_id}/explain")
def explain_block(plan_id: str, block_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)) -> dict:
    plan = get_plan(db, user, plan_id)
    block = next((item for item in plan.blocks if item.id == block_id), None)
    if block is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Plan block not found.")
    factors = json.loads(json.dumps(block.decision_factors or {})).get("items", [])
    material = [factor for factor in factors if factor.get("contribution") or factor.get("factor") in {"future_slot_weekday", "hard_commitment"}]
    action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id)) if block.action_id else None
    goal = db.scalar(select(Goal).where(Goal.id == action.goal_id, Goal.user_id == user.id)) if action and action.goal_id else None
    provenance = []
    if action and action.generated_reason:
        provenance.append(action.generated_reason)
    if goal:
        provenance.append(f"This block supports your goal: {goal.title}.")
    return {"plan_id": plan.id, "plan_block_id": block.id, "title": block.title, "domain": block.domain, "variant_type": block.variant_type, "requirement_key": action.requirement_key if action else None, "source_entity_type": action.source_entity_type if action else None, "source_entity_id": action.source_entity_id if action else None, "goal_id": action.goal_id if action else None, "factors": material, "summary": provenance + [factor.get("notes") or factor.get("factor") for factor in material[:5]]}


@router.post("/{plan_id}/blocks/{block_id}/skip", response_model=PlanRead)
def skip_block(
    plan_id: str,
    block_id: str,
    payload: PlanBlockExecutionCommand,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> PlanRead:
    plan = skip_block_service(
        db,
        user,
        plan_id,
        block_id,
        expected_version=payload.expected_version,
        reason=payload.reason,
        note=payload.note,
        occurred_at=payload.occurred_at,
    )
    response = plan_to_read(plan, user.world_revision)
    db.commit()
    return response
