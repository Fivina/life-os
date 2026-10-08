from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import RecoveryObservation, UserProfile, WorkoutSession
from app.domains.fitness.service import active_goal, active_program


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class FitnessNutritionTarget:
    calorie_target: int | None
    protein_target_g: int | None
    macro_targets: dict[str, float]
    training_day_adjustment: dict[str, int]
    source: str


@dataclass(frozen=True)
class FitnessNutritionContext:
    calories_target_daily: int | None
    protein_target_g: int | None
    carb_target_g: float | None
    fat_target_g: float | None
    recovery_context: str
    workout_today: bool
    workout_recently_completed: bool
    goal_context: str | None
    training_day_adjustment: dict[str, int]
    as_of: datetime
    data_completeness: str
    source_refs: tuple[str, ...]


def nutrition_target(db: Session, user: UserProfile) -> FitnessNutritionTarget:
    goal = active_goal(db, user)
    program = active_program(db, user)
    protein = 160 if goal and goal.direction in {"muscle_gain", "body_recomposition"} else None
    return FitnessNutritionTarget(
        calorie_target=None,
        protein_target_g=protein,
        macro_targets={},
        training_day_adjustment={"calories": 0, "protein_g": 0} if program is None else {"calories": 200, "protein_g": 10},
        source="fitness_domain",
    )


def nutrition_context(db: Session, user: UserProfile, *, now: datetime | None = None) -> FitnessNutritionContext:
    """Expose bounded typed Fitness facts; Kitchen adds its own meal-consumption totals."""
    when = now or datetime.now(UTC)
    goal = active_goal(db, user)
    program = active_program(db, user)
    recent = db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "completed",
            WorkoutSession.completed_at >= when - timedelta(hours=36),
        )
        .order_by(WorkoutSession.completed_at.desc())
    )
    recent_completed_at = _as_utc(recent.completed_at) if recent and recent.completed_at else None
    today = bool(recent_completed_at and recent_completed_at.date() == _as_utc(when).date())
    recovery = db.scalar(
        select(RecoveryObservation)
        .where(RecoveryObservation.user_id == user.id)
        .order_by(RecoveryObservation.observed_at.desc())
    )
    if recent_completed_at and recent_completed_at >= _as_utc(when) - timedelta(hours=6):
        recovery_context = "POST_WORKOUT"
    elif recovery and recovery.readiness is not None and recovery.readiness < 45:
        recovery_context = "LOW_READINESS"
    elif recovery is not None:
        recovery_context = "RECOVERY_REPORTED"
    else:
        recovery_context = "UNKNOWN"
    protein = 160 if goal and goal.direction in {"muscle_gain", "body_recomposition"} else None
    adjustment = {"calories": 200, "protein_g": 10} if today and program is not None else {"calories": 0, "protein_g": 0}
    refs = tuple(filter(None, (goal.id if goal else None, program.id if program else None, recent.id if recent else None, recovery.id if recovery else None)))
    known = sum(value is not None for value in (goal, program, recent, recovery))
    return FitnessNutritionContext(
        calories_target_daily=None,
        protein_target_g=protein,
        carb_target_g=None,
        fat_target_g=None,
        recovery_context=recovery_context,
        workout_today=today,
        workout_recently_completed=bool(recent),
        goal_context=goal.direction if goal else None,
        training_day_adjustment=adjustment,
        as_of=when,
        data_completeness="PARTIAL" if known else "UNKNOWN",
        source_refs=refs,
    )
