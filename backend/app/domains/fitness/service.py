from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionUpdate
from app.actions.service import create_action, list_actions, update_action
from app.database.models import (
    BodyMeasurement,
    Exercise,
    ExerciseSet,
    FitnessGoal,
    Plan,
    PlanBlock,
    ProgressionState,
    RecoveryObservation,
    UserProfile,
    WorkoutProgram,
    WorkoutSession,
    WorkoutTemplate,
    WorkoutTemplateExercise,
    Action,
    Constraint,
)
from app.core.logging import get_logger
from app.domains.base import ActionVariantSpec, PlanningRequirement
from app.domains.planning import reconcile_requirements
from app.domains.fitness.schemas import (
    BodyMeasurementCreate,
    BodyMeasurementRead,
    BodyTrendRead,
    ExerciseCreate,
    ExerciseRead,
    ExerciseSetRead,
    ExerciseUpdate,
    FitnessCandidateRead,
    FitnessContextRead,
    FitnessGoalCreate,
    FitnessGoalRead,
    FitnessStatusRead,
    ProgressionStateRead,
    ReadinessRead,
    RecoveryObservationCreate,
    RecoveryObservationRead,
    TemplateExerciseCreate,
    TemplateExerciseRead,
    TemplateExerciseUpdate,
    TrendMetric,
    WorkoutAbandonRequest,
    WorkoutCompleteRequest,
    WorkoutProgramCreate,
    WorkoutProgramRead,
    WorkoutProgramUpdate,
    WorkoutSessionRead,
    WorkoutSetCreate,
    WorkoutStartRequest,
    WorkoutTemplateCreate,
    WorkoutTemplateRead,
    WorkoutTemplateUpdate,
)
from app.events.service import append_event

logger = get_logger(__name__)

WORKOUT_STATUS_IN_PROGRESS = "in_progress"
WORKOUT_STATUS_COMPLETED = "completed"
WORKOUT_STATUS_ABANDONED = "abandoned"
DEFAULT_WEEKLY_TARGET = 3


def _now() -> datetime:
    return datetime.now(UTC)


def _check_version(record, expected_version: int | None) -> None:
    if expected_version is not None and record.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict. Current version is {record.version}.",
        )


def _get(db: Session, model, user: UserProfile, record_id: str):
    record = db.get(model, record_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found.")
    return record


def _event(db: Session, user: UserProfile, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> None:
    append_event(db, user, event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload, outbox=True)


def _exercise_read(exercise: Exercise | None) -> ExerciseRead | None:
    return ExerciseRead.model_validate(exercise) if exercise is not None else None


def _template_exercise_read(db: Session, item: WorkoutTemplateExercise) -> TemplateExerciseRead:
    exercise = db.get(Exercise, item.exercise_id)
    return TemplateExerciseRead(
        id=item.id,
        template_id=item.template_id,
        exercise_id=item.exercise_id,
        exercise=_exercise_read(exercise),
        order_index=item.order_index,
        target_sets=item.target_sets,
        target_rep_min=item.target_rep_min,
        target_rep_max=item.target_rep_max,
        target_load_kg=item.target_load_kg,
        target_rpe=item.target_rpe,
        rest_seconds=item.rest_seconds,
        progression_rule=item.progression_rule,
        load_increment_kg=item.load_increment_kg,
        notes=item.notes,
        version=item.version,
    )


def template_to_read(db: Session, template: WorkoutTemplate) -> WorkoutTemplateRead:
    items = db.scalars(
        select(WorkoutTemplateExercise)
        .where(WorkoutTemplateExercise.template_id == template.id, WorkoutTemplateExercise.user_id == template.user_id)
        .order_by(WorkoutTemplateExercise.order_index, WorkoutTemplateExercise.created_at)
    ).all()
    return WorkoutTemplateRead(
        id=template.id,
        program_id=template.program_id,
        name=template.name,
        sequence_order=template.sequence_order,
        estimated_duration_minutes=template.estimated_duration_minutes,
        active=template.active,
        notes=template.notes,
        exercises=[_template_exercise_read(db, item) for item in items],
        version=template.version,
    )


def _sets_for_session(db: Session, session: WorkoutSession) -> list[ExerciseSet]:
    return db.scalars(
        select(ExerciseSet)
        .where(ExerciseSet.workout_session_id == session.id, ExerciseSet.user_id == session.user_id)
        .order_by(ExerciseSet.completed_at, ExerciseSet.sequence, ExerciseSet.created_at)
    ).all()


def _progression_for_template(db: Session, user: UserProfile, template_id: str | None) -> list[ProgressionState]:
    if template_id is None:
        return []
    template_exercise_ids = db.scalars(
        select(WorkoutTemplateExercise.id).where(WorkoutTemplateExercise.user_id == user.id, WorkoutTemplateExercise.template_id == template_id)
    ).all()
    if not template_exercise_ids:
        return []
    return db.scalars(
        select(ProgressionState)
        .where(ProgressionState.user_id == user.id, ProgressionState.template_exercise_id.in_(template_exercise_ids))
        .order_by(ProgressionState.updated_at.desc())
    ).all()


def session_to_read(db: Session, user: UserProfile, session: WorkoutSession) -> WorkoutSessionRead:
    template = db.get(WorkoutTemplate, session.workout_template_id) if session.workout_template_id else None
    sets = _sets_for_session(db, session)
    progression = _progression_for_template(db, user, session.workout_template_id)
    return WorkoutSessionRead(
        id=session.id,
        workout_template_id=session.workout_template_id,
        source_action_id=session.source_action_id,
        source_plan_block_id=session.source_plan_block_id,
        started_at=session.started_at,
        completed_at=session.completed_at,
        status=session.status,
        perceived_session_difficulty=session.perceived_session_difficulty,
        notes=session.notes,
        planned_snapshot_json=session.planned_snapshot_json,
        actual_duration_minutes=session.actual_duration_minutes,
        modified=session.modified,
        template=template_to_read(db, template) if template else None,
        sets=[ExerciseSetRead.model_validate(item) for item in sets],
        progression=[ProgressionStateRead.model_validate(item) for item in progression],
        version=session.version,
    )


def add_body_measurement(db: Session, user: UserProfile, payload: BodyMeasurementCreate) -> BodyMeasurement:
    measurement = BodyMeasurement(
        user_id=user.id,
        measured_at=payload.measured_at or _now(),
        body_weight_kg=payload.body_weight_kg,
        body_fat_percentage=payload.body_fat_percentage,
        lean_mass_kg=payload.lean_mass_kg,
        muscle_mass_kg=payload.muscle_mass_kg,
        body_water_percentage=payload.body_water_percentage,
        visceral_fat_rating=payload.visceral_fat_rating,
        bmi=payload.bmi,
        metadata_json=payload.metadata_json,
        source=payload.source,
        notes=payload.notes,
    )
    db.add(measurement)
    db.flush()
    _event(db, user, "fitness.body_measurement.recorded", "body_measurement", measurement.id, {"measurement_id": measurement.id})
    return measurement


def list_body_measurements(db: Session, user: UserProfile) -> list[BodyMeasurement]:
    return db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user.id).order_by(BodyMeasurement.measured_at.desc())
    ).all()


