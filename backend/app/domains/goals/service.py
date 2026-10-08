from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Action, BodyMeasurement, FitnessGoal, Goal, Milestone, Trajectory, UserProfile, WeeklyFocus
from app.domains.goals.schemas import GoalCreate, GoalRead, GoalUpdate, GoalsOverview, MilestoneCreate, MilestoneRead, TrajectoryRead, WeeklyFocusCreate, WeeklyFocusRead
from app.events.service import append_event


def _now() -> datetime:
    return datetime.now(UTC)


def week_start(day: date | None = None) -> date:
    value = day or _now().date()
    return value - timedelta(days=value.weekday())


def _goal(db: Session, user: UserProfile, goal_id: str) -> Goal:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return goal


def create_goal(db: Session, user: UserProfile, payload: GoalCreate) -> Goal:
    goal = Goal(user_id=user.id, **payload.model_dump(), status="active", active=True)
    db.add(goal)
    db.flush()
    append_event(db, user, event_type="goal.created", aggregate_type="goal", aggregate_id=goal.id, payload={"goal_id": goal.id, "domain": goal.domain})
    refresh_trajectory(db, user, goal)
    return goal


def update_goal(db: Session, user: UserProfile, goal_id: str, payload: GoalUpdate) -> Goal:
    goal = _goal(db, user, goal_id)
    if goal.version != payload.expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Goal version conflict. Current version is {goal.version}.")
    values = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    for key, value in values.items():
        setattr(goal, key, value)
    if goal.status == "completed":
        goal.active = False
    goal.version += 1
    append_event(db, user, event_type="goal.updated", aggregate_type="goal", aggregate_id=goal.id, payload={"goal_id": goal.id, "fields": sorted(values)})
    refresh_trajectory(db, user, goal)
    return goal


def list_goals(db: Session, user: UserProfile, *, active_only: bool = False) -> list[Goal]:
    query = select(Goal).where(Goal.user_id == user.id)
    if active_only:
        query = query.where(Goal.active.is_(True), Goal.status == "active")
    return list(db.scalars(query.order_by(Goal.priority.desc(), Goal.target_date.asc().nulls_last(), Goal.created_at)).all())


def _upsert_trajectory(db: Session, user: UserProfile, goal: Goal) -> Trajectory:
    trajectory = db.scalar(select(Trajectory).where(Trajectory.user_id == user.id, Trajectory.goal_id == goal.id))
    if trajectory is None:
        trajectory = Trajectory(user_id=user.id, goal_id=goal.id, name=goal.title)
        db.add(trajectory)
    trajectory.name = goal.title
    trajectory.source_domain = goal.domain
    trajectory.source_entity_type = goal.source_entity_type
    trajectory.source_entity_id = goal.source_entity_id
    trajectory.target_date = goal.target_date
    trajectory.calculated_at = _now()
    return trajectory


def refresh_trajectory(db: Session, user: UserProfile, goal: Goal) -> Trajectory:
    trajectory = _upsert_trajectory(db, user, goal)
    metadata: dict = {"derivation": "manual"}
    if goal.domain == "learning" and goal.source_entity_type == "exam" and goal.source_entity_id:
        from app.domains.learning.service import _get_exam, trajectory_for_exam

        state = trajectory_for_exam(db, user, _get_exam(db, user, goal.source_entity_id))
        trajectory.metric_name = "readiness"
        trajectory.current_value = float(state.readiness_score)
        trajectory.target_value = 100.0
        trajectory.unit = "percent"
        trajectory.status = "on_track" if state.risk in {"low", "moderate"} else "at_risk"
        trajectory.risk = "critical" if state.risk == "infeasible" else state.risk
        trajectory.on_track = state.feasible and state.risk in {"low", "moderate"}
        trajectory.current_rate = None
        trajectory.required_rate = state.required_daily_minutes
        trajectory.target_date = (_get_exam(db, user, goal.source_entity_id).exam_at or datetime.combine(_get_exam(db, user, goal.source_entity_id).exam_date, datetime.min.time(), tzinfo=UTC)).date() if (_get_exam(db, user, goal.source_entity_id).exam_at or _get_exam(db, user, goal.source_entity_id).exam_date) else goal.target_date
        metadata = {"derivation": "learning_exam", "remaining_minutes": state.remaining_quality_adjusted_minutes, "readiness": state.readiness_score, "required_daily_minutes": state.required_daily_minutes}
    elif goal.domain == "fitness":
        fitness_goal = db.scalar(select(FitnessGoal).where(FitnessGoal.user_id == user.id, FitnessGoal.active.is_(True)).order_by(FitnessGoal.created_at.desc()))
        measurement = db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user.id).order_by(BodyMeasurement.measured_at.desc()))
        target = fitness_goal.target_weight_kg if fitness_goal else None
        current = measurement.body_weight_kg if measurement else None
        trajectory.metric_name = "body_weight"
        trajectory.current_value = current
        trajectory.target_value = target
        trajectory.unit = "kg"
        trajectory.on_track = None if current is None or target is None else abs(current - target) <= 1.0
        trajectory.status = "on_track" if trajectory.on_track else "tracking" if current is not None else "insufficient_data"
        trajectory.risk = "low" if trajectory.on_track else "medium" if current is not None else "unknown"
        metadata = {"derivation": "fitness_measurement", "direction": fitness_goal.direction if fitness_goal else None}
    else:
        milestones = list(db.scalars(select(Milestone).where(Milestone.user_id == user.id, Milestone.goal_id == goal.id)).all())
        milestone_progress = round(sum(1 for item in milestones if item.status == "completed") / len(milestones) * 100, 2) if milestones else None
        trajectory.metric_name = "manual_progress"
        trajectory.current_value = milestone_progress if milestone_progress is not None else goal.manual_progress
        trajectory.target_value = 100.0
        trajectory.unit = "percent"
        trajectory.on_track = None
        trajectory.status = "completed" if goal.status == "completed" else "tracking" if trajectory.current_value is not None else "insufficient_data"
        trajectory.risk = "low" if goal.status == "completed" else "unknown"
        metadata = {"derivation": "milestones" if milestones else "manual", "milestone_count": len(milestones)}
    trajectory.metadata_json = metadata
    trajectory.version = (trajectory.version or 1) + 1
    db.flush()
    return trajectory


