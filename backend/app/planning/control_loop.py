from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Action, Plan, PlanBlock, PlanningAllocation, PlanningDebt, UserProfile
from app.events.service import append_event
from app.commitments.service import list_commitments
from app.planning.engine import BLOCK_GENERATED_ACTION, BLOCK_HARD_COMMITMENT, BLOCK_SLACK
from app.planning.schemas import PlanGenerateRequest
from app.planning.service import generate_plan, get_current_plan, get_plan, plan_to_read
from app.state.service import latest_state

CONTROL_LOOP_VERSION = "v0.4-control-loop"
STATE_DELTA_THRESHOLD = 15
FREEZE_HORIZON_MINUTES = 30
STATE_REPLAN_COOLDOWN_MINUTES = 15
MISSED_GRACE_MINUTES = 5

BLOCK_STATUSES = {"planned", "in_progress", "completed", "partially_completed", "skipped", "missed", "cancelled", "moved"}
EXECUTION_REASONS = {
    "low_energy",
    "low_mental_state",
    "activation_difficulty",
    "unexpected_event",
    "time_conflict",
    "took_longer_elsewhere",
    "no_longer_relevant",
    "other",
}


@dataclass(frozen=True)
class PlanDiff:
    previous_plan_id: str | None
    new_plan_id: str | None
    trigger: str
    kept_block_ids: list[str]
    moved_blocks: list[dict[str, Any]]
    shortened_blocks: list[dict[str, Any]]
    removed_blocks: list[dict[str, Any]]
    added_blocks: list[dict[str, Any]]
    deferred_action_ids: list[str]
    previous_stress: int | None
    new_stress: int | None
    previous_slack_minutes: int | None
    new_slack_minutes: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous_plan_id": self.previous_plan_id,
            "new_plan_id": self.new_plan_id,
            "trigger": self.trigger,
            "kept_block_ids": self.kept_block_ids,
            "moved_blocks": self.moved_blocks,
            "shortened_blocks": self.shortened_blocks,
            "removed_blocks": self.removed_blocks,
            "added_blocks": self.added_blocks,
            "deferred_action_ids": self.deferred_action_ids,
            "previous_stress": self.previous_stress,
            "new_stress": self.new_stress,
            "previous_slack_minutes": self.previous_slack_minutes,
            "new_slack_minutes": self.new_slack_minutes,
        }


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(UTC)