def latest_body_measurement(db: Session, user: UserProfile) -> BodyMeasurement | None:
    return db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user.id).order_by(BodyMeasurement.measured_at.desc()).limit(1)
    ).one_or_none()


def _trend(values: list[tuple[datetime, float]], *, window_days: int = 7, suffix: str = "") -> TrendMetric:
    if not values:
        return TrendMetric(latest=None, rolling_average=None, sample_count=0, window_days=window_days, change=None, direction="unknown", label="No data")
    ordered = sorted(values, key=lambda item: item[0])
    latest_time, latest_value = ordered[-1]
    cutoff = latest_time - timedelta(days=window_days - 1)
    window = [(time, value) for time, value in ordered if time >= cutoff]
    average = round(sum(value for _, value in window) / len(window), 2)
    change = round(average - window[0][1], 2) if window else None
    if change is None or abs(change) < 0.05:
        direction = "flat"
    else:
        direction = "up" if change > 0 else "down"
    sample_note = "rolling 7-day average" if len(window) >= window_days else f"available-sample average ({len(window)})"
    label = f"{average}{suffix} {sample_note}"
    return TrendMetric(
        latest=round(latest_value, 2),
        rolling_average=average,
        sample_count=len(window),
        window_days=window_days,
        change=change,
        direction=direction,
        label=label,
    )


def body_trends(db: Session, user: UserProfile) -> BodyTrendRead:
    measurements = list_body_measurements(db, user)
    chronological = sorted(measurements, key=lambda item: item.measured_at)
    weight_values = [(item.measured_at, item.body_weight_kg) for item in chronological if item.body_weight_kg is not None]
    fat_values = [(item.measured_at, item.body_fat_percentage) for item in chronological if item.body_fat_percentage is not None]
    latest = latest_body_measurement(db, user)
    return BodyTrendRead(
        latest_measurement=BodyMeasurementRead.model_validate(latest) if latest is not None else None,
        weight=_trend(weight_values, suffix=" kg"),
        body_fat=_trend(fat_values, suffix="%"),
    )


def create_goal(db: Session, user: UserProfile, payload: FitnessGoalCreate) -> FitnessGoal:
    if payload.active:
        for item in db.scalars(select(FitnessGoal).where(FitnessGoal.user_id == user.id, FitnessGoal.active.is_(True))).all():
            item.active = False
            item.version += 1
    goal = FitnessGoal(user_id=user.id, **payload.model_dump())
    db.add(goal)
    db.flush()
    _event(db, user, "fitness.goal.updated", "fitness_goal", goal.id, {"goal_id": goal.id})
    return goal


def active_goal(db: Session, user: UserProfile) -> FitnessGoal | None:
    return db.scalar(select(FitnessGoal).where(FitnessGoal.user_id == user.id, FitnessGoal.active.is_(True)).order_by(FitnessGoal.updated_at.desc()))


def create_program(db: Session, user: UserProfile, payload: WorkoutProgramCreate) -> WorkoutProgram:
    if payload.active:
        for program in db.scalars(select(WorkoutProgram).where(WorkoutProgram.user_id == user.id, WorkoutProgram.active.is_(True))).all():
            program.active = False
            program.version += 1
    program = WorkoutProgram(user_id=user.id, **payload.model_dump())
    db.add(program)
    db.flush()
    _event(db, user, "fitness.program.created", "workout_program", program.id, {"program_id": program.id, "active": program.active})
    return program


