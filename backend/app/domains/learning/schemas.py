from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.commitments.schemas import ensure_aware


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=80)
    description: str | None = None
    institution: str | None = Field(default=None, max_length=255)
    status: str = "active"


class CourseUpdate(BaseModel):
    expected_version: int
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=80)
    description: str | None = None
    institution: str | None = Field(default=None, max_length=255)
    status: str | None = None


class CourseRead(BaseModel):
    id: str
    name: str
    code: str | None = None
    description: str | None = None
    institution: str | None = None
    status: str
    version: int

    model_config = {"from_attributes": True}


class ExamCreate(BaseModel):
    course_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    exam_at: datetime | None = None
    exam_date: date | None = None
    target_preparation_minutes: int | None = Field(default=None, gt=0)
    estimated_required_hours: float | None = Field(default=None, gt=0)
    minimum_required_preparation_minutes: int | None = Field(default=None, gt=0)
    target_quality_adjusted_minutes: int | None = Field(default=None, gt=0)
    importance: str = "normal"
    attempts_remaining: int | None = Field(default=None, ge=0)
    final_attempt: bool = False
    exam_format: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    status: str = "planned"

    @field_validator("exam_at")
    @classmethod
    def exam_at_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @model_validator(mode="after")
    def target_required(self) -> "ExamCreate":
        if self.target_preparation_minutes is None and self.estimated_required_hours is None:
            raise ValueError("target_preparation_minutes or estimated_required_hours is required.")
        return self


class ExamUpdate(BaseModel):
    expected_version: int
    course_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    exam_at: datetime | None = None
    exam_date: date | None = None
    target_preparation_minutes: int | None = Field(default=None, gt=0)
    minimum_required_preparation_minutes: int | None = Field(default=None, gt=0)
    target_quality_adjusted_minutes: int | None = Field(default=None, gt=0)
    importance: str | None = None
    attempts_remaining: int | None = Field(default=None, ge=0)
    final_attempt: bool | None = None
    exam_format: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    status: str | None = None

    @field_validator("exam_at")
    @classmethod
    def exam_at_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class TopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order_index: int = 0
    importance_weight: float = Field(default=1.0, gt=0)
    estimated_required_minutes: int | None = Field(default=None, gt=0)
    prerequisite_topic_id: str | None = None
    status: str = "open"


class TopicUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    order_index: int | None = None
    importance_weight: float | None = Field(default=None, gt=0)
    estimated_required_minutes: int | None = Field(default=None, gt=0)
    prerequisite_topic_id: str | None = None
    completed_minutes: int | None = Field(default=None, ge=0)
    status: str | None = None


class TopicRead(BaseModel):
    id: str
    exam_id: str
    title: str
    order_index: int
    importance_weight: float
    estimated_required_minutes: int | None = None
    prerequisite_topic_id: str | None = None
    completed_minutes: int
    status: str
    version: int

    model_config = {"from_attributes": True}


class StudySessionCreate(BaseModel):
    course_id: str | None = None
    exam_id: str
    topic_id: str | None = None
    source_action_id: str | None = None
    source_plan_block_id: str | None = None
    occurred_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_minutes: int = Field(gt=0)
    planned_duration_minutes: int | None = Field(default=None, gt=0)
    completion_status: str = "completed"
    location: str | None = None
    context_json: dict[str, Any] = Field(default_factory=dict)
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    focus_quality: int | None = Field(default=None, ge=1, le=5)
    comprehension_quality: int | None = Field(default=None, ge=1, le=5)
    source: str = "manual"
    notes: str | None = None

    @field_validator("occurred_at", "started_at", "completed_at")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class StudySessionRead(BaseModel):
    id: str
    course_id: str | None
    exam_id: str | None
    topic_id: str | None
    source_action_id: str | None
    source_plan_block_id: str | None
    occurred_at: datetime
    started_at: datetime
    completed_at: datetime | None
    duration_minutes: int
    planned_duration_minutes: int | None
    completion_status: str
    location: str | None
    context_json: dict[str, Any]
    quality_rating: int | None
    quality_multiplier: float
    quality_adjusted_minutes: int
    source: str
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class TopicCoverageRead(BaseModel):
    topic_id: str
    title: str
    status: str
    importance_weight: float
    estimated_required_minutes: int | None
    completed_quality_adjusted_minutes: int
    coverage_ratio: float
    prerequisite_topic_id: str | None = None
    prerequisite_satisfied: bool = True


class LearningTrajectoryRead(BaseModel):
    exam_id: str
    strategy_version: str
    target_preparation_minutes: int
    raw_completed_minutes: int
    quality_adjusted_completed_minutes: int
    remaining_quality_adjusted_minutes: int
    days_remaining: float
    hours_remaining: float
    future_capacity_minutes: int
    required_daily_minutes: float
    required_weekly_hours: float
    load_ratio: float | None
    risk: str
    feasible: bool
    shortfall_minutes: int
    shortfall_hours: float
    readiness_score: int
    readiness_label: str
    topic_coverage_ratio: float | None = None
    latest_safe_start: datetime | None = None
    behind_safe_pace: bool
    calculation_notes: dict[str, Any] = Field(default_factory=dict)


class ExamRead(BaseModel):
    id: str
    course_id: str | None
    title: str
    exam_date: date | None
    exam_at: datetime | None
    estimated_required_hours: float
    completed_hours: float
    target_preparation_minutes: int
    minimum_required_preparation_minutes: int | None
    target_quality_adjusted_minutes: int | None
    strategy_version: str
    importance: str
    attempts_remaining: int | None
    final_attempt: bool
    exam_format: str | None
    location: str | None
    notes: str | None
    status: str
    version: int
    course: CourseRead | None = None
    topics: list[TopicRead] = Field(default_factory=list)
    trajectory: LearningTrajectoryRead | None = None

    model_config = {"from_attributes": True}


class LearningCandidateRead(BaseModel):
    candidate_id: str
    title: str
    exam_id: str
    course_id: str | None
    topic_id: str | None
    duration_minutes: int
    minimum_minutes: int
    maximum_minutes: int
    variant: str
    commitment_level: str
    cognitive_load: int
    activation_difficulty: int
    trajectory_value: int
    urgency: int
    neglect_cost: int
    deadline: datetime | None
    prerequisite_satisfied: bool = True
    expected_state_effect: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningStatusRead(BaseModel):
    courses: list[CourseRead]
    exams: list[ExamRead]
    active_exam: ExamRead | None
    candidates: list[LearningCandidateRead]
    recent_sessions: list[StudySessionRead]
    current_learning_plan_window: list[dict[str, Any]]


class LearningContextRead(BaseModel):
    active_exams: list[dict[str, Any]]
    recent_study_sessions: list[dict[str, Any]]
    current_learning_plan_window: list[dict[str, Any]]
    candidate_summary: list[dict[str, Any]]
    allowed_tools: list[str]
