from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class HouseholdTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(default="chore", max_length=80)
    recurrence: dict = Field(default_factory=lambda: {"type": "weekly", "interval": 1})
    estimated_duration_minutes: int = Field(default=30, ge=5, le=480)
    minimum_duration_minutes: int = Field(default=15, ge=5, le=480)
    location: str = Field(default="home", max_length=120)
    priority: int = Field(default=50, ge=0, le=100)
    last_completed_at: datetime | None = None
    next_due_at: datetime | None = None
    active: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_duration(self):
        if self.minimum_duration_minutes > self.estimated_duration_minutes:
            raise ValueError("minimum_duration_minutes must be <= estimated_duration_minutes")
        return self


class HouseholdTaskUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=80)
    recurrence: dict | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=5, le=480)
    minimum_duration_minutes: int | None = Field(default=None, ge=5, le=480)
    location: str | None = Field(default=None, max_length=120)
    priority: int | None = Field(default=None, ge=0, le=100)
    next_due_at: datetime | None = None
    active: bool | None = None
    notes: str | None = None


class HouseholdTaskRead(BaseModel):
    id: str
    title: str
    category: str
    recurrence: dict
    estimated_duration_minutes: int
    minimum_duration_minutes: int
    location: str
    priority: int
    last_completed_at: datetime | None
    next_due_at: datetime | None
    active: bool
    notes: str | None
    due_status: str = "upcoming"
    version: int

    model_config = {"from_attributes": True}


class HouseholdOverview(BaseModel):
    due: list[HouseholdTaskRead]
    upcoming: list[HouseholdTaskRead]
    recently_completed: list[HouseholdTaskRead]
    active_count: int


class HouseholdCompleteRequest(BaseModel):
    expected_version: int
    completed_at: datetime | None = None