def list_programs(db: Session, user: UserProfile) -> list[WorkoutProgram]:
    return db.scalars(select(WorkoutProgram).where(WorkoutProgram.user_id == user.id).order_by(WorkoutProgram.active.desc(), WorkoutProgram.created_at.desc())).all()


def update_program(db: Session, user: UserProfile, program_id: str, payload: WorkoutProgramUpdate) -> WorkoutProgram:
    program = _get(db, WorkoutProgram, user, program_id)
    _check_version(program, payload.expected_version)
    data = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if data.get("active") is True:
        for item in db.scalars(select(WorkoutProgram).where(WorkoutProgram.user_id == user.id, WorkoutProgram.id != program.id, WorkoutProgram.active.is_(True))).all():
            item.active = False
            item.version += 1
    for key, value in data.items():
        setattr(program, key, value)
    program.version += 1
    _event(db, user, "fitness.program.updated", "workout_program", program.id, {"program_id": program.id})
    return program


def create_exercise(db: Session, user: UserProfile, payload: ExerciseCreate) -> Exercise:
    exercise = Exercise(user_id=user.id, **payload.model_dump())
    db.add(exercise)
    db.flush()
    _event(db, user, "fitness.exercise.created", "exercise", exercise.id, {"exercise_id": exercise.id, "name": exercise.name})
    return exercise


def list_exercises(db: Session, user: UserProfile) -> list[Exercise]:
    return db.scalars(select(Exercise).where(Exercise.user_id == user.id).order_by(Exercise.active.desc(), Exercise.name)).all()


def update_exercise(db: Session, user: UserProfile, exercise_id: str, payload: ExerciseUpdate) -> Exercise:
    exercise = _get(db, Exercise, user, exercise_id)
    _check_version(exercise, payload.expected_version)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_version"}).items():
        setattr(exercise, key, value)
    exercise.version += 1
    _event(db, user, "fitness.exercise.updated", "exercise", exercise.id, {"exercise_id": exercise.id})
    return exercise


def create_template(db: Session, user: UserProfile, payload: WorkoutTemplateCreate) -> WorkoutTemplate:
    program = _get(db, WorkoutProgram, user, payload.program_id)
    template = WorkoutTemplate(user_id=user.id, program_id=program.id, **payload.model_dump(exclude={"program_id"}))
    db.add(template)
    db.flush()
    _event(db, user, "fitness.template.created", "workout_template", template.id, {"template_id": template.id, "program_id": program.id})
    return template


def list_templates(db: Session, user: UserProfile, program_id: str | None = None) -> list[WorkoutTemplate]:
    query = select(WorkoutTemplate).where(WorkoutTemplate.user_id == user.id)
    if program_id:
        query = query.where(WorkoutTemplate.program_id == program_id)
    return db.scalars(query.order_by(WorkoutTemplate.sequence_order, WorkoutTemplate.created_at)).all()


def update_template(db: Session, user: UserProfile, template_id: str, payload: WorkoutTemplateUpdate) -> WorkoutTemplate:
    template = _get(db, WorkoutTemplate, user, template_id)
    _check_version(template, payload.expected_version)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_version"}).items():
        setattr(template, key, value)
    template.version += 1
    _event(db, user, "fitness.template.updated", "workout_template", template.id, {"template_id": template.id})
    return template


def add_template_exercise(db: Session, user: UserProfile, template_id: str, payload: TemplateExerciseCreate) -> WorkoutTemplateExercise:
    template = _get(db, WorkoutTemplate, user, template_id)
    exercise = _get(db, Exercise, user, payload.exercise_id)
    item = WorkoutTemplateExercise(user_id=user.id, template_id=template.id, exercise_id=exercise.id, **payload.model_dump(exclude={"exercise_id"}))
    db.add(item)
    db.flush()
    _event(db, user, "fitness.template_exercise.added", "workout_template", template.id, {"template_id": template.id, "template_exercise_id": item.id})
    return item


def update_template_exercise(db: Session, user: UserProfile, template_exercise_id: str, payload: TemplateExerciseUpdate) -> WorkoutTemplateExercise:
    item = _get(db, WorkoutTemplateExercise, user, template_exercise_id)
    _check_version(item, payload.expected_version)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_version"}).items():
        setattr(item, key, value)
    item.version += 1
    _event(db, user, "fitness.template_exercise.updated", "workout_template_exercise", item.id, {"template_exercise_id": item.id})
    return item


def active_program(db: Session, user: UserProfile) -> WorkoutProgram | None:
    return db.scalar(select(WorkoutProgram).where(WorkoutProgram.user_id == user.id, WorkoutProgram.active.is_(True), WorkoutProgram.status == "active").order_by(WorkoutProgram.updated_at.desc()))


