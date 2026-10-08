from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.actions.service import list_actions
from app.commitments.service import list_commitments
from app.core.config import get_settings
from app.database.models import Action, Plan, PlanBlock, PlanningAllocation, UserProfile
from app.events.service import append_event
from app.planning.engine import BLOCK_GENERATED_ACTION, BLOCK_HARD_COMMITMENT, BLOCK_SLACK, CorePlannerV03, decision_factors_json
from app.planning.schemas import PlanGenerateRequest, PlanRead, PlanSummaryRead, json_factors
from app.planning.behavior import PlanningBehaviorProfile
from app.planning.constraints import PlanningConstraintResolver
from app.planning.rolling import RollingPlanner, action_group_id
from app.planning.types import CandidateAction, PlannedBlock, PlanningContext, PlanningResult
from app.personal_model.service import snapshot as personal_model_snapshot
from app.state.service import latest_state

DEFAULT_ENERGY = 60
DEFAULT_MENTAL_STATE = 60


def _sort_time(value: datetime) -> float:
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.timestamp()


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown timezone: {name}.") from exc


def _default_horizon(planning_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = _timezone(timezone_name)
    return (
        datetime.combine(planning_date, time(8, 0), tzinfo=zone),
        datetime.combine(planning_date, time(22, 0), tzinfo=zone),
    )


def _planning_date(payload: PlanGenerateRequest) -> date:
    if payload.planning_date is not None:
        return payload.planning_date
    if payload.horizon_start is not None:
        return payload.horizon_start.date()
    return datetime.now(_timezone(payload.timezone)).date()


def _metadata_int(action: Action, key: str, default: int) -> int:
    value = action.metadata_json.get(key) if isinstance(action.metadata_json, dict) else None
    if isinstance(value, (int, float)):
        return max(0, min(100, round(value)))
    return default


def _action_candidate(action: Action, allocation: PlanningAllocation | None = None) -> CandidateAction:
    total_estimate = max(1, action.estimated_minutes or action.duration_max_minutes or action.duration_min_minutes or 30)
    estimated = max(1, total_estimate - action.completed_minutes)
    minimum = action.duration_min_minutes or min(25, estimated)
    maximum = action.duration_max_minutes or estimated
    if minimum > maximum:
        minimum = maximum

    default_cognitive = {"learning": 72, "admin": 62, "fitness": 38, "kitchen": 38, "home": 42, "personal": 45}.get(action.domain, 45)
    default_physical = {"fitness": 68, "kitchen": 35, "home": 40}.get(action.domain, 20)
    activation_default = {"goal_critical": 48, "maintenance": 36, "optional": 24}.get(action.level, 35)
    trajectory_value = max({"goal_critical": 55, "maintenance": 22, "optional": 10}.get(action.level, 15), action.planning_priority)
    maintenance_value = 28 if action.level == "maintenance" else 8 if action.domain in {"kitchen", "home", "admin"} else 0
    neglect_cost = {"goal_critical": 14, "maintenance": 25, "optional": 3}.get(action.level, 6)
    if action.deadline is not None:
        neglect_cost += 8

    return CandidateAction(
        source_action_id=action.id,
        domain=action.domain,
        title=action.title,
        commitment_level=action.level,
        estimated_minutes=estimated,
        minimum_minutes=minimum,
        maximum_minutes=maximum,
        earliest_start=action.earliest_start,
        latest_start=action.latest_start,
        deadline=action.deadline,
        location=action.location,
        context=action.context,
        cognitive_load=_metadata_int(action, "cognitive_load", default_cognitive),
        physical_load=_metadata_int(action, "physical_load", default_physical),
        activation_difficulty=_metadata_int(action, "activation_difficulty", activation_default),
        stress_cost=_metadata_int(action, "stress_cost", round((default_cognitive + activation_default) / 8)),
        trajectory_value=_metadata_int(action, "trajectory_value", trajectory_value),
        maintenance_value=_metadata_int(action, "maintenance_value", maintenance_value),
        neglect_cost=_metadata_int(action, "neglect_cost", neglect_cost),
        splittable=bool(action.metadata_json.get("splittable", True)) if isinstance(action.metadata_json, dict) else True,
        action_group_id=action_group_id(action),
        variant_type=action.variant_type,
        variant_rank=action.variant_rank,
        mutually_exclusive=action.mutually_exclusive,
        variant_quality=action.variant_quality,
        allocated_minutes=allocation.allocated_minutes if allocation is not None else None,
        debt_minutes=allocation.debt_minutes if allocation is not None else 0,
        energy_requirement=(action.metadata_json or {}).get("energy_requirement"),
        metadata=action.metadata_json,
    )


def assemble_planning_context(db: Session, user: UserProfile, payload: PlanGenerateRequest) -> PlanningContext:
    planning_day = _planning_date(payload)
    horizon_start, horizon_end = (
        (payload.horizon_start, payload.horizon_end)
        if payload.horizon_start is not None and payload.horizon_end is not None
        else _default_horizon(planning_day, payload.timezone)
    )
    values = latest_state(db, user)
    energy_observation = values.get("energy")
    mental_observation = values.get("mental_state")
    energy = round(energy_observation.value) if energy_observation is not None else DEFAULT_ENERGY
    mental_state = round(mental_observation.value) if mental_observation is not None else DEFAULT_MENTAL_STATE
    observed_times = [
        item.observed_at
        for item in (energy_observation, mental_observation)
        if item is not None
    ]

    commitments = list_commitments(
        db,
        user,
        status_filter="active",
        level="hard",
        starts_from=horizon_start,
        starts_to=horizon_end,
    )
    actions = list_actions(db, user, planning_pool=True)
    allocations = list(
        db.scalars(
            select(PlanningAllocation).where(
                PlanningAllocation.user_id == user.id,
                PlanningAllocation.planning_date == planning_day,
            )
        ).all()
    )
    allocations_by_group = {item.action_group_id: item for item in allocations}
    candidates = [
        _action_candidate(action, allocations_by_group.get(action_group_id(action)))
        for action in actions
        if action.status == "active" and (not allocations_by_group or action_group_id(action) in allocations_by_group)
    ]
    personal_snapshot = personal_model_snapshot(db, user).model_dump(mode="json")
    constraints = PlanningConstraintResolver().resolve(db, user, planning_day=planning_day, timezone_name=payload.timezone)
    behavior = PlanningBehaviorProfile.load(db, user)

    return PlanningContext(
        user_id=user.id,
        planning_date=planning_day,
        timezone=payload.timezone,
        generated_at=datetime.now(UTC),
        generated_from_world_revision=user.world_revision,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        energy=energy,
        mental_state=mental_state,
        state_observed_at=max(observed_times) if observed_times else None,
        hard_commitments=[item for item in commitments if item.starts_at is not None and item.ends_at is not None],
        candidate_actions=candidates,
        constraints=constraints,
        personal_model_snapshot=personal_snapshot,
        behavior_patterns=behavior.as_json(),
    )


def _preserved_blocks(previous: Plan | None, now: datetime) -> list[PlannedBlock]:
    if previous is None:
        return []
    freeze_until = now + timedelta(minutes=get_settings().planner_freeze_window_minutes)
    preserved: list[PlannedBlock] = []
    for block in previous.blocks:
        start = block.starts_at.replace(tzinfo=UTC) if block.starts_at.tzinfo is None else block.starts_at
        end = block.ends_at.replace(tzinfo=UTC) if block.ends_at.tzinfo is None else block.ends_at
        keep = block.status in {"completed", "in_progress", "partially_completed", "skipped", "missed", "cancelled"} or block.user_locked or block.user_modified or (
            block.block_type == BLOCK_GENERATED_ACTION and block.status == "planned" and start <= freeze_until
        )
        if not keep or block.block_type == BLOCK_HARD_COMMITMENT:
            continue
        preserved.append(
            PlannedBlock(
                title=block.title,
                block_type=block.block_type,
                starts_at=start,
                ends_at=end,
                duration_minutes=block.duration_minutes,
                source_type=block.source_type,
                source_id=block.source_id,
                domain=block.domain,
                commitment_level=block.commitment_level,
                movable=block.movable,
                action_id=block.action_id,
                commitment_id=block.commitment_id,
                action_group_id=block.action_group_id,
                variant_type=block.variant_type,
                frozen_until=(block.frozen_until.replace(tzinfo=UTC) if block.frozen_until and block.frozen_until.tzinfo is None else block.frozen_until) or freeze_until,
                user_locked=block.user_locked,
                user_modified=block.user_modified,
                original_starts_at=block.original_starts_at.replace(tzinfo=UTC) if block.original_starts_at and block.original_starts_at.tzinfo is None else block.original_starts_at,
                status=block.status,
                started_at=block.started_at.replace(tzinfo=UTC) if block.started_at and block.started_at.tzinfo is None else block.started_at,
                finished_at=block.finished_at.replace(tzinfo=UTC) if block.finished_at and block.finished_at.tzinfo is None else block.finished_at,
                actual_duration_minutes=block.actual_duration_minutes,
                outcome_reason=block.outcome_reason,
                note=block.note,
                residual_minutes=block.residual_minutes,
            )
        )
    return preserved


def _summary(result: PlanningResult, context: PlanningContext) -> dict:
    hard_minutes = sum(block.duration_minutes for block in result.blocks if block.block_type == BLOCK_HARD_COMMITMENT)
    flexible_minutes = sum(block.duration_minutes for block in result.blocks if block.block_type == BLOCK_GENERATED_ACTION)
    slack_minutes = sum(block.duration_minutes for block in result.blocks if block.block_type == BLOCK_SLACK)
    return {
        "flexible_work_minutes": flexible_minutes,
        "hard_commitment_minutes": hard_minutes,
        "slack_minutes": slack_minutes,
        "actions_scheduled": len([block for block in result.blocks if block.block_type == BLOCK_GENERATED_ACTION]),
        "actions_unscheduled": len(result.unscheduled_actions),
        "planning_load": result.stress.band,
        "stress_estimate": result.stress.value,
        "stress_threshold": result.stress.threshold,
        "state_band": result.capacity.state_band,
        "usable_flexible_minutes": result.capacity.usable_flexible_minutes,
        "required_slack_minutes": result.capacity.required_slack_minutes,
        "energy": context.energy,
        "mental_state": context.mental_state,
        "state_observed_at": context.state_observed_at.isoformat() if context.state_observed_at is not None else None,
        "unscheduled_actions": [asdict(item) for item in result.unscheduled_actions],
    }


def _read_plan_query(user: UserProfile):
    return select(Plan).where(Plan.user_id == user.id).options(selectinload(Plan.blocks))


def get_plan(db: Session, user: UserProfile, plan_id: str) -> Plan:
    plan = db.scalar(_read_plan_query(user).where(Plan.id == plan_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return plan


def get_current_plan(db: Session, user: UserProfile, planning_day: date | None = None) -> Plan | None:
    target_day = planning_day or datetime.now(ZoneInfo("Europe/Berlin")).date()
    return db.scalar(
        _read_plan_query(user)
        .where(Plan.status == "current", Plan.planning_day == target_day)
        .order_by(Plan.generated_at.desc(), Plan.created_at.desc())
    )


def generate_plan(
    db: Session,
    user: UserProfile,
    payload: PlanGenerateRequest,
    *,
    before_publish_hook: Callable[[], None] | None = None,
    previous_plan: Plan | None = None,
    replan_reason: str | None = None,
    plan_diff: dict | None = None,
    planning_now: datetime | None = None,
) -> Plan:
    if payload.expected_world_revision is not None and payload.expected_world_revision != user.world_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_world_revision",
                "message": "Planner input world revision is stale.",
                "current_world_revision": user.world_revision,
            },
        )

    from app.domains.orchestration import DomainRefreshService

    planning_day = _planning_date(payload)
    domain_refresh = DomainRefreshService().refresh_user(
        db,
        user,
        horizon_start=planning_day,
        horizon_end=planning_day + timedelta(days=get_settings().planner_horizon_days - 1),
    )
    RollingPlanner().refresh(db, user, start_day=planning_day, timezone_name=payload.timezone)
    context = assemble_planning_context(db, user, payload)
    current_time = planning_now or datetime.now(UTC)
    context = replace(context, preserved_blocks=_preserved_blocks(previous_plan, current_time))
    result = CorePlannerV03().run(context)

    if before_publish_hook is not None:
        before_publish_hook()

    if user.world_revision != result.generated_from_world_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_world_revision",
                "message": "World changed during planning; generated plan was not published.",
                "current_world_revision": user.world_revision,
            },
        )

    existing_current = db.scalars(
        select(Plan).where(Plan.user_id == user.id, Plan.planning_day == result.planning_date, Plan.status == "current")
    ).all()
    for plan in existing_current:
        plan.status = "superseded"
        plan.version += 1

    plan = Plan(
        user_id=user.id,
        planner_version=result.planner_version,
        generated_from_world_revision=result.generated_from_world_revision,
        status="current",
        planning_day=result.planning_date,
        horizon_start=result.horizon_start,
        horizon_end=result.horizon_end,
        generated_at=datetime.now(UTC),
        previous_plan_id=previous_plan.id if previous_plan is not None else None,
        replan_reason=replan_reason,
        control_loop_version="v0.4-control-loop",
        plan_diff=plan_diff or {},
        last_replanned_at=datetime.now(UTC) if previous_plan is not None else None,
        summary_metrics=_summary(result, context),
        decision_factors={"items": decision_factors_json(result.decision_factors)},
        personal_model_snapshot=context.personal_model_snapshot,
        personal_model_revision=context.personal_model_snapshot.get("model_revision", 0) if isinstance(context.personal_model_snapshot, dict) else 0,
        overload_status=result.overload_status,
        shortfall_minutes=result.shortfall_minutes,
        overload_json={
            **result.overload,
            "domain_errors": [
                {"domain": item.domain, "errors": list(item.errors)}
                for item in domain_refresh
                if item.errors
            ],
        },
    )
    db.add(plan)
    db.flush()

    for block in result.blocks:
        db.add(
            PlanBlock(
                user_id=user.id,
                plan_id=plan.id,
                action_id=block.action_id,
                commitment_id=block.commitment_id,
                source_type=block.source_type,
                source_id=block.source_id,
                domain=block.domain,
                title=block.title,
                starts_at=block.starts_at,
                ends_at=block.ends_at,
                duration_minutes=block.duration_minutes,
                block_type=block.block_type,
                commitment_level=block.commitment_level,
                movable=block.movable,
                status=block.status,
                source="planner",
                decision_factors={"items": decision_factors_json(block.decision_factors)},
                action_group_id=block.action_group_id,
                variant_type=block.variant_type,
                frozen_until=block.frozen_until,
                user_locked=block.user_locked,
                user_modified=block.user_modified,
                original_starts_at=block.original_starts_at,
                started_at=block.started_at,
                finished_at=block.finished_at,
                actual_duration_minutes=block.actual_duration_minutes,
                outcome_reason=block.outcome_reason,
                note=block.note,
                residual_minutes=block.residual_minutes,
            )
        )
    db.flush()

    append_event(
        db,
        user,
        event_type="plan.replanned" if previous_plan is not None else "plan.generated",
        aggregate_type="plan",
        aggregate_id=plan.id,
        payload={
            "plan_id": plan.id,
            "planning_day": result.planning_date.isoformat(),
            "generated_from_world_revision": result.generated_from_world_revision,
            "previous_plan_id": previous_plan.id if previous_plan is not None else None,
            "replan_reason": replan_reason,
            "summary_metrics": plan.summary_metrics,
            "personal_model_revision": plan.personal_model_revision,
            "overload_status": result.overload_status,
            "shortfall_minutes": result.shortfall_minutes,
        },
        outbox=True,
    )
    for block in result.blocks:
        if block.block_type != BLOCK_GENERATED_ACTION or not block.action_group_id:
            continue
        append_event(
            db,
            user,
            event_type="planning.action_variant.selected",
            aggregate_type="plan_block",
            aggregate_id=block.action_id or plan.id,
            payload={
                "plan_id": plan.id,
                "action_group_id": block.action_group_id,
                "action_id": block.action_id,
                "variant_type": block.variant_type,
                "duration_minutes": block.duration_minutes,
                "starts_at": block.starts_at.isoformat(),
            },
            outbox=True,
            increment_world_revision=False,
        )
    if result.overload_status not in {"feasible", "tight"}:
        append_event(
            db,
            user,
            event_type="planning.overload.detected",
            aggregate_type="plan",
            aggregate_id=plan.id,
            payload=result.overload,
            outbox=True,
            increment_world_revision=False,
        )
    db.flush()
    return get_plan(db, user, plan.id)


