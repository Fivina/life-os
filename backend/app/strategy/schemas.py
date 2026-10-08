from __future__ import annotations

from datetime import datetime
from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.attention.schemas import AttentionAction


CALCULATION_VERSION = "trajectory-calculation-v1"
INTERVENTION_POLICY_VERSION = "strategic-intervention-v1"
PROPOSAL_POLICY_VERSION = "plan-proposal-v1"


class DataCompleteness(str, Enum):
    complete = "COMPLETE"
    partial = "PARTIAL"
    insufficient = "INSUFFICIENT"


class DeviationType(str, Enum):
    pace_shortfall = "PACE_SHORTFALL"
    capacity_shortfall = "CAPACITY_SHORTFALL"
    missed_critical_work = "MISSED_CRITICAL_WORK"
    readiness_below_trajectory = "READINESS_BELOW_TRAJECTORY"
    planning_debt_surge = "PLANNING_DEBT_SURGE"
    deadline_pressure = "DEADLINE_PRESSURE"
    underallocation = "UNDERALLOCATION"
    plan_assumption_invalidated = "PLAN_ASSUMPTION_INVALIDATED"


class DeviationSeverity(str, Enum):
    none = "NONE"
    low = "LOW"
    moderate = "MODERATE"
    high = "HIGH"
    critical = "CRITICAL"


class Recoverability(str, Enum):
    existing_capacity = "EXISTING_UNUSED_CAPACITY"
    low_cost_reallocation = "LOW_COST_REALLOCATION"
    meaningful_tradeoff = "MEANINGFUL_TRADEOFF"
    unrecoverable = "UNRECOVERABLE_CURRENT_ASSUMPTIONS"
    unknown = "UNKNOWN"


class AuthorityLevel(IntEnum):
    observe = 0
    silent_repair_within_rules = 1
    prepare_proposal = 2
    ask_or_discuss_tradeoff = 3
    urgent_attention = 4


class ProposalStatus(str, Enum):
    draft = "DRAFT"
    presented = "PRESENTED"
    accepted = "ACCEPTED"
    modified = "MODIFIED"
    rejected = "REJECTED"
    expired = "EXPIRED"
    apply_failed = "APPLY_FAILED"


class ProposalChangeType(str, Enum):
    move = "MOVE"
    increase = "INCREASE"
    decrease = "DECREASE"
    change_variant = "CHANGE_REQUIREMENT_VARIANT"
    reallocate = "REALLOCATE"
    add_recovery = "ADD_RECOVERY_BLOCK"
    remove_optional = "REMOVE_OPTIONAL_ALLOCATION"


class ExamTrajectorySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exam_id: str
    course_id: str | None = None
    exam_title: str
    as_of: datetime
    exam_at: datetime | None = None
    days_remaining: float | None = None
    total_workload_minutes: int | None = None
    workload_source: str | None = None
    completed_effective_minutes: int
    remaining_workload_minutes: int | None = None
    planned_future_minutes: int
    recent_actual_effective_minutes: int
    recent_window_days: int
    actual_weekly_pace_minutes: float | None = None
    required_weekly_pace_minutes: float | None = None
    pace_gap_minutes: float | None = None
    future_capacity_minutes: int | None = None
    future_allocated_minutes: int
    capacity_shortfall_minutes: int | None = None
    projected_shortfall_minutes: int | None = None
    planning_debt_minutes: int
    readiness_score: int | None = None
    readiness_source: str | None = None
    buffer_minutes: int | None = None
    risk_indicators: tuple[str, ...] = ()
    completeness: DataCompleteness
    completeness_score: float = Field(ge=0, le=1)
    unavailable_metrics: tuple[str, ...] = ()
    source_world_revision: int = Field(ge=0)
    calculation_version: str = CALCULATION_VERSION


class StrategicDeviation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exam_id: str
    deviation_types: tuple[DeviationType, ...]
    severity: DeviationSeverity
    recoverability: Recoverability
    magnitude_minutes: int
    days_remaining: float | None = None
    evidence_quality: float = Field(ge=0, le=1)
    reason_codes: tuple[str, ...]
    fingerprint: str = Field(min_length=64, max_length=64)
    calculation_version: str = CALCULATION_VERSION


class InterventionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_level: AuthorityLevel
    attention_action: AttentionAction
    reason_code: str
    priority: int = Field(ge=0, le=100)
    urgency: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    provider_judgment: str | None = None
    source_trace_id: str | None = None
    policy_version: str = INTERVENTION_POLICY_VERSION


class ProposalModificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_target_minutes: int | None = Field(default=None, ge=10, le=720)
    protected_block_ids: list[str] = Field(default_factory=list, max_length=24)
    minimum_exam_minutes: dict[str, int] = Field(default_factory=dict)
    preferred_day: datetime | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("minimum_exam_minutes")
    @classmethod
    def validate_minimums(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 12 or any(minutes < 0 or minutes > 10_080 for minutes in value.values()):
            raise ValueError("Exam minimums must contain at most 12 bounded minute values.")
        return value


class PlanProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_id: str
    source_trace_id: str | None
    parent_proposal_id: str | None
    current_plan_id: str
    current_plan_version: int
    current_world_revision: int
    applied_plan_id: str | None
    trigger: str
    reason_code: str
    trajectory_snapshot: dict[str, Any]
    deviation: dict[str, Any]
    candidate_plan: dict[str, Any]
    changes: list[dict[str, Any]]
    expected_effects: dict[str, Any]
    tradeoffs: list[dict[str, Any]]
    confidence: dict[str, Any]
    modification: dict[str, Any]
    authority_level: int
    attention_action: AttentionAction
    status: ProposalStatus
    expires_at: datetime
    presented_at: datetime | None
    accepted_at: datetime | None
    modified_at: datetime | None
    rejected_at: datetime | None
    expired_at: datetime | None
    policy_version: str
    planner_version: str
    calculation_version: str
    created_at: datetime
    updated_at: datetime
    version: int


class StrategicEvaluationRead(BaseModel):
    snapshot: ExamTrajectorySnapshot
    deviation: StrategicDeviation | None
    intervention: InterventionDecision
    proposal: PlanProposalRead | None = None
    deduplicated: bool = False