def next_template(db: Session, user: UserProfile) -> WorkoutTemplate | None:
    program = active_program(db, user)
    if program is None:
        return None
    templates = list_templates(db, user, program.id)
    templates = [item for item in templates if item.active]
    if not templates:
        return None
    last = db.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id, WorkoutSession.status == WORKOUT_STATUS_COMPLETED, WorkoutSession.workout_template_id.in_([item.id for item in templates]))
        .order_by(WorkoutSession.completed_at.desc())
    )
    if last is None or last.workout_template_id is None:
        return templates[0]
    ids = [item.id for item in templates]
    index = ids.index(last.workout_template_id) if last.workout_template_id in ids else -1
    return templates[(index + 1) % len(templates)]


def active_session(db: Session, user: UserProfile) -> WorkoutSession | None:
    return db.scalar(select(WorkoutSession).where(WorkoutSession.user_id == user.id, WorkoutSession.status == WORKOUT_STATUS_IN_PROGRESS).order_by(WorkoutSession.started_at.desc()))


def start_workout(db: Session, user: UserProfile, payload: WorkoutStartRequest) -> WorkoutSession:
    template = _get(db, WorkoutTemplate, user, payload.workout_template_id)
    if not template.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workout template is inactive.")
    exercises = db.scalars(select(WorkoutTemplateExercise).where(WorkoutTemplateExercise.template_id == template.id, WorkoutTemplateExercise.user_id == user.id)).all()
    if not exercises:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workout template has no exercises.")
    existing = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.workout_template_id == template.id,
            WorkoutSession.status == WORKOUT_STATUS_IN_PROGRESS,
        )
    )
    if existing is not None:
        return existing
    session = WorkoutSession(
        user_id=user.id,
        workout_template_id=template.id,
        source_action_id=payload.source_action_id,
        source_plan_block_id=payload.source_plan_block_id,
        started_at=payload.started_at or _now(),
        status=WORKOUT_STATUS_IN_PROGRESS,
        runtime_state={"current_template_exercise_id": sorted(exercises, key=lambda item: item.order_index)[0].id},
        planned_snapshot_json=template_to_read(db, template).model_dump(mode="json"),
    )
    db.add(session)
    db.flush()
    _event(db, user, "fitness.workout.started", "workout_session", session.id, {"session_id": session.id, "template_id": template.id})
    return session


def _next_sequence(db: Session, session: WorkoutSession, template_exercise_id: str) -> int:
    existing = db.scalars(
        select(ExerciseSet.sequence)
        .where(
            ExerciseSet.user_id == session.user_id,
            ExerciseSet.workout_session_id == session.id,
            ExerciseSet.template_exercise_id == template_exercise_id,
        )
        .order_by(ExerciseSet.sequence.desc())
        .limit(1)
    ).first()
    return (existing or 0) + 1


def _previous_load(db: Session, user: UserProfile, exercise_id: str) -> float | None:
    prior = db.scalar(
        select(ExerciseSet)
        .where(ExerciseSet.user_id == user.id, ExerciseSet.exercise_id == exercise_id, ExerciseSet.load_kg.is_not(None))
        .order_by(ExerciseSet.completed_at.desc(), ExerciseSet.created_at.desc())
    )
    return prior.load_kg if prior is not None else None


