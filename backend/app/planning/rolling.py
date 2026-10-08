from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Action, Commitment, PlanningAllocation, PlanningDebt, UserProfile
from app.events.service import append_event


@dataclass(frozen=True)
class HorizonStatus:
    status: str
    required_minutes: int
    available_minutes: int
    shortfall_minutes: int
    horizon_start: date
    horizon_end: date


def action_group_id(action: Action) -> str:
    return action.candidate_group_id or action.id


def _aware(value: datetime, zone: ZoneInfo) -> datetime:
    return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)


def _remaining(action: Action) -> int:
    return max(0, int(action.estimated_minutes or action.duration_max_minutes or action.duration_min_minutes or 30) - action.completed_minutes)


def _daily_capacity(db: Session, user: UserProfile, day: date, timezone_name: str) -> int:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(day, time(8, 0), tzinfo=zone)
    end = datetime.combine(day, time(22, 0), tzinfo=zone)
    commitments = list(
        db.scalars(
            select(Commitment).where(
                Commitment.user_id == user.id,
                Commitment.status == "active",
                Commitment.level == "hard",
                Commitment.starts_at < end,
                Commitment.ends_at > start,
            )
        ).all()
    )
    fixed = sum(
        max(0, int((min(end, _aware(item.ends_at, zone)) - max(start, _aware(item.starts_at, zone))).total_seconds() // 60))
        for item in commitments
        if item.starts_at and item.ends_at
    )
    free = max(0, 14 * 60 - fixed)
    return max(0, round(free * 0.60) - 60)


class RollingPlanner:
    def refresh(self, db: Session, user: UserProfile, *, start_day: date | None = None, timezone_name: str = "Europe/Berlin") -> HorizonStatus:
        settings = get_settings()
        zone = ZoneInfo(timezone_name)
        first = start_day or datetime.now(zone).date()
        last = first + timedelta(days=settings.planner_horizon_days - 1)
        actions = list(db.scalars(select(Action).where(Action.user_id == user.id, Action.status == "active")).all())
        groups: dict[str, list[Action]] = {}
        for action in actions[: settings.planner_max_candidates]:
            groups.setdefault(action_group_id(action), []).append(action)
        debts = list(db.scalars(select(PlanningDebt).where(PlanningDebt.user_id == user.id, PlanningDebt.status == "open")).all())
        debt_by_group: dict[str, int] = {}
        for debt in debts:
            debt_by_group[debt.action_group_id] = debt_by_group.get(debt.action_group_id, 0) + debt.residual_minutes

        capacities = {first + timedelta(days=offset): _daily_capacity(db, user, first + timedelta(days=offset), timezone_name) for offset in range(settings.planner_horizon_days)}
        remaining_capacity = capacities.copy()
        previous_allocations = list(
            db.scalars(
                select(PlanningAllocation).where(
                    PlanningAllocation.user_id == user.id,
                    PlanningAllocation.planning_date >= first,
                    PlanningAllocation.planning_date <= last,
                )
            ).all()
        )
        completed_by_key = {
            (row.planning_date, row.action_group_id): row.completed_minutes
            for row in previous_allocations
            if row.completed_minutes > 0
        }
        completed_rows = {
            (row.planning_date, row.action_group_id): row
            for row in previous_allocations
            if row.completed_minutes > 0
        }
        db.execute(delete(PlanningAllocation).where(PlanningAllocation.user_id == user.id, PlanningAllocation.planning_date >= first, PlanningAllocation.planning_date <= last))

        required_total = 0
        allocated_total = 0
        ordered = sorted(
            groups.items(),
            key=lambda item: (
                min((_aware(row.deadline, zone) if row.deadline else datetime.max.replace(tzinfo=zone)) for row in item[1]),
                -max({"goal_critical": 3, "maintenance": 2, "optional": 1}.get(row.level, 0) for row in item[1]),
                item[0],
            ),
        )
        for group_id, variants in ordered:
            representative = sorted(variants, key=lambda row: (-row.variant_rank, -(row.estimated_minutes or 0), row.id))[0]
            required = max(max(_remaining(row) for row in variants), debt_by_group.get(group_id, 0))
            required_total += required
            remaining = required
            deadline_day = _aware(representative.deadline, zone).date() if representative.deadline else last
            eligible_days = [day for day in capacities if day <= deadline_day]
            for day in eligible_days:
                if remaining <= 0:
                    break
                amount = min(remaining, remaining_capacity[day])
                if amount <= 0:
                    continue
                remaining_capacity[day] -= amount
                remaining -= amount
                allocated_total += amount
                db.add(
                    PlanningAllocation(
                        user_id=user.id,
                        planning_date=day,
                        action_group_id=group_id,
                        source_action_id=representative.id,
                        domain=representative.domain,
                        required_minutes=required,
                        allocated_minutes=amount,
                        completed_minutes=min(amount, completed_by_key.pop((day, group_id), 0)),
                        debt_minutes=debt_by_group.get(group_id, 0),
                        deadline=representative.deadline,
                        status="allocated",
                        risk_status="feasible" if remaining == 0 else "at_risk",
                        reason_json={"planner": "rolling_v1.3", "remaining_after_day": remaining},
                    )
                )
            if remaining > 0:
                allocated_total += 0

        for key, completed in completed_by_key.items():
            old = completed_rows[key]
            db.add(
                PlanningAllocation(
                    user_id=user.id,
                    planning_date=old.planning_date,
                    action_group_id=old.action_group_id,
                    source_action_id=old.source_action_id,
                    domain=old.domain,
                    required_minutes=old.required_minutes,
                    allocated_minutes=old.allocated_minutes,
                    completed_minutes=completed,
                    debt_minutes=0,
                    deadline=old.deadline,
                    status="completed",
                    risk_status="feasible",
                    reason_json={"planner": "rolling_v1.3", "retained_completion": True},
                )
            )

        shortfall = max(0, required_total - allocated_total)
        available_total = sum(capacities.values())
        status = "impossible_before_deadline" if shortfall > 0 else "tight" if required_total > available_total * 0.85 else "feasible"
        append_event(
            db,
            user,
            event_type="planning.allocation.refreshed",
            aggregate_type="planning_horizon",
            aggregate_id=user.id,
            payload={"horizon_start": first.isoformat(), "horizon_end": last.isoformat(), "required_minutes": required_total, "available_minutes": available_total, "shortfall_minutes": shortfall, "status": status},
            outbox=True,
            increment_world_revision=False,
        )
        db.flush()
        return HorizonStatus(status, required_total, available_total, shortfall, first, last)

    def allocations(self, db: Session, user: UserProfile, *, start_day: date, end_day: date) -> list[PlanningAllocation]:
        return list(
            db.scalars(
                select(PlanningAllocation)
                .where(PlanningAllocation.user_id == user.id, PlanningAllocation.planning_date >= start_day, PlanningAllocation.planning_date <= end_day)
                .order_by(PlanningAllocation.planning_date, PlanningAllocation.domain, PlanningAllocation.action_group_id)
            ).all()
        )