def plan_to_read(plan: Plan, current_world_revision: int | None = None) -> PlanRead:
    metrics = dict(plan.summary_metrics or {})
    unscheduled = metrics.pop("unscheduled_actions", [])
    metrics.pop("energy", None)
    metrics.pop("mental_state", None)
    metrics.pop("state_observed_at", None)
    blocks = sorted(plan.blocks, key=lambda item: (_sort_time(item.starts_at), item.block_type, item.title))
    return PlanRead(
        id=plan.id,
        user_id=plan.user_id,
        planner_version=plan.planner_version,
        generated_from_world_revision=plan.generated_from_world_revision,
        status=plan.status,
        planning_day=plan.planning_day,
        horizon_start=plan.horizon_start,
        horizon_end=plan.horizon_end,
        generated_at=plan.generated_at,
        previous_plan_id=plan.previous_plan_id,
        replan_reason=plan.replan_reason,
        control_loop_version=plan.control_loop_version,
        plan_diff=plan.plan_diff or {},
        last_evaluated_at=plan.last_evaluated_at,
        last_replanned_at=plan.last_replanned_at,
        summary_metrics=PlanSummaryRead(**metrics),
        decision_factors=json_factors(plan.decision_factors),
        personal_model_snapshot=plan.personal_model_snapshot or {},
        personal_model_revision=plan.personal_model_revision,
        overload_status=plan.overload_status,
        shortfall_minutes=plan.shortfall_minutes,
        overload=plan.overload_json or {},
        blocks=[
            {
                "id": block.id,
                "source_type": block.source_type,
                "source_id": block.source_id,
                "action_id": block.action_id,
                "commitment_id": block.commitment_id,
                "domain": block.domain,
                "title": block.title,
                "starts_at": block.starts_at,
                "ends_at": block.ends_at,
                "duration_minutes": block.duration_minutes,
                "block_type": block.block_type,
                "commitment_level": block.commitment_level,
                "movable": block.movable,
                "status": block.status,
                "started_at": block.started_at,
                "finished_at": block.finished_at,
                "actual_duration_minutes": block.actual_duration_minutes,
                "outcome_reason": block.outcome_reason,
                "note": block.note,
                "action_group_id": block.action_group_id,
                "variant_type": block.variant_type,
                "frozen_until": block.frozen_until,
                "user_locked": block.user_locked,
                "user_modified": block.user_modified,
                "original_starts_at": block.original_starts_at,
                "residual_minutes": block.residual_minutes,
                "decision_factors": json_factors(block.decision_factors),
                "version": block.version,
            }
            for block in blocks
        ],
        unscheduled_actions=unscheduled,
        current_world_revision=current_world_revision,
        version=plan.version,
    )