def log_set(db: Session, user: UserProfile, session_id: str, payload: WorkoutSetCreate, idempotency_key: str | None = None) -> ExerciseSet:
    session = _get(db, WorkoutSession, user, session_id)
    if session.status != WORKOUT_STATUS_IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workout session is not in progress.")
    template_exercise = _get(db, WorkoutTemplateExercise, user, payload.template_exercise_id)
    if template_exercise.template_id != session.workout_template_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template exercise does not belong to this workout.")
    if idempotency_key:
        existing = db.scalar(select(ExerciseSet).where(ExerciseSet.user_id == user.id, ExerciseSet.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    sequence = _next_sequence(db, session, template_exercise.id)
    completed_at = payload.completed_at or _now()
    exercise_set = ExerciseSet(
        user_id=user.id,
        workout_session_id=session.id,
        exercise_id=template_exercise.exercise_id,
        template_exercise_id=template_exercise.id,
        sequence=sequence,
        reps=payload.reps,
        load_kg=payload.load_kg,
        weight_kg=payload.load_kg,
        rpe=payload.rpe,
        perceived_exertion=payload.rpe,
        set_type=payload.set_type,
        completed_at=completed_at,
        note=payload.note,
        completed=True,
        idempotency_key=idempotency_key,
    )
    db.add(exercise_set)
    session.runtime_state = {"last_completed_set_id": exercise_set.id, "last_rest_seconds": template_exercise.rest_seconds}
    session.version += 1
    db.flush()
    _event(
        db,
        user,
        "fitness.set.logged",
        "exercise_set",
        exercise_set.id,
        {
            "session_id": session.id,
            "exercise_id": template_exercise.exercise_id,
            "template_exercise_id": template_exercise.id,
            "sequence": sequence,
            "reps": payload.reps,
            "load_kg": payload.load_kg,
            "rpe": payload.rpe,
            "unit": "kg",
        },
    )
    return exercise_set


def _progression_for_exercise(db: Session, user: UserProfile, session: WorkoutSession, template_exercise: WorkoutTemplateExercise) -> ProgressionState:
    sets = db.scalars(
        select(ExerciseSet)
        .where(
            ExerciseSet.user_id == user.id,
            ExerciseSet.workout_session_id == session.id,
            ExerciseSet.template_exercise_id == template_exercise.id,
            ExerciseSet.set_type == "working",
            ExerciseSet.completed.is_(True),
        )
        .order_by(ExerciseSet.sequence)
    ).all()
    usable = sets[: template_exercise.target_sets]
    load = usable[-1].load_kg if usable else template_exercise.target_load_kg
    rpe_threshold = template_exercise.target_rpe or 8.5
    strong = (
        len(usable) >= template_exercise.target_sets
        and all((item.reps or 0) >= template_exercise.target_rep_max for item in usable)
        and all((item.rpe or 10) <= rpe_threshold for item in usable)
        and load is not None
    )
    weak = len(usable) >= template_exercise.target_sets and any((item.reps or 0) < template_exercise.target_rep_min for item in usable)
    if strong:
        recommendation = "increase"
        recommended = round((load or 0) + template_exercise.load_increment_kg, 2)
        reason = "All required working sets reached the upper rep target within the RPE threshold."
    elif weak:
        recommendation = "maintain"
        recommended = load
        reason = "At least one required working set fell below the lower rep target; maintain load."
    else:
        recommendation = "maintain"
        recommended = load
        reason = "Double progression threshold was not fully satisfied."
    explanation = {
        "rule": "double_progression",
        "previous_load_kg": load,
        "recommended_load_kg": recommended,
        "target_sets": template_exercise.target_sets,
        "target_rep_min": template_exercise.target_rep_min,
        "target_rep_max": template_exercise.target_rep_max,
        "rpe_threshold": rpe_threshold,
        "completed_sets": [{"reps": item.reps, "load_kg": item.load_kg, "rpe": item.rpe} for item in usable],
        "reason": reason,
    }
    state = db.scalar(
        select(ProgressionState).where(
            ProgressionState.user_id == user.id,
            ProgressionState.template_exercise_id == template_exercise.id,
        )
    )
    if state is None:
        state = ProgressionState(
            user_id=user.id,
            template_exercise_id=template_exercise.id,
            exercise_id=template_exercise.exercise_id,
            rule="double_progression",
        )
        db.add(state)
    state.previous_load_kg = load
    state.recommended_load_kg = recommended
    state.recommendation = recommendation
    state.explanation_json = explanation
    state.version = (state.version or 1) + 1
    return state


def update_progression(db: Session, user: UserProfile, session: WorkoutSession) -> list[ProgressionState]:
    if session.workout_template_id is None:
        return []
    items = db.scalars(
        select(WorkoutTemplateExercise)
        .where(WorkoutTemplateExercise.user_id == user.id, WorkoutTemplateExercise.template_id == session.workout_template_id)
        .order_by(WorkoutTemplateExercise.order_index)
    ).all()
    states = [_progression_for_exercise(db, user, session, item) for item in items]
    db.flush()
    return states


def complete_workout(db: Session, user: UserProfile, session_id: str, payload: WorkoutCompleteRequest) -> WorkoutSession:
    session = _get(db, WorkoutSession, user, session_id)
    if session.status != WORKOUT_STATUS_IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workout session is not in progress.")
    if not _sets_for_session(db, session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot complete a workout with no logged sets.")
    session.status = WORKOUT_STATUS_COMPLETED
    session.completed_at = payload.completed_at or _now()
    session.perceived_session_difficulty = payload.perceived_session_difficulty
    session.notes = payload.notes
    started_at = session.started_at
    if started_at.tzinfo is None and session.completed_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=session.completed_at.tzinfo)
    elif started_at.tzinfo is not None and session.completed_at.tzinfo is None:
        session.completed_at = session.completed_at.replace(tzinfo=started_at.tzinfo)
    session.actual_duration_minutes = max(1, round((session.completed_at - started_at).total_seconds() / 60))
    planned_ids = {item.id for item in db.scalars(select(WorkoutTemplateExercise).where(WorkoutTemplateExercise.template_id == session.workout_template_id)).all()}
    actual_ids = {item.template_exercise_id for item in _sets_for_session(db, session) if item.template_exercise_id}
    session.modified = bool(actual_ids and actual_ids != planned_ids)
    session.version += 1
    states = update_progression(db, user, session)
    _event(
        db,
        user,
        "fitness.workout.completed",
        "workout_session",
        session.id,
        {"session_id": session.id, "progression_state_ids": [item.id for item in states]},
    )
    return session


def abandon_workout(db: Session, user: UserProfile, session_id: str, payload: WorkoutAbandonRequest) -> WorkoutSession:
    session = _get(db, WorkoutSession, user, session_id)
    if session.status != WORKOUT_STATUS_IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workout session is not in progress.")
    session.status = WORKOUT_STATUS_ABANDONED
    session.completed_at = payload.abandoned_at or _now()
    session.notes = payload.notes
    session.version += 1
    _event(db, user, "fitness.workout.abandoned", "workout_session", session.id, {"session_id": session.id})
    return session


def exercise_history(db: Session, user: UserProfile, exercise_id: str, limit: int = 12) -> list[ExerciseSet]:
    _get(db, Exercise, user, exercise_id)
    return db.scalars(
        select(ExerciseSet)
        .where(ExerciseSet.user_id == user.id, ExerciseSet.exercise_id == exercise_id, ExerciseSet.completed.is_(True))
        .order_by(ExerciseSet.completed_at.desc(), ExerciseSet.created_at.desc())
        .limit(limit)
    ).all()


def add_recovery_observation(db: Session, user: UserProfile, payload: RecoveryObservationCreate) -> RecoveryObservation:
    observation = RecoveryObservation(user_id=user.id, observed_at=payload.observed_at or _now(), **payload.model_dump(exclude={"observed_at"}))
    db.add(observation)
    db.flush()
    _event(db, user, "fitness.recovery.observed", "recovery_observation", observation.id, {"recovery_observation_id": observation.id})
    return observation


def latest_recovery_observation(db: Session, user: UserProfile) -> RecoveryObservation | None:
    return db.scalar(select(RecoveryObservation).where(RecoveryObservation.user_id == user.id).order_by(RecoveryObservation.observed_at.desc()))


def readiness(db: Session, user: UserProfile) -> ReadinessRead:
    observation = latest_recovery_observation(db, user)
    score = observation.readiness if observation and observation.readiness is not None else 70
    factors: list[dict[str, Any]] = [{"factor": "base_readiness", "contribution": score}]
    if observation is not None:
        if observation.soreness is not None:
            penalty = round(observation.soreness * 0.35)
            score -= penalty
            factors.append({"factor": "soreness", "contribution": -penalty, "value": observation.soreness})
        if observation.stress is not None:
            penalty = round(observation.stress * 0.2)
            score -= penalty
            factors.append({"factor": "stress", "contribution": -penalty, "value": observation.stress})
        if observation.sleep_quality is not None:
            bonus = round((observation.sleep_quality - 50) * 0.25)
            score += bonus
            factors.append({"factor": "sleep_quality", "contribution": bonus, "value": observation.sleep_quality})
    recent_hard = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == WORKOUT_STATUS_COMPLETED,
            WorkoutSession.completed_at >= _now() - timedelta(hours=24),
            WorkoutSession.perceived_session_difficulty >= 8,
        )
    )
    if recent_hard is not None:
        score -= 12
        factors.append({"factor": "recent_hard_session", "contribution": -12})
    score = max(0, min(100, round(score)))
    band = "good" if score >= 70 else "moderate" if score >= 45 else "low"
    return ReadinessRead(
        score=score,
        band=band,
        factors=factors,
        latest_observation=RecoveryObservationRead.model_validate(observation) if observation is not None else None,
    )