def _align(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _sort_time(value: datetime) -> float:
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.timestamp()


def _current_state(db: Session, user: UserProfile) -> tuple[int, int]:
    values = latest_state(db, user)
    energy = round(values["energy"].value) if "energy" in values else 60
    mental = round(values["mental_state"].value) if "mental_state" in values else 60
    return energy, mental


def _capacity_band(energy: int, mental_state: int) -> str:
    average = round((energy + mental_state) / 2)
    if average >= 70:
        return "high"
    if average >= 50:
        return "medium"
    if average >= 35:
        return "low"
    return "very_low"


def _material_state_change(plan: Plan, energy: int, mental_state: int) -> tuple[bool, list[str]]:
    previous_energy = plan.summary_metrics.get("energy")
    previous_mental = plan.summary_metrics.get("mental_state")
    previous_band = plan.summary_metrics.get("state_band")
    reasons: list[str] = []
    energy_delta = abs(energy - previous_energy) if isinstance(previous_energy, int) else 0
    mental_delta = abs(mental_state - previous_mental) if isinstance(previous_mental, int) else 0
    if isinstance(previous_energy, int) and abs(energy - previous_energy) >= STATE_DELTA_THRESHOLD:
        reasons.append("STATE_MATERIAL_CHANGE")
    if isinstance(previous_mental, int) and abs(mental_state - previous_mental) >= STATE_DELTA_THRESHOLD:
        reasons.append("STATE_MATERIAL_CHANGE")
    if previous_band and previous_band != _capacity_band(energy, mental_state) and max(energy_delta, mental_delta) >= 10:
        reasons.append("CAPACITY_BAND_CHANGED")
    return bool(reasons), sorted(set(reasons))


def _block_key(block: PlanBlock) -> tuple[str, str | None, str]:
    return (block.block_type, block.source_id or block.id, block.title)


def _stress(plan: Plan) -> int | None:
    value = plan.summary_metrics.get("stress_estimate") if plan.summary_metrics else None
    return value if isinstance(value, int) else None


def _slack(plan: Plan) -> int | None:
    value = plan.summary_metrics.get("slack_minutes") if plan.summary_metrics else None
    return value if isinstance(value, int) else None


def _diff(previous: Plan | None, new: Plan | None, trigger: str) -> PlanDiff:
    if previous is None and new is None:
        return PlanDiff(None, None, trigger, [], [], [], [], [], [], None, None, None, None)

    previous_blocks = sorted(previous.blocks, key=lambda block: (_sort_time(block.starts_at), block.title)) if previous else []
    new_blocks = sorted(new.blocks, key=lambda block: (_sort_time(block.starts_at), block.title)) if new else []
    previous_by_key = {_block_key(block): block for block in previous_blocks}
    new_by_key = {_block_key(block): block for block in new_blocks}
    kept: list[str] = []
    moved: list[dict[str, Any]] = []
    shortened: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    deferred: list[str] = []

    for key, old in previous_by_key.items():
        new_block = new_by_key.get(key)
        if new_block is None:
            if old.block_type == BLOCK_GENERATED_ACTION and old.action_id:
                deferred.append(old.action_id)
            removed.append({"block_id": old.id, "title": old.title, "source_id": old.source_id, "block_type": old.block_type})
            continue
        if old.starts_at == new_block.starts_at and old.ends_at == new_block.ends_at and old.status == new_block.status:
            kept.append(old.id)
        else:
            moved.append(
                {
                    "block_id": old.id,
                    "new_block_id": new_block.id,
                    "title": old.title,
                    "from": old.starts_at.isoformat(),
                    "to": new_block.starts_at.isoformat(),
                }
            )
        if new_block.duration_minutes < old.duration_minutes:
            shortened.append(
                {
                    "block_id": old.id,
                    "new_block_id": new_block.id,
                    "title": old.title,
                    "from_minutes": old.duration_minutes,
                    "to_minutes": new_block.duration_minutes,
                }
            )

    for key, new_block in new_by_key.items():
        if key not in previous_by_key:
            added.append({"block_id": new_block.id, "title": new_block.title, "source_id": new_block.source_id, "block_type": new_block.block_type})

    return PlanDiff(
        previous_plan_id=previous.id if previous else None,
        new_plan_id=new.id if new else None,
        trigger=trigger,
        kept_block_ids=kept,
        moved_blocks=moved,
        shortened_blocks=shortened,
        removed_blocks=removed,
        added_blocks=added,
        deferred_action_ids=sorted(set(deferred)),
        previous_stress=_stress(previous) if previous else None,
        new_stress=_stress(new) if new else None,
        previous_slack_minutes=_slack(previous) if previous else None,
        new_slack_minutes=_slack(new) if new else None,
    )


def _read_block(db: Session, user: UserProfile, plan_id: str, block_id: str) -> PlanBlock:
    block = db.scalar(
        select(PlanBlock)
        .join(Plan, Plan.id == PlanBlock.plan_id)
        .where(Plan.user_id == user.id, Plan.id == plan_id, PlanBlock.id == block_id)
    )
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan block not found.")
    return block


def _validate_generated_block(block: PlanBlock) -> None:
    if block.block_type != BLOCK_GENERATED_ACTION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only generated action blocks support execution commands in V0.4.")


def _validate_reason(reason: str | None) -> None:
    if reason is not None and reason not in EXECUTION_REASONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid execution reason: {reason}.")


def _append_block_event(db: Session, user: UserProfile, block: PlanBlock, event_type: str, payload: dict[str, Any]) -> None:
    append_event(
        db,
        user,
        event_type=event_type,
        aggregate_type="plan_block",
        aggregate_id=block.id,
        payload={
            "plan_id": block.plan_id,
            "plan_block_id": block.id,
            "source_action_id": block.action_id,
            "source_commitment_id": block.commitment_id,
            **payload,
        },
        outbox=True,
    )


def _action_group(db: Session, block: PlanBlock) -> tuple[str, Action | None]:
    action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == block.user_id)) if block.action_id else None
    return block.action_group_id or (action.candidate_group_id if action else None) or block.action_id or block.id, action


