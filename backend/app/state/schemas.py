from datetime import datetime

from pydantic import BaseModel, Field


class StateObservationCreate(BaseModel):
    energy: int | None = Field(default=None, ge=0, le=100)
    mental_state: int | None = Field(default=None, ge=0, le=100)
    stress: float | None = Field(default=None, ge=0, le=100)
    sleep_quality: float | None = Field(default=None, ge=0, le=100)
    physical_readiness: float | None = Field(default=None, ge=0, le=100)
    observed_at: datetime | None = None
    notes: str | None = None


class StateObservationRead(BaseModel):
    id: str
    observation_type: str
    value: float
    observed_at: datetime
    source: str
    notes: str | None

    model_config = {"from_attributes": True}


class StateObservationBatchRead(BaseModel):
    observations: list[StateObservationRead]
    world_revision: int


class LatestCheckInRead(BaseModel):
    energy: int | None = None
    mental_state: int | None = None
    observed_at: datetime | None = None
    observation_ids: dict[str, str] = Field(default_factory=dict)


class LatestStateRead(BaseModel):
    values: dict[str, StateObservationRead]
    check_in: LatestCheckInRead | None
    world_revision: int