def fitness_candidates(db: Session, user: UserProfile) -> list[FitnessCandidateRead]:
    template = next_template(db, user)
    if template is None:
        return []
    read = template_to_read(db, template)
    ready = readiness(db, user)
    variants = [
        ("full", template.estimated_duration_minutes, template.estimated_duration_minutes),
        ("reduced", max(40, round(template.estimated_duration_minutes * 0.8)), max(40, round(template.estimated_duration_minutes * 0.8))),
        ("minimum", min(45, max(25, round(template.estimated_duration_minutes * 0.55))), min(45, max(25, round(template.estimated_duration_minutes * 0.55)))),
    ]
    if ready.band == "low":
        physical_load, activation, trajectory = 58, 54, 34
    elif ready.band == "moderate":
        physical_load, activation, trajectory = 64, 42, 42
    else:
        physical_load, activation, trajectory = 70, 34, 48
    candidates: list[FitnessCandidateRead] = []
    for label, duration, maximum in variants:
        candidates.append(
            FitnessCandidateRead(
                candidate_id=f"fitness:{template.id}:{label}",
                title=f"{template.name} ({label})",
                template_id=template.id,
                duration_minutes=duration,
                minimum_minutes=min(25, duration),
                maximum_minutes=maximum,
                physical_load=physical_load if label != "minimum" else max(35, physical_load - 15),
                activation_difficulty=activation if label != "minimum" else max(20, activation - 12),
                trajectory_value=trajectory if label == "full" else max(20, trajectory - 8),
                expected_state_effect={
                    "energy_cost": "moderate" if label == "full" else "low",
                    "recovery_need": ready.band,
                    "readiness_score": ready.score,
                },
                metadata={"template": read.model_dump(mode="json"), "duration_variant": label, "readiness_band": ready.band},
            )
        )
    return candidates


