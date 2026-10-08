from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class TimeInterval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))


@dataclass(frozen=True)
class CandidateAction:
    source_action_id: str
    domain: str
    title: str
    commitment_level: str
    estimated_minutes: int
    minimum_minutes: int
    maximum_minutes: int
    earliest_start: datetime | None = None
    latest_start: datetime | None = None
    deadline: datetime | None = None
    location: str | None = None
    context: str | None = None
    cognitive_load: int = 45
    physical_load: int = 25
    activation_difficulty: int = 35
    stress_cost: int = 20
    trajectory_value: int = 20
    maintenance_value: int = 0
    neglect_cost: int = 0
    splittable: bool = True
    action_group_id: str | None = None
    variant_type: str = "standard"
    variant_rank: int = 0
    mutually_exclusive: bool = False
    variant_quality: float = 1.0
    allocated_minutes: int | None = None
    debt_minutes: int = 0
    energy_requirement: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanningConstraint:
    name: str
    constraint_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    strength: str = "hard"
    provenance: str = "canonical"
    domain: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    penalty: float = 12.0


@dataclass(frozen=True)
class DecisionFactor:
    factor: str
    contribution: float
    notes: str | None = None


PlanDecisionFactor = DecisionFactor


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: CandidateAction
    score: float
    factors: list[DecisionFactor]


@dataclass(frozen=True)
class CapacityEstimate:
    average_state: int
    available_minutes: int
    required_slack_minutes: int
    usable_flexible_minutes: int
    capacity_ratio: float
    slack_ratio: float
    state_band: str


@dataclass(frozen=True)
class StressEstimate:
    value: int
    threshold: int
    band: str
    factors: list[DecisionFactor]


@dataclass(frozen=True)
class PlanningContext:
    user_id: str
    planning_date: date
    timezone: str
    generated_at: datetime
    generated_from_world_revision: int
    horizon_start: datetime
    horizon_end: datetime
    energy: int
    mental_state: int
    state_observed_at: datetime | None = None
    hard_commitments: list[Any] = field(default_factory=list)
    candidate_actions: list[CandidateAction] = field(default_factory=list)
    constraints: list[PlanningConstraint] = field(default_factory=list)
    preserved_blocks: list[Any] = field(default_factory=list)
    personal_model_snapshot: dict[str, Any] = field(default_factory=dict)
    behavior_patterns: list[dict[str, Any]] = field(default_factory=list)

    @property
    def world_revision(self) -> int:
        return self.generated_from_world_revision

    @property
    def state(self) -> dict[str, Any]:
        return {"energy": self.energy, "mental_state": self.mental_state, "observed_at": self.state_observed_at}


@dataclass(frozen=True)
class PlannedBlock:
    title: str
    block_type: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    source_type: str
    source_id: str | None
    domain: str | None
    commitment_level: str | None
    movable: bool
    action_id: str | None = None
    commitment_id: str | None = None
    action_group_id: str | None = None
    variant_type: str | None = None
    frozen_until: datetime | None = None
    user_locked: bool = False
    user_modified: bool = False
    original_starts_at: datetime | None = None
    status: str = "planned"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actual_duration_minutes: int | None = None
    outcome_reason: str | None = None
    note: str | None = None
    residual_minutes: int = 0
    decision_factors: list[DecisionFactor] = field(default_factory=list)


@dataclass(frozen=True)
class UnscheduledAction:
    source_action_id: str
    title: str
    reason: str
    score: float
    required_minutes: int = 0
    available_minutes: int = 0
    shortfall_minutes: int = 0
    risk_status: str = "at_risk"


@dataclass(frozen=True)
class PlanningResult:
    planner_version: str
    generated_from_world_revision: int
    planning_date: date
    horizon_start: datetime
    horizon_end: datetime
    capacity: CapacityEstimate
    stress: StressEstimate
    blocks: list[PlannedBlock]
    unscheduled_actions: list[UnscheduledAction]
    decision_factors: list[DecisionFactor]
    warnings: list[str] = field(default_factory=list)
    overload_status: str = "feasible"
    shortfall_minutes: int = 0
    overload: dict[str, Any] = field(default_factory=dict)

    @property
    def selected_action_ids(self) -> list[str]:
        return [block.action_id for block in self.blocks if block.action_id is not None]
