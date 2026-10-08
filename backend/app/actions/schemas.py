from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.commitments.schemas import ensure_aware
from app.core.lifecycle import normalize_token


class ActionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    domain: str = "personal"
    level: str = "maintenance"
    description: str | None = None
    earliest_start: datetime | None = None
    latest_start: datetime | None = None
    deadline: datetime | None = None
    estimated_minutes: int = Field(gt=0)
    duration_min_minutes: int | None = Field(default=None, gt=0)
    duration_max_minutes: int | None = Field(default=None, gt=0)
    location: str | None = None
    context: str | None = None
    metadata_json: dict = Field(default_factory=dict)
    candidate_group_id: str | None = Field(default=None, max_length=120)
    variant_type: str = "standard"
    variant_rank: int = Field(default=0, ge=0)
    mutually_exclusive: bool = False
    variant_quality: float = Field(default=1.0, ge=0, le=2)
    requirement_key: str | None = Field(default=None, max_length=255)
    source_entity_type: str | None = Field(default=None, max_length=80)
    source_entity_id: str | None = Field(default=None, max_length=36)
    goal_id: str | None = Field(default=None, max_length=36)
    trajectory_id: str | None = Field(default=None, max_length=36)
    generated_reason: str | None = None
    generation_version: str = Field(default="manual", max_length=40)
    planning_priority: int = Field(default=50, ge=0, le=100)

    @field_validator("earliest_start", "latest_start", "deadline")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @field_validator("domain", "level")
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        return normalize_token(value)

    @model_validator(mode="after")
    def validate_windows(self) -> "ActionCreate":
        if self.earliest_start and self.latest_start and self.earliest_start > self.latest_start:
            raise ValueError("earliest_start must be before latest_start.")
        if self.latest_start and self.deadline and self.latest_start > self.deadline:
            raise ValueError("latest_start must be before deadline.")
        if self.duration_min_minutes and self.duration_max_minutes and self.duration_min_minutes > self.duration_max_minutes:
            raise ValueError("duration_min_minutes must be <= duration_max_minutes.")
        return self


class ActionUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = None
    level: str | None = None
    description: str | None = None
    earliest_start: datetime | None = None
    latest_start: datetime | None = None
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    duration_min_minutes: int | None = Field(default=None, gt=0)
    duration_max_minutes: int | None = Field(default=None, gt=0)
    location: str | None = None
    context: str | None = None
    metadata_json: dict | None = None
    candidate_group_id: str | None = Field(default=None, max_length=120)
    variant_type: str | None = None
    variant_rank: int | None = Field(default=None, ge=0)
    mutually_exclusive: bool | None = None
    variant_quality: float | None = Field(default=None, ge=0, le=2)
    requirement_key: str | None = Field(default=None, max_length=255)
    source_entity_type: str | None = Field(default=None, max_length=80)
    source_entity_id: str | None = Field(default=None, max_length=36)
    goal_id: str | None = Field(default=None, max_length=36)
    trajectory_id: str | None = Field(default=None, max_length=36)
    generated_reason: str | None = None
    generation_version: str | None = Field(default=None, max_length=40)
    planning_priority: int | None = Field(default=None, ge=0, le=100)

    @field_validator("earliest_start", "latest_start", "deadline")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @field_validator("domain", "level")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return normalize_token(value) if value is not None else None


class ActionRead(BaseModel):
    id: str
    title: str
    domain: str
    level: str
    description: str | None
    earliest_start: datetime | None
    latest_start: datetime | None
    deadline: datetime | None
    estimated_minutes: int | None
    completed_minutes: int
    duration_min_minutes: int | None
    duration_max_minutes: int | None
    location: str | None
    context: str | None
    status: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    metadata_json: dict
    candidate_group_id: str | None = None
    variant_type: str = "standard"
    variant_rank: int = 0
    mutually_exclusive: bool = False
    variant_quality: float = 1.0
    requirement_key: str | None = None
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    goal_id: str | None = None
    trajectory_id: str | None = None
    generated_reason: str | None = None
    generation_version: str = "manual"
    planning_priority: int = 50
    version: int
    world_revision: int | None = None

    model_config = {"from_attributes": True}


class StatusCommand(BaseModel):
    expected_version: int
