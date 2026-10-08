from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.lifecycle import normalize_token


def ensure_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Datetime must include timezone information.")
    return value


class CommitmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    level: str = "hard"
    commitment_type: str = "hard"
    starts_at: datetime | None
    ends_at: datetime | None
    timezone: str = "Europe/Berlin"
    all_day: bool = False
    location: str | None = None
    recurrence: dict = Field(default_factory=dict)
    source: str = "manual"
    notes: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        ensure_aware(value)
        return value

    @field_validator("level", "commitment_type", "source")
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        return normalize_token(value)

    @model_validator(mode="after")
    def validate_time_order(self) -> "CommitmentCreate":
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at.")
        return self


class CommitmentUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    level: str | None = None
    commitment_type: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    all_day: bool | None = None
    location: str | None = None
    recurrence: dict | None = None
    notes: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @field_validator("level", "commitment_type")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return normalize_token(value) if value is not None else None


class CommitmentRead(BaseModel):
    id: str
    title: str
    description: str | None
    level: str
    commitment_type: str
    starts_at: datetime | None
    ends_at: datetime | None
    timezone: str
    all_day: bool
    location: str | None
    recurrence: dict
    source: str
    status: str
    notes: str | None
    version: int
    world_revision: int | None = None

    model_config = {"from_attributes": True}


class StatusCommand(BaseModel):
    expected_version: int
