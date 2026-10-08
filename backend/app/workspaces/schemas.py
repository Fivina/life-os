from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceType(str, Enum):
    cooking = "COOKING"
    workout = "WORKOUT"
    study = "STUDY"
    planning = "PLANNING"


class WorkspaceStatus(str, Enum):
    active = "ACTIVE"
    paused = "PAUSED"
    completed = "COMPLETED"
    abandoned = "ABANDONED"


class WorkspacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload_version: Literal[1] = 1


class CookingWorkspacePayload(WorkspacePayload):
    workspace_type: Literal[WorkspaceType.cooking] = WorkspaceType.cooking
    meal_history_ref: str | None = Field(default=None, max_length=160)
    recipe_ref: str | None = Field(default=None, max_length=160)
    recipe_version: int | None = Field(default=None, ge=1)
    meal_plan_ref: str | None = Field(default=None, max_length=160)
    recommendation_ref: str | None = Field(default=None, max_length=160)
    recommendation_option_ref: str | None = Field(default=None, max_length=160)
    current_step: str | None = Field(default=None, max_length=240)
    current_step_index: int | None = Field(default=None, ge=0, le=500)
    previous_step: str | None = Field(default=None, max_length=240)
    step_started_at: datetime | None = None
    servings: float | None = Field(default=None, gt=0, le=100)
    timer_refs: tuple[str, ...] = Field(default=(), max_length=8)
    equipment_refs: tuple[str, ...] = Field(default=(), max_length=16)
    ingredient_change_refs: tuple[str, ...] = Field(default=(), max_length=24)
    temporary_notes: str | None = Field(default=None, max_length=1200)
    current_feedback_note: str | None = Field(default=None, max_length=600)


class WorkoutWorkspacePayload(WorkspacePayload):
    workspace_type: Literal[WorkspaceType.workout] = WorkspaceType.workout
    workout_session_ref: str | None = Field(default=None, max_length=160)
    program_ref: str | None = Field(default=None, max_length=160)
    current_exercise_ref: str | None = Field(default=None, max_length=160)
    current_set_index: int | None = Field(default=None, ge=0, le=500)
    previous_set_ref: str | None = Field(default=None, max_length=160)
    load_kg: float | None = Field(default=None, ge=0, le=2000)
    reps: int | None = Field(default=None, ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=0, le=10)
    rir: float | None = Field(default=None, ge=0, le=20)
    recovery_state: str | None = Field(default=None, max_length=120)
    substitution_refs: tuple[str, ...] = Field(default=(), max_length=12)
    session_phase: str | None = Field(default=None, max_length=80)


class StudyWorkspacePayload(WorkspacePayload):
    workspace_type: Literal[WorkspaceType.study] = WorkspaceType.study
    course_ref: str | None = Field(default=None, max_length=160)
    exam_ref: str | None = Field(default=None, max_length=160)
    topic_ref: str | None = Field(default=None, max_length=160)
    material_ref: str | None = Field(default=None, max_length=160)
    current_question_ref: str | None = Field(default=None, max_length=160)
    current_question_content: str | None = Field(default=None, max_length=2000)
    session_goal: str | None = Field(default=None, max_length=600)
    session_phase: str | None = Field(default=None, max_length=80)
    started_at: datetime | None = None
    effective_minutes: int | None = Field(default=None, ge=0, le=1440)
    quality_self_report: float | None = Field(default=None, ge=0, le=1)
    temporary_note: str | None = Field(default=None, max_length=1200)


class PlanningWorkspacePayload(WorkspacePayload):
    workspace_type: Literal[WorkspaceType.planning] = WorkspaceType.planning
    plan_ref: str | None = Field(default=None, max_length=160)
    plan_version: int | None = Field(default=None, ge=1)
    horizon_start: datetime | None = None
    horizon_end: datetime | None = None
    current_review_section: str | None = Field(default=None, max_length=160)
    candidate_action_refs: tuple[str, ...] = Field(default=(), max_length=24)
    temporary_tradeoff_notes: str | None = Field(default=None, max_length=1600)
    current_phase: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_horizon(self) -> "PlanningWorkspacePayload":
        if self.horizon_start and self.horizon_end and self.horizon_start > self.horizon_end:
            raise ValueError("Planning horizon start must not be after its end.")
        return self


WorkspacePayloadType: TypeAlias = Annotated[
    CookingWorkspacePayload | WorkoutWorkspacePayload | StudyWorkspacePayload | PlanningWorkspacePayload,
    Field(discriminator="workspace_type"),
]


PAYLOAD_MODELS: dict[WorkspaceType, type[WorkspacePayload]] = {
    WorkspaceType.cooking: CookingWorkspacePayload,
    WorkspaceType.workout: WorkoutWorkspacePayload,
    WorkspaceType.study: StudyWorkspacePayload,
    WorkspaceType.planning: PlanningWorkspacePayload,
}


def validate_workspace_payload(
    workspace_type: WorkspaceType | str,
    payload: WorkspacePayload | dict,
) -> WorkspacePayload:
    resolved_type = WorkspaceType(workspace_type)
    model = PAYLOAD_MODELS[resolved_type]
    validated = model.model_validate(payload)
    if validated.workspace_type != resolved_type:
        raise ValueError("Workspace payload type does not match the workspace type.")
    return validated


class ActiveWorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_type: WorkspaceType
    status: WorkspaceStatus
    is_foreground: bool
    conversation_thread_id: str | None
    primary_entity_type: str | None
    primary_entity_id: str | None
    current_phase: str | None
    current_step: str | None
    payload_version: int
    payload: dict
    state_revision: int
    started_at: datetime
    last_meaningful_activity_at: datetime
    updated_at: datetime


def workspace_to_read(row) -> ActiveWorkspaceRead:
    return ActiveWorkspaceRead(
        id=row.id,
        workspace_type=WorkspaceType(row.workspace_type),
        status=WorkspaceStatus(row.status),
        is_foreground=row.is_foreground,
        conversation_thread_id=row.conversation_thread_id,
        primary_entity_type=row.primary_entity_type,
        primary_entity_id=row.primary_entity_id,
        current_phase=row.current_phase,
        current_step=row.current_step,
        payload_version=row.payload_version,
        payload=row.payload_json,
        state_revision=row.state_revision,
        started_at=row.started_at,
        last_meaningful_activity_at=row.last_meaningful_activity_at,
        updated_at=row.updated_at,
    )
