from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VersionedUpdate(BaseModel):
    expected_version: int | None = None


class BodyMeasurementCreate(BaseModel):
    measured_at: datetime | None = None
    body_weight_kg: float | None = Field(default=None, gt=0, le=500)
    body_fat_percentage: float | None = Field(default=None, ge=0, le=100)
    lean_mass_kg: float | None = Field(default=None, ge=0, le=500)
    muscle_mass_kg: float | None = Field(default=None, ge=0, le=500)
    body_water_percentage: float | None = Field(default=None, ge=0, le=100)
    visceral_fat_rating: float | None = Field(default=None, ge=0)
    bmi: float | None = Field(default=None, ge=0, le=100)
    source: str = "etekcity_scale"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class BodyMeasurementRead(BaseModel):
    id: str
    measured_at: datetime
    body_weight_kg: float | None
    body_fat_percentage: float | None
    lean_mass_kg: float | None
    muscle_mass_kg: float | None
    body_water_percentage: float | None
    visceral_fat_rating: float | None
    bmi: float | None
    source: str
    metadata_json: dict[str, Any]
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class TrendMetric(BaseModel):
    latest: float | None
    rolling_average: float | None
    sample_count: int
    window_days: int
    change: float | None
    direction: str
    label: str


class BodyTrendRead(BaseModel):
    latest_measurement: BodyMeasurementRead | None
    weight: TrendMetric
    body_fat: TrendMetric


class FitnessGoalCreate(BaseModel):
    target_weight_kg: float | None = Field(default=None, gt=0, le=500)
    target_body_fat_percentage: float | None = Field(default=None, ge=0, le=100)
    target_lean_mass_kg: float | None = Field(default=None, ge=0, le=500)
    direction: str = "body_recomposition"
    active: bool = True
    notes: str | None = None


class FitnessGoalRead(BaseModel):
    id: str
    target_weight_kg: float | None
    target_body_fat_percentage: float | None
    target_lean_mass_kg: float | None
    direction: str
    active: bool
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class WorkoutProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    goal_type: str | None = None
    active: bool = True
    weekly_frequency: int = Field(default=3, ge=1, le=7)
    minimum_recovery_hours: int = Field(default=24, ge=0, le=168)
    location: str | None = Field(default="gym", max_length=120)