def planning_requirements(db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> list[PlanningRequirement]:
    program = active_program(db, user)
    if program is None:
        return []
    templates = [
        item
        for item in list_templates(db, user, program.id)
        if item.active and db.scalar(select(WorkoutTemplateExercise.id).where(WorkoutTemplateExercise.template_id == item.id).limit(1)) is not None
    ]
    if not templates:
        return []
    result: list[PlanningRequirement] = []
    carried_action = next(
        (
            item
            for item in list_actions(db, user, status_filter="active", domain="fitness")
            if item.requirement_key and isinstance(item.metadata_json, dict) and item.metadata_json.get("program_id") == program.id
        ),
        None,
    )
    last_session = db.scalar(select(WorkoutSession).where(WorkoutSession.user_id == user.id, WorkoutSession.status == WORKOUT_STATUS_COMPLETED).order_by(WorkoutSession.completed_at.desc()))
    earliest = (last_session.completed_at + timedelta(hours=program.minimum_recovery_hours)) if last_session and last_session.completed_at else None
    priority = 50
    goal_id = None
    try:
        from app.domains.goals.service import priority_signal

        priority, goal_id = priority_signal(db, user, domain="fitness", source_entity_type="workout_program", source_entity_id=program.id)
    except Exception as exc:
        logger.warning(
            "Optional Goals priority signal failed for Fitness",
            extra={"user_id": user.id, "program_id": program.id, "error_type": type(exc).__name__},
        )
    cursor = horizon_start - timedelta(days=horizon_start.weekday())
    while cursor <= horizon_end:
        week_end = cursor + timedelta(days=6)
        completed = list(
            db.scalars(
                select(WorkoutSession).where(
                    WorkoutSession.user_id == user.id,
                    WorkoutSession.status == WORKOUT_STATUS_COMPLETED,
                    WorkoutSession.completed_at >= datetime.combine(cursor, time.min, tzinfo=UTC),
                    WorkoutSession.completed_at <= datetime.combine(week_end, time.max, tzinfo=UTC),
                )
            ).all()
        )
        remaining = max(0, program.weekly_frequency - len(completed))
        last_template_id = completed[-1].workout_template_id if completed else (last_session.workout_template_id if last_session else None)
        ids = [item.id for item in templates]
        start_index = (ids.index(last_template_id) + 1) % len(ids) if last_template_id in ids else 0
        if remaining:
            template = next((item for item in templates if carried_action and item.id == carried_action.source_entity_id), templates[start_index])
            occurrence = len(completed) + 1
            key = carried_action.requirement_key if carried_action else f"fitness:program:{program.id}:week:{cursor.isoformat()}:occurrence:{occurrence}"
            full = template.estimated_duration_minutes
            reduced = max(30, round(full * .7))
            minimum = max(20, min(reduced, round(full * .45)))
            variants = [ActionVariantSpec("full", full, full, full, 3, 1.0)]
            if reduced < full:
                variants.append(ActionVariantSpec("reduced", reduced, reduced, reduced, 2, .8))
            if minimum < reduced:
                variants.append(ActionVariantSpec("minimum", minimum, minimum, minimum, 1, .55))
            result.append(
                PlanningRequirement(
                    key=key,
                    domain="fitness",
                    title=template.name,
                    source_entity_type="workout_template",
                    source_entity_id=template.id,
                    reason=f"Workout {occurrence} of {program.weekly_frequency} for {program.name} is required this week.",
                    deadline=datetime.combine(min(week_end, horizon_end), time(21, 0), tzinfo=UTC),
                    variants=tuple(variants),
                    priority=priority,
                    earliest_start=earliest,
                    location=program.location,
                    context="training",
                    goal_id=goal_id,
                    metadata={"template_id": template.id, "program_id": program.id, "weekly_occurrence": occurrence, "physical_load": 70, "activation_difficulty": 35, "trajectory_value": priority, "splittable": False, "minimum_recovery_hours": program.minimum_recovery_hours},
                )
            )
        if result:
            break
        cursor += timedelta(days=7)
    return result


def sync_candidate_actions(db: Session, user: UserProfile, *, horizon_start: date | None = None, horizon_end: date | None = None) -> list[Action]:
    start = horizon_start or _now().date()
    end = horizon_end or start + timedelta(days=9)
    for action in list_actions(db, user, status_filter="active", domain="fitness"):
        if action.requirement_key is None and isinstance(action.metadata_json, dict) and action.metadata_json.get("fitness_candidate_id"):
            action.status = "archived"
            action.version += 1
    reconcile_requirements(db, user, "fitness", planning_requirements(db, user, horizon_start=start, horizon_end=end))
    _sync_recovery_constraint(db, user)
    return list_actions(db, user, planning_pool=True, domain="fitness")


def _sync_recovery_constraint(db: Session, user: UserProfile) -> Constraint | None:
    program = active_program(db, user)
    name = f"fitness_recovery:{program.id}" if program else "fitness_recovery"
    existing = db.scalar(select(Constraint).where(Constraint.user_id == user.id, Constraint.domain == "fitness", Constraint.name.like("fitness_recovery%"), Constraint.is_active.is_(True)))
    if program is None:
        if existing:
            existing.is_active = False
            existing.version += 1
        return None
    if existing is None:
        existing = Constraint(user_id=user.id, name=name, constraint_type="minimum_recovery_interval", domain="fitness", strength="hard", provenance="canonical")
        db.add(existing)
    existing.name = name
    existing.payload = {"hours": program.minimum_recovery_hours, "program_id": program.id}
    existing.is_active = True
    return existing


def start_fitness_plan_block(db: Session, user: UserProfile, block: PlanBlock, occurred_at: datetime) -> WorkoutSession | None:
    if block.domain != "fitness" or block.action_id is None:
        return None
    action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id))
    template_id = action.source_entity_id if action and action.source_entity_type == "workout_template" else (action.metadata_json or {}).get("template_id") if action else None
    if not template_id:
        return None
    return start_workout(db, user, WorkoutStartRequest(workout_template_id=template_id, source_action_id=action.id, source_plan_block_id=block.id, started_at=occurred_at))


