from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    domain: str = Field(default="personal", max_length=80)
    description: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    horizon: str | None = None
    target_date: date | None = None
    success_condition: str | None = None
    progress_mode: str = "manual"
    manual_progress: float | None = Field(default=None, ge=0, le=100)
    source_entity_type: str | None = None
    source_entity_id: str | None = None


class GoalUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    target_date: date | None = None
    success_condition: str | None = None
    manual_progress: float | None = Field(default=None, ge=0, le=100)
    active: bool | None = None


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_date: date | None = None
    order_index: int = 0


class MilestoneRead(BaseModel):
    id: str
    goal_id: str
    title: str
    description: str | None
    status: str
    target_date: date | None
    order_index: int
    completed_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class TrajectoryRead(BaseModel):
    id: str
    goal_id: str | None
    name: str
    metric_name: str | None
    target_value: float | None
    current_value: float | None
    unit: str | None
    status: str
    risk: str
    on_track: bool | None
    target_date: date | None
    current_rate: float | None
    required_rate: float | None
    source_domain: str | None
    source_entity_type: str | None
    source_entity_id: str | None
    calculated_at: datetime | None
    metadata_json: dict
    version: int

    model_config = {"from_attributes": True}


class GoalRead(BaseModel):
    id: str
    title: str
    domain: str
    description: str | None
    status: str
    priority: int
    horizon: str | None
    target_date: date | None
    success_condition: str | None
    progress_mode: str
    manual_progress: float | None
    source_entity_type: str | None
    source_entity_id: str | None
    active: bool
    progress: float | None = None
    trajectory: TrajectoryRead | None = None
    milestones: list[MilestoneRead] = Field(default_factory=list)
    linked_upcoming_actions: list[dict] = Field(default_factory=list)
    version: int


class WeeklyFocusCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    goal_id: str | None = None
    week_start: date | None = None
    priority_boost: int = Field(default=15, ge=0, le=50)


class WeeklyFocusRead(BaseModel):
    id: str
    week_start: date
    goal_id: str | None
    title: str
    priority_boost: int
    active: bool
    version: int

    model_config = {"from_attributes": True}


class GoalsOverview(BaseModel):
    goals: list[GoalRead]
    weekly_focus: list[WeeklyFocusRead]