class WorkoutProgramUpdate(VersionedUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    goal_type: str | None = None
    status: str | None = None
    active: bool | None = None
    weekly_frequency: int | None = Field(default=None, ge=1, le=7)
    minimum_recovery_hours: int | None = Field(default=None, ge=0, le=168)
    location: str | None = Field(default=None, max_length=120)


class WorkoutProgramRead(BaseModel):
    id: str
    name: str
    description: str | None
    goal_type: str | None
    status: str
    active: bool
    weekly_frequency: int
    minimum_recovery_hours: int
    location: str | None
    version: int

    model_config = {"from_attributes": True}


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: str | None = None
    primary_muscle_group: str | None = None
    equipment: str | None = None
    default_rest_seconds: int = Field(default=120, ge=15, le=600)
    active: bool = True
    notes: str | None = None


class ExerciseUpdate(VersionedUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = None
    primary_muscle_group: str | None = None
    equipment: str | None = None
    default_rest_seconds: int | None = Field(default=None, ge=15, le=600)
    active: bool | None = None
    notes: str | None = None


class ExerciseRead(BaseModel):
    id: str
    name: str
    category: str | None
    primary_muscle_group: str | None
    equipment: str | None
    default_rest_seconds: int
    active: bool
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class WorkoutTemplateCreate(BaseModel):
    program_id: str
    name: str = Field(min_length=1, max_length=180)
    sequence_order: int = Field(default=0, ge=0)
    estimated_duration_minutes: int = Field(default=60, ge=10, le=240)
    active: bool = True
    notes: str | None = None


class WorkoutTemplateUpdate(VersionedUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    sequence_order: int | None = Field(default=None, ge=0)
    estimated_duration_minutes: int | None = Field(default=None, ge=10, le=240)
    active: bool | None = None
    notes: str | None = None


class TemplateExerciseCreate(BaseModel):
    exercise_id: str
    order_index: int = Field(default=0, ge=0)
    target_sets: int = Field(default=3, ge=1, le=12)
    target_rep_min: int = Field(default=8, ge=1, le=100)
    target_rep_max: int = Field(default=10, ge=1, le=100)
    target_load_kg: float | None = Field(default=None, ge=0, le=1000)
    target_rpe: float | None = Field(default=8.5, ge=1, le=10)
    rest_seconds: int = Field(default=120, ge=15, le=600)
    progression_rule: str = "double_progression"
    load_increment_kg: float = Field(default=2.5, gt=0, le=25)
    notes: str | None = None

    @field_validator("target_rep_max")
    @classmethod
    def rep_max_must_be_gte_min(cls, value: int, info):
        minimum = info.data.get("target_rep_min")
        if minimum is not None and value < minimum:
            raise ValueError("target_rep_max must be greater than or equal to target_rep_min")
        return value


class TemplateExerciseUpdate(VersionedUpdate):
    order_index: int | None = Field(default=None, ge=0)
    target_sets: int | None = Field(default=None, ge=1, le=12)
    target_rep_min: int | None = Field(default=None, ge=1, le=100)
    target_rep_max: int | None = Field(default=None, ge=1, le=100)
    target_load_kg: float | None = Field(default=None, ge=0, le=1000)
    target_rpe: float | None = Field(default=None, ge=1, le=10)
    rest_seconds: int | None = Field(default=None, ge=15, le=600)
    progression_rule: str | None = None
    load_increment_kg: float | None = Field(default=None, gt=0, le=25)
    notes: str | None = None


class TemplateExerciseRead(BaseModel):
    id: str
    template_id: str
    exercise_id: str
    exercise: ExerciseRead | None = None
    order_index: int
    target_sets: int
    target_rep_min: int
    target_rep_max: int
    target_load_kg: float | None
    target_rpe: float | None
    rest_seconds: int
    progression_rule: str
    load_increment_kg: float
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class WorkoutTemplateRead(BaseModel):
    id: str
    program_id: str
    name: str
    sequence_order: int
    estimated_duration_minutes: int
    active: bool
    notes: str | None
    exercises: list[TemplateExerciseRead] = Field(default_factory=list)
    version: int

    model_config = {"from_attributes": True}


class WorkoutStartRequest(BaseModel):
    workout_template_id: str
    source_action_id: str | None = None
    source_plan_block_id: str | None = None
    started_at: datetime | None = None


class WorkoutSetCreate(BaseModel):
    template_exercise_id: str
    reps: int = Field(ge=0, le=200)
    load_kg: float = Field(ge=0, le=1000)
    rpe: float = Field(ge=1, le=10)
    set_type: str = "working"
    completed_at: datetime | None = None
    note: str | None = None


class WorkoutCompleteRequest(BaseModel):
    perceived_session_difficulty: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = None
    completed_at: datetime | None = None


class WorkoutAbandonRequest(BaseModel):
    notes: str | None = None
    abandoned_at: datetime | None = None


class ExerciseSetRead(BaseModel):
    id: str
    workout_session_id: str | None
    exercise_id: str | None
    template_exercise_id: str | None
    sequence: int
    reps: int | None
    load_kg: float | None
    rpe: float | None
    set_type: str
    completed_at: datetime | None
    note: str | None
    completed: bool
    version: int

    model_config = {"from_attributes": True}


class ProgressionStateRead(BaseModel):
    id: str
    template_exercise_id: str
    exercise_id: str
    rule: str
    previous_load_kg: float | None
    recommended_load_kg: float | None
    recommendation: str
    explanation_json: dict[str, Any]
    version: int

    model_config = {"from_attributes": True}


class WorkoutSessionRead(BaseModel):
    id: str
    workout_template_id: str | None
    source_action_id: str | None
    source_plan_block_id: str | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    perceived_session_difficulty: float | None
    notes: str | None
    planned_snapshot_json: dict[str, Any]
    actual_duration_minutes: int | None
    modified: bool
    template: WorkoutTemplateRead | None = None
    sets: list[ExerciseSetRead] = Field(default_factory=list)
    progression: list[ProgressionStateRead] = Field(default_factory=list)
    version: int

    model_config = {"from_attributes": True}


class RecoveryObservationCreate(BaseModel):
    observed_at: datetime | None = None
    soreness: int | None = Field(default=None, ge=0, le=100)
    sleep_quality: int | None = Field(default=None, ge=0, le=100)
    stress: int | None = Field(default=None, ge=0, le=100)
    readiness: int | None = Field(default=None, ge=0, le=100)
    source: str = "manual"
    notes: str | None = None


class RecoveryObservationRead(BaseModel):
    id: str
    observed_at: datetime
    soreness: int | None
    sleep_quality: int | None
    stress: int | None
    readiness: int | None
    source: str
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class ReadinessRead(BaseModel):
    score: int
    band: str
    factors: list[dict[str, Any]]
    latest_observation: RecoveryObservationRead | None = None


class FitnessCandidateRead(BaseModel):
    candidate_id: str
    title: str
    template_id: str
    duration_minutes: int
    minimum_minutes: int
    maximum_minutes: int
    physical_load: int
    activation_difficulty: int
    trajectory_value: int
    expected_state_effect: dict[str, Any]
    metadata: dict[str, Any]


class FitnessStatusRead(BaseModel):
    active_program: WorkoutProgramRead | None
    next_workout: WorkoutTemplateRead | None
    active_session: WorkoutSessionRead | None
    latest_measurement: BodyMeasurementRead | None
    body_trend: BodyTrendRead
    readiness: ReadinessRead
    workouts_this_week: int
    weekly_target: int = 4
    progression: list[ProgressionStateRead] = Field(default_factory=list)
    candidates: list[FitnessCandidateRead] = Field(default_factory=list)
    recent_workouts: list[WorkoutSessionRead] = Field(default_factory=list)
    current_fitness_plan_window: list[dict[str, Any]] = Field(default_factory=list)


class FitnessContextRead(BaseModel):
    active_program: dict[str, Any] | None
    current_or_next_workout: dict[str, Any] | None
    progression_state: list[dict[str, Any]]
    recent_sets: list[dict[str, Any]]
    body_trends: dict[str, Any]
    recovery_readiness: dict[str, Any]
    current_fitness_plan_window: list[dict[str, Any]]
    allowed_tools: list[str]