def complete_fitness_plan_block(db: Session, user: UserProfile, block: PlanBlock, actual_minutes: int, occurred_at: datetime, *, partial: bool = False) -> WorkoutSession | None:
    if block.domain != "fitness":
        return None
    session = db.scalar(select(WorkoutSession).where(WorkoutSession.user_id == user.id, WorkoutSession.source_plan_block_id == block.id))
    if session is None:
        session = start_fitness_plan_block(db, user, block, block.started_at or occurred_at)
    if session is None:
        return None
    session.completed_at = occurred_at
    session.actual_duration_minutes = actual_minutes
    session.status = "partially_completed" if partial else WORKOUT_STATUS_COMPLETED
    planned = session.planned_snapshot_json or {}
    session.modified = actual_minutes != block.duration_minutes or not bool(_sets_for_session(db, session))
    session.runtime_state = {**(session.runtime_state or {}), "calendar_outcome": session.status, "actual_set_count": len(_sets_for_session(db, session))}
    session.version += 1
    states = update_progression(db, user, session) if _sets_for_session(db, session) else []
    _event(db, user, "fitness.workout.partially_completed" if partial else "fitness.workout.completed", "workout_session", session.id, {"session_id": session.id, "actual_duration_minutes": actual_minutes, "modified": session.modified, "progression_state_ids": [item.id for item in states], "planned_snapshot_present": bool(planned)})
    return session


def _workouts_this_week_count(db: Session, user: UserProfile) -> int:
    rows = db.scalars(
        select(WorkoutSession.id).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == WORKOUT_STATUS_COMPLETED,
            WorkoutSession.completed_at >= _now() - timedelta(days=7),
        )
    ).all()
    return len(rows)


def status_summary(db: Session, user: UserProfile) -> FitnessStatusRead:
    program = active_program(db, user)
    template = next_template(db, user)
    active = active_session(db, user)
    latest = latest_body_measurement(db, user)
    progression = []
    if template is not None:
        progression = _progression_for_template(db, user, template.id)
    recent = list(db.scalars(select(WorkoutSession).where(WorkoutSession.user_id == user.id, WorkoutSession.status == WORKOUT_STATUS_COMPLETED).order_by(WorkoutSession.completed_at.desc()).limit(8)).all())
    today = _now().date()
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.status == "current", Plan.planning_day == today).order_by(Plan.generated_at.desc()))
    plan_window = [] if plan is None else [
        {"id": block.id, "title": block.title, "starts_at": block.starts_at.isoformat(), "ends_at": block.ends_at.isoformat(), "status": block.status, "variant_type": block.variant_type}
        for block in db.scalars(select(PlanBlock).where(PlanBlock.plan_id == plan.id, PlanBlock.domain == "fitness").order_by(PlanBlock.starts_at)).all()
    ]
    return FitnessStatusRead(
        active_program=WorkoutProgramRead.model_validate(program) if program is not None else None,
        next_workout=template_to_read(db, template) if template is not None else None,
        active_session=session_to_read(db, user, active) if active is not None else None,
        latest_measurement=BodyMeasurementRead.model_validate(latest) if latest is not None else None,
        body_trend=body_trends(db, user),
        readiness=readiness(db, user),
        workouts_this_week=_workouts_this_week_count(db, user),
        weekly_target=program.weekly_frequency if program is not None else DEFAULT_WEEKLY_TARGET,
        progression=[ProgressionStateRead.model_validate(item) for item in progression],
        candidates=fitness_candidates(db, user),
        recent_workouts=[session_to_read(db, user, item) for item in recent],
        current_fitness_plan_window=plan_window,
    )


def coach_context(db: Session, user: UserProfile) -> FitnessContextRead:
    status = status_summary(db, user)
    recent_sets = db.scalars(
        select(ExerciseSet)
        .where(ExerciseSet.user_id == user.id, ExerciseSet.completed.is_(True))
        .order_by(ExerciseSet.completed_at.desc(), ExerciseSet.created_at.desc())
        .limit(12)
    ).all()
    today = _now().date()
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.status == "current", Plan.planning_day == today).order_by(Plan.generated_at.desc()))
    plan_blocks: list[dict[str, Any]] = []
    if plan is not None:
        plan_blocks = [
            {
                "id": block.id,
                "title": block.title,
                "starts_at": block.starts_at.isoformat(),
                "ends_at": block.ends_at.isoformat(),
                "status": block.status,
            }
            for block in db.scalars(
                select(PlanBlock).where(PlanBlock.plan_id == plan.id, PlanBlock.domain == "fitness").order_by(PlanBlock.starts_at)
            ).all()
        ]
    return FitnessContextRead(
        active_program=status.active_program.model_dump(mode="json") if status.active_program else None,
        current_or_next_workout=(
            status.active_session.model_dump(mode="json") if status.active_session else status.next_workout.model_dump(mode="json") if status.next_workout else None
        ),
        progression_state=[item.model_dump(mode="json") for item in status.progression],
        recent_sets=[ExerciseSetRead.model_validate(item).model_dump(mode="json") for item in recent_sets],
        body_trends=status.body_trend.model_dump(mode="json"),
        recovery_readiness=status.readiness.model_dump(mode="json"),
        current_fitness_plan_window=plan_blocks,
        allowed_tools=["start_workout", "record_workout_set", "complete_workout", "add_body_measurement", "get_fitness_status"],
    )
