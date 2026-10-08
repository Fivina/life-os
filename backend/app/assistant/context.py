from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.service import list_actions
from app.assistant.schemas import AssistantRole
from app.commitments.service import list_commitments
from app.database.models import PlanBlock, UserProfile
from app.domains.fitness.service import coach_context as fitness_coach_context
from app.domains.fitness.service import status_summary as fitness_status_summary
from app.domains.finance.service import grocery_context as finance_grocery_context
from app.domains.finance.service import overview as finance_overview
from app.domains.kitchen.service import chef_context as kitchen_chef_context
from app.domains.kitchen.service import status_summary as kitchen_status_summary
from app.domains.learning.service import learning_context, status_summary as learning_status_summary
from app.domains.home.service import overview as home_overview
from app.domains.goals.service import overview as goals_overview
from app.planning.service import get_current_plan, plan_to_read
from app.state.service import latest_check_in, latest_state

MAX_PLAN_BLOCKS = 8
MAX_COMMITMENTS = 8
MAX_POOL_ACTIONS = 8


def _local_now(now: datetime | None, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def _current_state_context(db: Session, user: UserProfile) -> dict:
    values = latest_state(db, user)
    check_in = latest_check_in(values)
    return check_in.model_dump(mode="json") if check_in else {"energy": None, "mental_state": None, "observed_at": None}


def _plan_context(db: Session, user: UserProfile, now: datetime) -> dict:
    plan = get_current_plan(db, user, now.date())
    if plan is None:
        return {"plan": None, "blocks": [], "summary_metrics": None, "decision_factors": []}
    read = plan_to_read(plan, user.world_revision)
    futureish = [
        block
        for block in read.blocks
        if block.status in {"planned", "in_progress"} or block.ends_at >= now.replace(tzinfo=block.ends_at.tzinfo)
    ][:MAX_PLAN_BLOCKS]
    return {
        "plan": {
            "id": read.id,
            "planning_day": read.planning_day.isoformat() if read.planning_day else None,
            "generated_from_world_revision": read.generated_from_world_revision,
            "status": read.status,
        },
        "summary_metrics": read.summary_metrics.model_dump(mode="json"),
        "decision_factors": [item.model_dump(mode="json") for item in read.decision_factors[:6]],
        "blocks": [block.model_dump(mode="json") for block in futureish],
        "recent_plan_diff": read.plan_diff,
    }


def _commitments_context(db: Session, user: UserProfile, now: datetime) -> list[dict]:
    day_start = datetime.combine(now.date(), time(0, 0), tzinfo=now.tzinfo)
    day_end = day_start + timedelta(days=1)
    commitments = list_commitments(db, user, status_filter="active", starts_from=day_start, starts_to=day_end)
    return [
        {
            "id": item.id,
            "title": item.title,
            "level": item.level,
            "starts_at": item.starts_at.isoformat() if item.starts_at else None,
            "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "location": item.location,
            "version": item.version,
        }
        for item in commitments[:MAX_COMMITMENTS]
    ]


def _planning_pool_context(db: Session, user: UserProfile) -> list[dict]:
    return [
        {
            "id": item.id,
            "title": item.title,
            "domain": item.domain,
            "level": item.level,
            "deadline": item.deadline.isoformat() if item.deadline else None,
            "estimated_minutes": item.estimated_minutes,
            "completed_minutes": item.completed_minutes,
        }
        for item in list_actions(db, user, planning_pool=True)[:MAX_POOL_ACTIONS]
    ]


class ContextCompiler:
    def compile(
        self,
        db: Session,
        user: UserProfile,
        *,
        role: AssistantRole,
        user_request: str,
        now: datetime | None,
        timezone: str,
        recent_messages: list[dict[str, str]] | None = None,
    ) -> dict:
        current = _local_now(now, timezone)
        base = {
            "role": role,
            "timezone": timezone,
            "now": current.isoformat(),
            "world_revision": user.world_revision,
            "current_state": _current_state_context(db, user),
            "recent_messages": (recent_messages or [])[-4:],
            "context_budget": {
                "plan_blocks": MAX_PLAN_BLOCKS,
                "commitments": MAX_COMMITMENTS,
                "planning_pool_actions": MAX_POOL_ACTIONS,
                "recent_messages": 4,
                "whole_database_included": False,
            },
            "memory": None,
        }
        if role == "FITNESS_COACH":
            base["fitness"] = fitness_coach_context(db, user).model_dump(mode="json")
            base["current_plan"] = _domain_plan_window(db, user, "fitness", current)
            return base
        if role == "LEARNING_COACH":
            base["learning"] = learning_context(db, user).model_dump(mode="json")
            base["current_plan"] = _domain_plan_window(db, user, "learning", current)
            return base
        if role == "CHEF":
            base["kitchen"] = kitchen_chef_context(db, user)
            base["current_plan"] = _domain_plan_window(db, user, "kitchen", current)
            return base
        if role == "HOME_MANAGER":
            base["home"] = home_overview(db, user).model_dump(mode="json")
            base["current_plan"] = _domain_plan_window(db, user, "home", current)
            return base
        if role == "FINANCE_ADVISOR":
            overview = finance_overview(db, user)
            base["finance"] = {
                "month_start": overview.month_start,
                "currency": overview.currency,
                "income": overview.income,
                "spending": overview.spending,
                "category_totals": overview.category_totals,
                "budgets": [item.model_dump(mode="json") for item in overview.budgets],
                "recurring_expenses": [item.model_dump(mode="json") for item in overview.recurring_expenses[:8]],
                "safe_to_spend": overview.safe_to_spend.model_dump(mode="json"),
                "recent_transactions": [item.model_dump(mode="json") for item in overview.recent_transactions[:8]],
                "savings_goals": overview.savings_goals[:5],
                "whole_transaction_history_included": False,
            }
            return base
        learning = learning_status_summary(db, user)
        fitness = fitness_status_summary(db, user)
        kitchen = kitchen_status_summary(db, user)
        home = home_overview(db, user)
        goals = goals_overview(db, user)
        base.update(
            {
                "today": {
                    "plan": _plan_context(db, user, current),
                    "commitments": _commitments_context(db, user, current),
                    "planning_pool": _planning_pool_context(db, user),
                },
                "learning": {
                    "active_exam": learning.active_exam.model_dump(mode="json") if learning.active_exam else None,
                    "upcoming_or_high_risk_exams": [item.model_dump(mode="json") for item in learning.exams[:5]],
                    "candidate_count": len(learning.candidates),
                },
                "fitness": {
                    "active_program": fitness.active_program.model_dump(mode="json") if fitness.active_program else None,
                    "next_workout": fitness.next_workout.model_dump(mode="json") if fitness.next_workout else None,
                    "active_session": fitness.active_session.model_dump(mode="json") if fitness.active_session else None,
                    "readiness": fitness.readiness.model_dump(mode="json"),
                    "workouts_this_week": fitness.workouts_this_week,
                    "weekly_target": fitness.weekly_target,
                },
                "kitchen": {
                    "inventory_count": kitchen.inventory_count,
                    "expiring_lots": kitchen.expiring_lots,
                    "expired_lots": kitchen.expired_lots,
                    "nutrition": kitchen.nutrition.model_dump(mode="json"),
                    "top_recommendation": kitchen.top_recommendation.model_dump(mode="json") if kitchen.top_recommendation else None,
                    "shopping_need_count": kitchen.shopping_need_count,
                    "active_candidate_count": kitchen.active_candidate_count,
                },
                "home": {
                    "due": [item.model_dump(mode="json") for item in home.due[:6]],
                    "upcoming_count": len(home.upcoming),
                    "active_count": home.active_count,
                },
                "goals": {
                    "active": [item.model_dump(mode="json") for item in goals.goals if item.active][:5],
                    "weekly_focus": [item.model_dump(mode="json") for item in goals.weekly_focus],
                },
                "finance": {
                    "authority": "bounded spending capacity only; transaction history omitted",
                    "grocery_budget": finance_grocery_context(db, user).model_dump(mode="json"),
                },
            }
        )
        return base


def _domain_plan_window(db: Session, user: UserProfile, domain: str, now: datetime) -> list[dict]:
    plan = get_current_plan(db, user, now.date())
    if plan is None:
        return []
    blocks = db.scalars(
        select(PlanBlock).where(PlanBlock.plan_id == plan.id, PlanBlock.domain == domain).order_by(PlanBlock.starts_at).limit(6)
    ).all()
    return [
        {
            "id": block.id,
            "title": block.title,
            "starts_at": block.starts_at.isoformat(),
            "ends_at": block.ends_at.isoformat(),
            "status": block.status,
            "decision_factors": block.decision_factors,
            "version": block.version,
        }
        for block in blocks
    ]