def refresh_all_trajectories(db: Session, user: UserProfile) -> list[Trajectory]:
    return [refresh_trajectory(db, user, goal) for goal in list_goals(db, user, active_only=True)]


def create_milestone(db: Session, user: UserProfile, goal_id: str, payload: MilestoneCreate) -> Milestone:
    goal = _goal(db, user, goal_id)
    milestone = Milestone(user_id=user.id, goal_id=goal.id, **payload.model_dump())
    db.add(milestone)
    db.flush()
    append_event(db, user, event_type="milestone.created", aggregate_type="milestone", aggregate_id=milestone.id, payload={"milestone_id": milestone.id, "goal_id": goal.id})
    return milestone


def complete_milestone(db: Session, user: UserProfile, milestone_id: str, expected_version: int) -> Milestone:
    milestone = db.scalar(select(Milestone).where(Milestone.id == milestone_id, Milestone.user_id == user.id))
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    if milestone.version != expected_version:
        raise HTTPException(status_code=409, detail=f"Milestone version conflict. Current version is {milestone.version}.")
    milestone.status = "completed"
    milestone.completed_at = _now()
    milestone.version += 1
    append_event(db, user, event_type="milestone.completed", aggregate_type="milestone", aggregate_id=milestone.id, payload={"milestone_id": milestone.id, "goal_id": milestone.goal_id})
    refresh_trajectory(db, user, _goal(db, user, milestone.goal_id))
    return milestone


def add_weekly_focus(db: Session, user: UserProfile, payload: WeeklyFocusCreate) -> WeeklyFocus:
    if payload.goal_id:
        _goal(db, user, payload.goal_id)
    focus = WeeklyFocus(user_id=user.id, week_start=payload.week_start or week_start(), goal_id=payload.goal_id, title=payload.title, priority_boost=payload.priority_boost)
    db.add(focus)
    db.flush()
    append_event(db, user, event_type="weekly_focus.changed", aggregate_type="weekly_focus", aggregate_id=focus.id, payload={"weekly_focus_id": focus.id, "goal_id": focus.goal_id})
    return focus


def current_focus(db: Session, user: UserProfile) -> list[WeeklyFocus]:
    return list(db.scalars(select(WeeklyFocus).where(WeeklyFocus.user_id == user.id, WeeklyFocus.week_start == week_start(), WeeklyFocus.active.is_(True)).order_by(WeeklyFocus.priority_boost.desc())).all())


def priority_signal(db: Session, user: UserProfile, *, domain: str, source_entity_type: str | None = None, source_entity_id: str | None = None) -> tuple[int, str | None]:
    goals = list_goals(db, user, active_only=True)
    matches = [goal for goal in goals if goal.domain == domain and (not goal.source_entity_id or goal.source_entity_id == source_entity_id) and (not goal.source_entity_type or goal.source_entity_type == source_entity_type)]
    if not matches:
        return 50, None
    goal = max(matches, key=lambda item: item.priority)
    boost = sum(item.priority_boost for item in current_focus(db, user) if item.goal_id == goal.id)
    return min(100, goal.priority + boost), goal.id


def goal_to_read(db: Session, user: UserProfile, goal: Goal) -> GoalRead:
    trajectory = db.scalar(select(Trajectory).where(Trajectory.user_id == user.id, Trajectory.goal_id == goal.id)) or refresh_trajectory(db, user, goal)
    milestones = list(db.scalars(select(Milestone).where(Milestone.user_id == user.id, Milestone.goal_id == goal.id).order_by(Milestone.order_index, Milestone.created_at)).all())
    actions = list(db.scalars(select(Action).where(Action.user_id == user.id, Action.goal_id == goal.id, Action.status == "active").order_by(Action.deadline.asc().nulls_last()).limit(8)).all())
    progress = trajectory.current_value if trajectory.metric_name in {"readiness", "manual_progress"} else goal.manual_progress
    return GoalRead(
        id=goal.id, title=goal.title, domain=goal.domain, description=goal.description, status=goal.status, priority=goal.priority,
        horizon=goal.horizon, target_date=goal.target_date, success_condition=goal.success_condition, progress_mode=goal.progress_mode,
        manual_progress=goal.manual_progress, source_entity_type=goal.source_entity_type, source_entity_id=goal.source_entity_id,
        active=goal.active, progress=progress, trajectory=TrajectoryRead.model_validate(trajectory),
        milestones=[MilestoneRead.model_validate(item) for item in milestones],
        linked_upcoming_actions=[{"id": item.id, "title": item.title, "domain": item.domain, "deadline": item.deadline, "requirement_key": item.requirement_key} for item in actions],
        version=goal.version,
    )


def overview(db: Session, user: UserProfile) -> GoalsOverview:
    goals = list_goals(db, user)
    return GoalsOverview(goals=[goal_to_read(db, user, item) for item in goals], weekly_focus=[WeeklyFocusRead.model_validate(item) for item in current_focus(db, user)])