def _record_debt(db: Session, user: UserProfile, block: PlanBlock, residual: int, reason: str) -> PlanningDebt | None:
    residual = max(0, residual)
    if residual <= 0:
        return None
    group_id, action = _action_group(db, block)
    row = db.scalar(select(PlanningDebt).where(PlanningDebt.user_id == user.id, PlanningDebt.source_plan_block_id == block.id))
    if row is None:
        row = PlanningDebt(
            user_id=user.id,
            action_group_id=group_id,
            source_action_id=block.action_id,
            source_plan_block_id=block.id,
            domain=block.domain or "general",
            residual_minutes=residual,
            reason=reason,
            status="open",
            deadline=action.deadline if action else None,
            metadata_json={"plan_id": block.plan_id, "variant_type": block.variant_type},
        )
        db.add(row)
        db.flush()
        append_event(
            db,
            user,
            event_type="planning.debt.created",
            aggregate_type="planning_debt",
            aggregate_id=row.id,
            payload={"plan_block_id": block.id, "action_group_id": group_id, "residual_minutes": residual, "reason": reason},
            outbox=True,
        )
    else:
        row.residual_minutes = residual
        row.reason = reason
        row.status = "open"
        row.version += 1
    block.residual_minutes = residual
    return row


def _resolve_group_debt(db: Session, user: UserProfile, group_id: str, completed: int, when: datetime) -> None:
    remaining = max(0, completed)
    rows = list(
        db.scalars(
            select(PlanningDebt)
            .where(PlanningDebt.user_id == user.id, PlanningDebt.action_group_id == group_id, PlanningDebt.status == "open")
            .order_by(PlanningDebt.created_at)
        ).all()
    )
    for row in rows:
        if remaining <= 0:
            break
        used = min(remaining, row.residual_minutes)
        row.residual_minutes -= used
        remaining -= used
        if row.residual_minutes == 0:
            row.status = "resolved"
            row.resolved_at = when
            append_event(db, user, event_type="planning.debt.resolved", aggregate_type="planning_debt", aggregate_id=row.id, payload={"action_group_id": group_id}, outbox=True)
        row.version += 1


def _record_allocation_progress(db: Session, user: UserProfile, block: PlanBlock, completed: int) -> None:
    plan = db.get(Plan, block.plan_id)
    group_id, _ = _action_group(db, block)
    if plan is None or plan.planning_day is None:
        return
    allocation = db.scalar(
        select(PlanningAllocation).where(
            PlanningAllocation.user_id == user.id,
            PlanningAllocation.planning_date == plan.planning_day,
            PlanningAllocation.action_group_id == group_id,
        )
    )
    if allocation is None:
        return
    allocation.completed_minutes = min(allocation.allocated_minutes, allocation.completed_minutes + max(0, completed))
    allocation.status = "completed" if allocation.completed_minutes >= allocation.allocated_minutes else "in_progress"
    allocation.version += 1


def start_block(db: Session, user: UserProfile, plan_id: str, block_id: str, *, expected_version: int, occurred_at: datetime | None = None) -> Plan:
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status != "planned":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot start block from status {block.status}.")
    when = _now(occurred_at)
    block.status = "in_progress"
    block.started_at = when
    block.version += 1
    _append_block_event(db, user, block, "plan.block.started", {"started_at": when.isoformat()})
    if block.domain == "fitness":
        from app.domains.fitness.service import start_fitness_plan_block

        start_fitness_plan_block(db, user, block, when)
    db.flush()
    return get_plan(db, user, plan_id)


