from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.actions.schemas import ActionRead
from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.fitness import service
from app.domains.fitness.contracts import nutrition_target
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

router = APIRouter(prefix="/fitness", tags=["fitness"])


@router.get("/nutrition-target")
def fitness_nutrition_target(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return nutrition_target(db, user)


@router.get("/status", response_model=FitnessStatusRead)
def fitness_status(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.status_summary(db, user)


@router.get("/coach-context", response_model=FitnessContextRead)
def fitness_coach_context(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.coach_context(db, user)


@router.post("/goals", response_model=FitnessGoalRead)
def create_goal(payload: FitnessGoalCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    goal = service.create_goal(db, user, payload)
    db.commit()
    return goal


@router.get("/goals/active", response_model=FitnessGoalRead | None)
def get_active_goal(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.active_goal(db, user)


@router.post("/programs", response_model=WorkoutProgramRead)
def create_program(payload: WorkoutProgramCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    program = service.create_program(db, user, payload)
    db.commit()
    return program


@router.get("/programs", response_model=list[WorkoutProgramRead])
def get_programs(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_programs(db, user)


@router.patch("/programs/{program_id}", response_model=WorkoutProgramRead)
def update_program(program_id: str, payload: WorkoutProgramUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    program = service.update_program(db, user, program_id, payload)
    service.sync_candidate_actions(db, user)
    db.commit()
    return program


@router.post("/exercises", response_model=ExerciseRead)
def create_exercise(payload: ExerciseCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    exercise = service.create_exercise(db, user, payload)
    db.commit()
    return exercise


@router.get("/exercises", response_model=list[ExerciseRead])
def get_exercises(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_exercises(db, user)


@router.patch("/exercises/{exercise_id}", response_model=ExerciseRead)
def update_exercise(exercise_id: str, payload: ExerciseUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    exercise = service.update_exercise(db, user, exercise_id, payload)
    db.commit()
    return exercise


@router.get("/exercises/{exercise_id}/history", response_model=list[ExerciseSetRead])
def exercise_history(exercise_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.exercise_history(db, user, exercise_id)


@router.post("/templates", response_model=WorkoutTemplateRead)
def create_template(payload: WorkoutTemplateCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    template = service.create_template(db, user, payload)
    db.commit()
    return service.template_to_read(db, template)


@router.get("/templates", response_model=list[WorkoutTemplateRead])
def get_templates(program_id: str | None = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return [service.template_to_read(db, item) for item in service.list_templates(db, user, program_id)]


@router.patch("/templates/{template_id}", response_model=WorkoutTemplateRead)
def update_template(template_id: str, payload: WorkoutTemplateUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    template = service.update_template(db, user, template_id, payload)
    db.commit()
    return service.template_to_read(db, template)


@router.post("/templates/{template_id}/exercises", response_model=TemplateExerciseRead)
def add_template_exercise(
    template_id: str,
    payload: TemplateExerciseCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    item = service.add_template_exercise(db, user, template_id, payload)
    service.sync_candidate_actions(db, user)
    db.commit()
    return service._template_exercise_read(db, item)


@router.patch("/template-exercises/{template_exercise_id}", response_model=TemplateExerciseRead)
def update_template_exercise(
    template_exercise_id: str,
    payload: TemplateExerciseUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    item = service.update_template_exercise(db, user, template_exercise_id, payload)
    db.commit()
    return service._template_exercise_read(db, item)


@router.get("/sessions/active", response_model=WorkoutSessionRead | None)
def get_active_session(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    session = service.active_session(db, user)
    return service.session_to_read(db, user, session) if session else None


@router.post("/sessions/start", response_model=WorkoutSessionRead)
def start_workout(
    payload: WorkoutStartRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    session = service.start_workout(db, user, payload)
    db.commit()
    return service.session_to_read(db, user, session)


@router.post("/sessions/{session_id}/sets", response_model=ExerciseSetRead)
def log_set(
    session_id: str,
    payload: WorkoutSetCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    exercise_set = service.log_set(db, user, session_id, payload, idempotency_key)
    db.commit()
    return exercise_set


@router.post("/sessions/{session_id}/complete", response_model=WorkoutSessionRead)
def complete_workout(session_id: str, payload: WorkoutCompleteRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    session = service.complete_workout(db, user, session_id, payload)
    service.sync_candidate_actions(db, user)
    db.commit()
    return service.session_to_read(db, user, session)


@router.post("/sessions/{session_id}/abandon", response_model=WorkoutSessionRead)
def abandon_workout(session_id: str, payload: WorkoutAbandonRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    session = service.abandon_workout(db, user, session_id, payload)
    db.commit()
    return service.session_to_read(db, user, session)


@router.post("/body-measurements", response_model=BodyMeasurementRead)
def create_body_measurement(payload: BodyMeasurementCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    measurement = service.add_body_measurement(db, user, payload)
    db.commit()
    return measurement


@router.get("/body-measurements", response_model=list[BodyMeasurementRead])
def get_body_measurements(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_body_measurements(db, user)


@router.get("/body-measurements/latest", response_model=BodyMeasurementRead)
def get_latest_body_measurement(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    measurement = service.latest_body_measurement(db, user)
    if measurement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No body measurements found.")
    return measurement


@router.get("/body-trends", response_model=BodyTrendRead)
def get_body_trends(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.body_trends(db, user)


@router.post("/recovery", response_model=RecoveryObservationRead)
def create_recovery(payload: RecoveryObservationCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    observation = service.add_recovery_observation(db, user, payload)
    db.commit()
    return observation


@router.get("/readiness", response_model=RecoveryObservationRead | None)
def get_latest_recovery(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.latest_recovery_observation(db, user)


@router.get("/readiness/summary", response_model=ReadinessRead)
def get_readiness_summary(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.readiness(db, user)


@router.get("/candidates", response_model=list[FitnessCandidateRead])
def get_candidates(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.fitness_candidates(db, user)


@router.post("/candidates/sync-actions", response_model=list[ActionRead])
def sync_candidate_actions(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    actions = service.sync_candidate_actions(db, user)
    db.commit()
    return actions


@router.get("/progression", response_model=list[ProgressionStateRead])
def get_progression(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    template = service.next_template(db, user)
    return [ProgressionStateRead.model_validate(item) for item in service._progression_for_template(db, user, template.id if template else None)]
