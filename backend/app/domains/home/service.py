from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import HouseholdTask, PlanBlock, UserProfile
from app.domains.base import ActionVariantSpec, DomainRefreshResult, PlanningRequirement
from app.domains.home.schemas import HouseholdOverview, HouseholdTaskCreate, HouseholdTaskRead, HouseholdTaskUpdate
from app.domains.planning import reconcile_requirements
from app.events.service import append_event


HOME_PLANNING_TIMEZONE = "Europe/Berlin"


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def local_planning_date(value: datetime | None = None) -> date:
    zone = ZoneInfo(HOME_PLANNING_TIMEZONE)
    current = datetime.now(zone) if value is None else _aware(value).astimezone(zone)
    return current.date()


def _task(db: Session, user: UserProfile, task_id: str) -> HouseholdTask:
    task = db.scalar(select(HouseholdTask).where(HouseholdTask.id == task_id, HouseholdTask.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household task not found.")
    return task


def next_due(recurrence: dict, anchor: datetime) -> datetime:
    kind = str(recurrence.get("type", "weekly")).lower()
    interval = max(1, int(recurrence.get("interval", recurrence.get("days", 1))))
    if kind == "daily":
        return anchor + timedelta(days=interval)
    if kind in {"interval", "every_n_days", "manual_interval"}:
        return anchor + timedelta(days=interval)
    if kind == "weekly":
        weekdays = sorted({int(item) % 7 for item in recurrence.get("weekdays", [])})
        if weekdays:
            for offset in range(1, 8 * interval + 1):
                candidate = anchor + timedelta(days=offset)
                if candidate.weekday() in weekdays:
                    return candidate
        return anchor + timedelta(weeks=interval)
    if kind == "monthly":
        month_index = anchor.month - 1 + interval
        year = anchor.year + month_index // 12
        month = month_index % 12 + 1
        day = min(int(recurrence.get("day", anchor.day)), monthrange(year, month)[1])
        return anchor.replace(year=year, month=month, day=day)
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported household recurrence type: {kind}.")


def create_task(db: Session, user: UserProfile, payload: HouseholdTaskCreate) -> HouseholdTask:
    anchor = payload.last_completed_at or _now()
    task = HouseholdTask(user_id=user.id, **payload.model_dump(exclude={"next_due_at"}), next_due_at=payload.next_due_at or anchor)
    db.add(task)
    db.flush()
    append_event(db, user, event_type="home.task.created", aggregate_type="household_task", aggregate_id=task.id, payload={"task_id": task.id})
    return task


def update_task(db: Session, user: UserProfile, task_id: str, payload: HouseholdTaskUpdate) -> HouseholdTask:
    task = _task(db, user, task_id)
    if task.version != payload.expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Household task version conflict. Current version is {task.version}.")
    values = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    next_estimated = values.get("estimated_duration_minutes", task.estimated_duration_minutes)
    next_minimum = values.get("minimum_duration_minutes", task.minimum_duration_minutes)
    if next_minimum > next_estimated:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="minimum_duration_minutes must be <= estimated_duration_minutes.")
    for key, value in values.items():
        setattr(task, key, value)
    task.version += 1
    append_event(db, user, event_type="home.task.updated", aggregate_type="household_task", aggregate_id=task.id, payload={"task_id": task.id, "fields": sorted(values)})
    return task


def list_tasks(db: Session, user: UserProfile, *, active_only: bool = False) -> list[HouseholdTask]:
    query = select(HouseholdTask).where(HouseholdTask.user_id == user.id)
    if active_only:
        query = query.where(HouseholdTask.active.is_(True))
    return list(db.scalars(query.order_by(HouseholdTask.next_due_at.asc().nulls_last(), HouseholdTask.title)).all())


def _read(task: HouseholdTask, now: datetime) -> HouseholdTaskRead:
    due = _aware(task.next_due_at) if task.next_due_at else None
    due_status = "inactive" if not task.active else "overdue" if due and due < now else "due" if due and due.date() == now.date() else "upcoming"
    return HouseholdTaskRead(**{key: getattr(task, key) for key in HouseholdTaskRead.model_fields if key not in {"due_status"}}, due_status=due_status)


def overview(db: Session, user: UserProfile, *, now: datetime | None = None) -> HouseholdOverview:
    current = now or _now()
    tasks = list_tasks(db, user)
    reads = [_read(item, current) for item in tasks]
    return HouseholdOverview(
        due=[item for item in reads if item.active and item.due_status in {"due", "overdue"}],
        upcoming=[item for item in reads if item.active and item.due_status == "upcoming"],
        recently_completed=[item for item in sorted(reads, key=lambda row: row.last_completed_at or datetime.min.replace(tzinfo=UTC), reverse=True) if item.last_completed_at][:8],
        active_count=sum(1 for item in reads if item.active),
    )


def requirements(db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date, timezone_name: str = HOME_PLANNING_TIMEZONE) -> list[PlanningRequirement]:
    zone = ZoneInfo(timezone_name)
    horizon_end_at = datetime.combine(horizon_end, time(23, 59), tzinfo=zone)
    current = datetime.now(zone)
    rows: list[PlanningRequirement] = []
    for task in list_tasks(db, user, active_only=True):
        due = _aware(task.next_due_at).astimezone(zone) if task.next_due_at else current
        if due > horizon_end_at:
            continue
        overdue_days = max(0, (current.date() - due.date()).days)
        first_planning_day_end = datetime.combine(horizon_start, time(22, 0), tzinfo=zone)
        planning_deadline = max(due, current + timedelta(hours=4), first_planning_day_end)
        key = f"home:task:{task.id}:due:{due.date().isoformat()}"
        variants = [ActionVariantSpec("full", task.estimated_duration_minutes, task.minimum_duration_minutes, task.estimated_duration_minutes, 2, 1.0)]
        if task.minimum_duration_minutes < task.estimated_duration_minutes:
            variants.append(ActionVariantSpec("minimum", task.minimum_duration_minutes, task.minimum_duration_minutes, task.minimum_duration_minutes, 1, 0.7))
        rows.append(
            PlanningRequirement(
                key=key,
                domain="home",
                title=task.title,
                source_entity_type="household_task",
                source_entity_id=task.id,
                reason=f"Recurring household task is {'overdue by ' + str(overdue_days) + ' days' if overdue_days else 'due'}.",
                deadline=planning_deadline,
                variants=tuple(variants),
                level="maintenance",
                priority=min(100, task.priority + overdue_days * 5),
                location=task.location,
                context="household",
                metadata={"household_task_id": task.id, "due_at": due.isoformat(), "overdue_days": overdue_days, "splittable": False, "maintenance_value": 40, "neglect_cost": min(80, 25 + overdue_days * 5)},
            )
        )
    return rows


def refresh_actions(db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> DomainRefreshResult:
    return reconcile_requirements(db, user, "home", requirements(db, user, horizon_start=horizon_start, horizon_end=horizon_end))


def complete_task(db: Session, user: UserProfile, task_id: str, *, occurred_at: datetime | None = None) -> HouseholdTask:
    task = _task(db, user, task_id)
    when = occurred_at or _now()
    task.last_completed_at = when
    task.next_due_at = next_due(task.recurrence, when)
    task.version += 1
    append_event(db, user, event_type="home.task.completed", aggregate_type="household_task", aggregate_id=task.id, payload={"task_id": task.id, "completed_at": when.isoformat(), "next_due_at": task.next_due_at.isoformat()})
    return task


def complete_plan_block(db: Session, user: UserProfile, block: PlanBlock, occurred_at: datetime) -> HouseholdTask | None:
    if block.domain != "home" or block.action_id is None:
        return None
    from app.database.models import Action

    action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id))
    if action is None or action.source_entity_type != "household_task" or not action.source_entity_id:
        return None
    return complete_task(db, user, action.source_entity_id, occurred_at=occurred_at)


def record_skip(db: Session, user: UserProfile, block: PlanBlock, occurred_at: datetime) -> None:
    if block.domain != "home":
        return
    append_event(db, user, event_type="home.task.skipped", aggregate_type="plan_block", aggregate_id=block.id, payload={"plan_block_id": block.id, "skipped_at": occurred_at.isoformat()}, increment_world_revision=False)