def complete_block(
    db: Session,
    user: UserProfile,
    plan_id: str,
    block_id: str,
    *,
    expected_version: int,
    actual_duration_minutes: int | None = None,
    reason: str | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> Plan:
    _validate_reason(reason)
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status not in {"planned", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot complete block from status {block.status}.")
    when = _now(occurred_at)
    actual = actual_duration_minutes or block.duration_minutes
    block.status = "completed"
    block.started_at = block.started_at or when
    block.finished_at = when
    block.actual_duration_minutes = actual
    block.outcome_reason = reason
    block.note = note
    block.version += 1

    action_completed = False
    if block.action_id:
        action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id))
        if action is not None and action.status == "active":
            total = action.estimated_minutes or action.duration_max_minutes or action.duration_min_minutes or block.duration_minutes
            action.completed_minutes = min(total, action.completed_minutes + actual)
            if action.completed_minutes >= total:
                action.status = "completed"
                action_completed = True
            action.version += 1
            group_id = block.action_group_id or action.candidate_group_id
            if group_id and actual >= block.duration_minutes:
                siblings = list(
                    db.scalars(
                        select(Action).where(
                            Action.user_id == user.id,
                            Action.candidate_group_id == group_id,
                            Action.id != action.id,
                            Action.status == "active",
                        )
                    ).all()
                )
                for sibling in siblings:
                    sibling.status = "cancelled"
                    sibling.version += 1
            _resolve_group_debt(db, user, group_id or action.id, actual, when)

    if block.domain == "learning":
        from app.domains.learning.service import complete_learning_plan_block

        complete_learning_plan_block(db, user, block, actual, when)
    elif block.domain == "fitness":
        from app.domains.fitness.service import complete_fitness_plan_block

        complete_fitness_plan_block(db, user, block, actual, when)
    elif block.domain == "home":
        from app.domains.home.service import complete_plan_block

        complete_plan_block(db, user, block, when)
    elif block.domain == "kitchen":
        from app.domains.kitchen.service import complete_kitchen_plan_block

        complete_kitchen_plan_block(db, user, block, when)

    _record_allocation_progress(db, user, block, actual)

    _append_block_event(
        db,
        user,
        block,
        "plan.block.completed",
        {
            "finished_at": when.isoformat(),
            "actual_duration_minutes": actual,
            "reason": reason,
            "note": note,
            "source_action_completed": action_completed,
        },
    )
    from app.domains.orchestration import DomainRefreshService

    DomainRefreshService().refresh_user(db, user)
    db.flush()
    return get_plan(db, user, plan_id)


def partial_complete_block(
    db: Session,
    user: UserProfile,
    plan_id: str,
    block_id: str,
    *,
    expected_version: int,
    actual_duration_minutes: int,
    reason: str | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> Plan:
    _validate_reason(reason)
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status not in {"planned", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot partially complete block from status {block.status}.")
    if actual_duration_minutes >= block.duration_minutes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Partial duration must be less than planned duration.")
    when = _now(occurred_at)
    block.status = "partially_completed"
    block.started_at = block.started_at or when
    block.finished_at = when
    block.actual_duration_minutes = actual_duration_minutes
    block.outcome_reason = reason
    block.note = note
    block.version += 1
    if block.action_id:
        action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id))
        if action is not None:
            action.completed_minutes += actual_duration_minutes
            action.version += 1
    residual = block.duration_minutes - actual_duration_minutes
    if block.domain == "learning":
        from app.domains.learning.service import complete_learning_plan_block

        complete_learning_plan_block(db, user, block, actual_duration_minutes, when, completion_status="partially_completed")
    elif block.domain == "fitness":
        from app.domains.fitness.service import complete_fitness_plan_block

        complete_fitness_plan_block(db, user, block, actual_duration_minutes, when, partial=True)
    _record_allocation_progress(db, user, block, actual_duration_minutes)
    _record_debt(db, user, block, residual, "partial_completion")
    _append_block_event(
        db,
        user,
        block,
        "plan.block.partially_completed",
        {"actual_duration_minutes": actual_duration_minutes, "residual_minutes": residual, "reason": reason, "finished_at": when.isoformat()},
    )
    from app.domains.orchestration import DomainRefreshService

    DomainRefreshService().refresh_user(db, user)
    db.flush()
    return get_plan(db, user, plan_id)


