from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.commitments.schemas import ensure_aware


class PlanGenerateRequest(BaseModel):
    planning_date: date | None = None
    horizon_start: datetime | None = None
    horizon_end: datetime | None = None
    timezone: str = "Europe/Berlin"
    expected_world_revision: int | None = None

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @model_validator(mode="after")
    def validate_horizon(self) -> "PlanGenerateRequest":
        if (self.horizon_start is None) != (self.horizon_end is None):
            raise ValueError("horizon_start and horizon_end must be provided together.")
        if self.horizon_start and self.horizon_end and self.horizon_start >= self.horizon_end:
            raise ValueError("horizon_start must be before horizon_end.")
        return self


class DecisionFactorRead(BaseModel):
    factor: str
    contribution: float
    notes: str | None = None


class PlanBlockRead(BaseModel):
    id: str
    source_type: str
    source_id: str | None
    action_id: str | None
    commitment_id: str | None
    domain: str | None
    title: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    block_type: str
    commitment_level: str | None
    movable: bool
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actual_duration_minutes: int | None = None
    outcome_reason: str | None = None
    note: str | None = None
    action_group_id: str | None = None
    variant_type: str | None = None
    frozen_until: datetime | None = None
    user_locked: bool = False
    user_modified: bool = False
    original_starts_at: datetime | None = None
    residual_minutes: int = 0
    decision_factors: list[DecisionFactorRead] = Field(default_factory=list)
    version: int


class UnscheduledActionRead(BaseModel):
    source_action_id: str
    title: str
    reason: str
    score: float
    required_minutes: int = 0
    available_minutes: int = 0
    shortfall_minutes: int = 0
    risk_status: str = "at_risk"


class PlanSummaryRead(BaseModel):
    flexible_work_minutes: int = 0
    hard_commitment_minutes: int = 0
    slack_minutes: int = 0
    actions_scheduled: int = 0
    actions_unscheduled: int = 0
    planning_load: str = "low"
    stress_estimate: int = 0
    stress_threshold: int = 68
    state_band: str = "medium"
    usable_flexible_minutes: int = 0
    required_slack_minutes: int = 0


class PlanRead(BaseModel):
    id: str
    user_id: str
    planner_version: str
    generated_from_world_revision: int | None
    status: str
    planning_day: date | None
    horizon_start: datetime | None
    horizon_end: datetime | None
    generated_at: datetime
    previous_plan_id: str | None = None
    replan_reason: str | None = None
    control_loop_version: str = "v0.4-control-loop"
    plan_diff: dict[str, Any] = Field(default_factory=dict)
    last_evaluated_at: datetime | None = None
    last_replanned_at: datetime | None = None
    summary_metrics: PlanSummaryRead
    decision_factors: list[DecisionFactorRead] = Field(default_factory=list)
    personal_model_snapshot: dict[str, Any] = Field(default_factory=dict)
    personal_model_revision: int = 0
    overload_status: str = "feasible"
    shortfall_minutes: int = 0
    overload: dict[str, Any] = Field(default_factory=dict)
    blocks: list[PlanBlockRead] = Field(default_factory=list)
    unscheduled_actions: list[UnscheduledActionRead] = Field(default_factory=list)
    current_world_revision: int | None = None
    version: int


class PlanBlockExecutionCommand(BaseModel):
    expected_version: int
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class PlanBlockMoveCommand(BaseModel):
    expected_version: int
    starts_at: datetime
    ends_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def move_times_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware(value)

    @model_validator(mode="after")
    def validate_move(self) -> "PlanBlockMoveCommand":
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at.")
        return self


class AllocationRead(BaseModel):
    id: str
    planning_date: date
    action_group_id: str
    source_action_id: str | None
    domain: str
    required_minutes: int
    allocated_minutes: int
    completed_minutes: int
    debt_minutes: int
    deadline: datetime | None
    status: str
    risk_status: str
    reason_json: dict[str, Any]

    model_config = {"from_attributes": True}


class HorizonAllocationRead(BaseModel):
    horizon_start: date
    horizon_end: date
    status: str
    required_minutes: int
    available_minutes: int
    shortfall_minutes: int
    allocations: list[AllocationRead]


class PlanDiffRead(BaseModel):
    previous_plan_id: str | None = None
    new_plan_id: str | None = None
    trigger: str
    kept_block_ids: list[str] = Field(default_factory=list)
    moved_blocks: list[dict[str, Any]] = Field(default_factory=list)
    shortened_blocks: list[dict[str, Any]] = Field(default_factory=list)
    removed_blocks: list[dict[str, Any]] = Field(default_factory=list)
    added_blocks: list[dict[str, Any]] = Field(default_factory=list)
    deferred_action_ids: list[str] = Field(default_factory=list)
    previous_stress: int | None = None
    new_stress: int | None = None
    previous_slack_minutes: int | None = None
    new_slack_minutes: int | None = None


class ReplanRequest(BaseModel):
    reason: str = "user_requested"
    planning_date: date | None = None
    force: bool = False
    now: datetime | None = None

    @field_validator("now")
    @classmethod
    def now_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class ReplanResponse(BaseModel):
    plan: PlanRead | None
    replan_mode: str
    trigger_reason: str
    control_status: str
    plan_diff: PlanDiffRead
    last_evaluated_at: datetime
    last_replanned_at: datetime | None = None


class DayEvaluateRequest(BaseModel):
    planning_date: date | None = None
    now: datetime | None = None
    trigger_reason: str = "day_evaluate"

    @field_validator("now")
    @classmethod
    def now_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class ControlStatusRead(BaseModel):
    plan: PlanRead | None
    control_status: str
    replan_reason: str | None = None
    last_evaluated_at: datetime
    last_replanned_at: datetime | None = None
    plan_diff: PlanDiffRead | None = None


def json_factors(value: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        items = value.get("items", [])
        return items if isinstance(items, list) else []
    if isinstance(value, list):
        return value
    return []
