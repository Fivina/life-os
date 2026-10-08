from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.decision.schemas import EntityReference


class OpenThreadStatus(str, Enum):
    open = "OPEN"
    resolved = "RESOLVED"
    dismissed = "DISMISSED"
    archived = "ARCHIVED"


class ProspectiveThreadStatus(str, Enum):
    open = "OPEN"
    resolved = "RESOLVED"
    dismissed = "DISMISSED"
    expired = "EXPIRED"
    archived = "ARCHIVED"


class ProspectiveTriggerType(str, Enum):
    date_approaching = "DATE_APPROACHING"
    event_available = "EVENT_AVAILABLE"
    price_below = "PRICE_BELOW"
    schedule_opens = "SCHEDULE_OPENS"
    goal_state_changed = "GOAL_STATE_CHANGED"
    location_relevant = "LOCATION_RELEVANT"
    external_entity_changed = "EXTERNAL_ENTITY_CHANGED"
    manual = "MANUAL"


class TriggerConditions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1


class ManualTriggerConditions(TriggerConditions):
    label: str | None = Field(default=None, max_length=160)


class DateApproachingTriggerConditions(TriggerConditions):
    target_at: datetime | None = None
    lead_minutes: int = Field(default=0, ge=0, le=525_600)


class GoalStateChangedTriggerConditions(TriggerConditions):
    goal_ref: str = Field(min_length=1, max_length=160)
    target_state: str = Field(min_length=1, max_length=120)


class LocationRelevantTriggerConditions(TriggerConditions):
    location: str = Field(min_length=1, max_length=120)


class ExternalObservationTriggerConditions(TriggerConditions):
    observation_key: str = Field(min_length=1, max_length=160)
    expected_value: str | bool | int | float | None = None


TRIGGER_CONDITION_MODELS: dict[ProspectiveTriggerType, type[TriggerConditions]] = {
    ProspectiveTriggerType.manual: ManualTriggerConditions,
    ProspectiveTriggerType.date_approaching: DateApproachingTriggerConditions,
    ProspectiveTriggerType.goal_state_changed: GoalStateChangedTriggerConditions,
    ProspectiveTriggerType.location_relevant: LocationRelevantTriggerConditions,
    ProspectiveTriggerType.event_available: ExternalObservationTriggerConditions,
    ProspectiveTriggerType.price_below: ExternalObservationTriggerConditions,
    ProspectiveTriggerType.schedule_opens: ExternalObservationTriggerConditions,
    ProspectiveTriggerType.external_entity_changed: ExternalObservationTriggerConditions,
}


def validate_trigger_conditions(
    trigger_type: ProspectiveTriggerType | str,
    conditions: TriggerConditions | dict[str, Any],
) -> TriggerConditions:
    return TRIGGER_CONDITION_MODELS[ProspectiveTriggerType(trigger_type)].model_validate(conditions)


class ProspectiveEvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    now: datetime
    manual: bool = False
    location: str | None = Field(default=None, max_length=120)
    goal_states: dict[str, str] = Field(default_factory=dict)
    trigger_observations: dict[str, str | bool | int | float | None] = Field(default_factory=dict)

    @field_validator("goal_states", "trigger_observations")
    @classmethod
    def validate_bounded_mapping(cls, value: dict) -> dict:
        if len(value) > 32:
            raise ValueError("Evaluation context mappings are limited to 32 entries.")
        return value


class ProspectiveEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    thread_id: str
    eligible: bool
    reason_code: str
    evaluated_at: datetime
    expired: bool = False
    observation_ref: str | None = None


ENTITY_REFERENCES = TypeAdapter(tuple[EntityReference, ...])