def skip_block(
    db: Session,
    user: UserProfile,
    plan_id: str,
    block_id: str,
    *,
    expected_version: int,
    reason: str | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> Plan:
    _validate_reason(reason)
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status not in {"planned", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot skip block from status {block.status}.")
    when = _now(occurred_at)
    block.status = "skipped"
    block.finished_at = when
    block.outcome_reason = reason
    block.note = note
    block.version += 1
    _record_debt(db, user, block, block.duration_minutes, "skipped")
    if block.domain == "home":
        from app.domains.home.service import record_skip

        record_skip(db, user, block, when)
    elif block.domain in {"learning", "fitness"}:
        append_event(
            db,
            user,
            event_type=f"{block.domain}.{'study' if block.domain == 'learning' else 'workout'}.skipped",
            aggregate_type="plan_block",
            aggregate_id=block.id,
            payload={"plan_block_id": block.id, "skipped_at": when.isoformat(), "reason": reason},
            increment_world_revision=False,
        )
    _append_block_event(db, user, block, "plan.block.skipped", {"skipped_at": when.isoformat(), "reason": reason, "note": note})
    from app.domains.orchestration import DomainRefreshService

    DomainRefreshService().refresh_user(db, user)
    db.flush()
    return get_plan(db, user, plan_id)


def move_block(
    db: Session,
    user: UserProfile,
    plan_id: str,
    block_id: str,
    *,
    expected_version: int,
    starts_at: datetime,
    ends_at: datetime,
    note: str | None = None,
) -> Plan:
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status != "planned":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot move block from status {block.status}.")
    plan = get_plan(db, user, plan_id)
    for other in plan.blocks:
        if other.id == block.id or other.status in {"skipped", "missed", "cancelled"}:
            continue
        if starts_at < _align(other.ends_at, starts_at) and ends_at > _align(other.starts_at, starts_at):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Move conflicts with {other.title}.")
    previous_start, previous_end = block.starts_at, block.ends_at
    block.original_starts_at = block.original_starts_at or previous_start
    block.starts_at = starts_at
    block.ends_at = ends_at
    block.duration_minutes = max(1, int((ends_at - starts_at).total_seconds() // 60))
    block.user_modified = True
    block.user_locked = True
    block.frozen_until = ends_at
    block.note = note
    block.version += 1
    _append_block_event(db, user, block, "plan.block.moved", {"from_start": previous_start.isoformat(), "from_end": previous_end.isoformat(), "to_start": starts_at.isoformat(), "to_end": ends_at.isoformat(), "user_directed": True})
    db.flush()
    return get_plan(db, user, plan_id)


def cancel_placement(db: Session, user: UserProfile, plan_id: str, block_id: str, *, expected_version: int, note: str | None = None) -> Plan:
    block = _read_block(db, user, plan_id, block_id)
    _validate_generated_block(block)
    if block.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PlanBlock version conflict. Current version is {block.version}.")
    if block.status not in {"planned", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel placement from status {block.status}.")
    block.status = "cancelled"
    block.finished_at = _now()
    block.note = note
    block.user_modified = True
    block.version += 1
    _record_debt(db, user, block, block.duration_minutes, "placement_cancelled")
    _append_block_event(db, user, block, "plan.block.cancelled", {"requirement_preserved": True, "note": note})
    db.flush()
    return get_plan(db, user, plan_id)


def mark_overdue_blocks_missed(db: Session, user: UserProfile, plan: Plan, now: datetime) -> list[PlanBlock]:
    missed: list[PlanBlock] = []
    cutoff = now - timedelta(minutes=MISSED_GRACE_MINUTES)
    for block in plan.blocks:
        end = _align(block.ends_at, now)
        if block.block_type == BLOCK_GENERATED_ACTION and block.status == "planned" and end < cutoff:
            block.status = "missed"
            block.finished_at = now
            block.outcome_reason = "time_conflict"
            block.version += 1
            _record_debt(db, user, block, block.duration_minutes, "missed")
            _append_block_event(db, user, block, "plan.block.missed", {"missed_at": now.isoformat(), "reason": "time_conflict"})
            missed.append(block)
    return missed


def _hard_conflict_exists(db: Session, user: UserProfile, plan: Plan) -> bool:
    hard_blocks = [block for block in plan.blocks if block.block_type == BLOCK_HARD_COMMITMENT]
    if plan.horizon_start is not None and plan.horizon_end is not None:
        for commitment in list_commitments(db, user, status_filter="active", level="hard", starts_from=plan.horizon_start, starts_to=plan.horizon_end):
            if commitment.starts_at is None or commitment.ends_at is None:
                continue
            hard_blocks.append(
                PlanBlock(
                    user_id=user.id,
                    plan_id=plan.id,
                    title=commitment.title,
                    starts_at=commitment.starts_at,
                    ends_at=commitment.ends_at,
                    duration_minutes=0,
                    block_type=BLOCK_HARD_COMMITMENT,
                    source_type="commitment",
                    source_id=commitment.id,
                    commitment_id=commitment.id,
                    movable=False,
                )
            )
    generated = [block for block in plan.blocks if block.block_type == BLOCK_GENERATED_ACTION and block.status in {"planned", "in_progress"}]
    for hard in hard_blocks:
        for block in generated:
            block_start = _align(block.starts_at, hard.starts_at)
            block_end = _align(block.ends_at, hard.starts_at)
            if block_start < hard.ends_at and block_end > hard.starts_at:
                return True
    return False


def _replan_payload(plan: Plan, expected_world_revision: int, now: datetime | None = None) -> PlanGenerateRequest:
    horizon_start = plan.horizon_start.replace(tzinfo=UTC) if plan.horizon_start and plan.horizon_start.tzinfo is None else plan.horizon_start
    horizon_end = plan.horizon_end.replace(tzinfo=UTC) if plan.horizon_end and plan.horizon_end.tzinfo is None else plan.horizon_end
    if now is not None and horizon_start is not None:
        aligned_now = _align(now, horizon_start)
        horizon_start = max(horizon_start, aligned_now)
        if horizon_end is not None and horizon_start >= horizon_end:
            horizon_start = horizon_end - timedelta(minutes=1)
    return PlanGenerateRequest(
        planning_date=plan.planning_day,
        timezone="Europe/Berlin",
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        expected_world_revision=expected_world_revision,
    )


def _copy_preserved_blocks(db: Session, previous: Plan, new: Plan, now: datetime) -> None:
    freeze_until = now + timedelta(minutes=FREEZE_HORIZON_MINUTES)
    for block in previous.blocks:
        start = _align(block.starts_at, now)
        preserve = block.status in {"completed", "in_progress"} or (
            block.block_type == BLOCK_GENERATED_ACTION and block.status == "planned" and start <= freeze_until
        )
        if not preserve:
            continue
        copied = PlanBlock(
            user_id=block.user_id,
            plan_id=new.id,
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
            source=block.source,
            decision_factors=block.decision_factors,
            started_at=block.started_at,
            finished_at=block.finished_at,
            actual_duration_minutes=block.actual_duration_minutes,
            outcome_reason=block.outcome_reason,
            note=block.note,
        )
        db.add(copied)
        new.blocks.append(copied)


def replan_remaining_day(
    db: Session,
    user: UserProfile,
    *,
    plan: Plan,
    trigger: str,
    mode: str,
    now: datetime | None = None,
    before_publish_hook=None,
) -> tuple[Plan, PlanDiff]:
    current_time = _now(now)
    payload = _replan_payload(plan, user.world_revision, current_time)
    new_plan = generate_plan(
        db,
        user,
        payload,
        previous_plan=plan,
        replan_reason=trigger,
        plan_diff={"trigger": trigger, "mode": mode},
        before_publish_hook=before_publish_hook,
        planning_now=current_time,
    )
    db.flush()
    new_plan = get_plan(db, user, new_plan.id)
    diff = _diff(plan, new_plan, trigger)
    new_plan.plan_diff = diff.as_dict()
    new_plan.last_replanned_at = current_time
    db.flush()
    return get_plan(db, user, new_plan.id), diff


def evaluate_day(db: Session, user: UserProfile, *, planning_day: date | None = None, now: datetime | None = None, trigger_reason: str = "day_evaluate") -> dict:
    current_time = _now(now)
    plan = get_current_plan(db, user, planning_day)
    if plan is None:
        return {
            "plan": None,
            "control_status": "no_current_plan",
            "replan_reason": None,
            "last_evaluated_at": current_time,
            "last_replanned_at": None,
            "plan_diff": None,
        }

    missed = mark_overdue_blocks_missed(db, user, plan, current_time)
    energy, mental_state = _current_state(db, user)
    material, state_reasons = _material_state_change(plan, energy, mental_state)
    hard_conflict = _hard_conflict_exists(db, user, plan)
    plan.last_evaluated_at = current_time

    if hard_conflict:
        new_plan, diff = replan_remaining_day(db, user, plan=plan, trigger="HARD_CONFLICT", mode="LOCAL_REPAIR", now=current_time)
        return {
            "plan": plan_to_read(new_plan, user.world_revision),
            "control_status": "repaired",
            "replan_reason": "HARD_CONFLICT",
            "last_evaluated_at": current_time,
            "last_replanned_at": new_plan.last_replanned_at,
            "plan_diff": diff.as_dict(),
        }

    if missed:
        new_plan, diff = replan_remaining_day(db, user, plan=plan, trigger="BLOCK_MISSED", mode="LOCAL_REPAIR", now=current_time)
        return {
            "plan": plan_to_read(new_plan, user.world_revision),
            "control_status": "replanned",
            "replan_reason": "BLOCK_MISSED",
            "last_evaluated_at": current_time,
            "last_replanned_at": new_plan.last_replanned_at,
            "plan_diff": diff.as_dict(),
        }

    cooldown_active = (
        plan.last_replanned_at is not None
        and current_time - _align(plan.last_replanned_at, current_time) < timedelta(minutes=STATE_REPLAN_COOLDOWN_MINUTES)
    )
    if material and not cooldown_active:
        trigger = state_reasons[0]
        new_plan, diff = replan_remaining_day(db, user, plan=plan, trigger=trigger, mode="FULL_REPLAN", now=current_time)
        return {
            "plan": plan_to_read(new_plan, user.world_revision),
            "control_status": "replanned",
            "replan_reason": trigger,
            "last_evaluated_at": current_time,
            "last_replanned_at": new_plan.last_replanned_at,
            "plan_diff": diff.as_dict(),
        }

    status_value = "update_suggested" if material else "kept"
    reason = "STATE_REPLAN_COOLDOWN" if material and cooldown_active else ("BLOCK_MISSED" if missed else "NO_CHANGE")
    db.flush()
    return {
        "plan": plan_to_read(get_plan(db, user, plan.id), user.world_revision),
        "control_status": status_value,
        "replan_reason": reason,
        "last_evaluated_at": current_time,
        "last_replanned_at": plan.last_replanned_at,
        "plan_diff": _diff(plan, plan, reason).as_dict(),
    }


def manual_replan(db: Session, user: UserProfile, *, planning_day: date | None = None, reason: str = "USER_REQUESTED", now: datetime | None = None) -> dict:
    current_time = _now(now)
    plan = get_current_plan(db, user, planning_day)
    if plan is None:
        return {
            "plan": None,
            "replan_mode": "KEEP",
            "trigger_reason": "NO_CURRENT_PLAN",
            "control_status": "no_current_plan",
            "plan_diff": _diff(None, None, "NO_CURRENT_PLAN").as_dict(),
            "last_evaluated_at": current_time,
            "last_replanned_at": None,
        }
    new_plan, diff = replan_remaining_day(db, user, plan=plan, trigger=reason, mode="FULL_REPLAN", now=current_time)
    return {
        "plan": plan_to_read(new_plan, user.world_revision),
        "replan_mode": "FULL_REPLAN",
        "trigger_reason": reason,
        "control_status": "replanned",
        "plan_diff": diff.as_dict(),
        "last_evaluated_at": current_time,
        "last_replanned_at": new_plan.last_replanned_at,
    }
