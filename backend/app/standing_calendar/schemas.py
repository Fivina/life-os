from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, ValidationError, field_validator, model_validator


FixtureStatus = Literal["SCHEDULED", "CONFIRMED", "POSTPONED", "CANCELLED", "COMPLETED"]
_logo_url_adapter = TypeAdapter(HttpUrl)


class NormalizedFixture(BaseModel):
    provider: str
    source_fixture_id: str
    status: FixtureStatus
    kickoff_at: datetime | None = None
    home_team: str
    away_team: str
    home_team_logo_url: str | None = None
    away_team_logo_url: str | None = None
    competition: str | None = None
    venue: str | None = None
    source_updated_at: datetime | None = None
    raw_hash: str
    raw_status: str

    @field_validator("home_team_logo_url", "away_team_logo_url", mode="before")
    @classmethod
    def optional_logo_url(cls, value: Any) -> str | None:
        # Optional provider artwork must not make otherwise valid fixtures fail.
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value.lower().startswith(("https://", "http://")) or "\\" in value or any(character.isspace() or ord(character) < 32 for character in value):
            return None
        try:
            parsed = _logo_url_adapter.validate_python(value)
        except ValidationError:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        return value

    @field_validator("kickoff_at", "source_updated_at")
    @classmethod
    def aware_datetimes(cls, value: datetime | None):
        if value is not None and value.tzinfo is None:
            raise ValueError("Fixture datetimes must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def scheduled_requires_time(self):
        unconfirmed_time = self.status == "SCHEDULED" and self.raw_status == "TBD"
        if self.status in {"SCHEDULED", "CONFIRMED", "COMPLETED"} and self.kickoff_at is None and not unconfirmed_time:
            raise ValueError(f"{self.status} fixture requires kickoff_at.")
        return self


class StandingRuleRead(BaseModel):
    id: str
    name: str
    rule_type: str
    enabled: bool
    protected: bool
    auto_create: bool
    source_provider: str
    source_identity: str
    source_config_json: dict[str, Any]
    sync_interval_days: int
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    last_sync_status: str
    last_sync_summary_json: dict[str, Any]
    last_error: str | None
    next_fixture_selection_known: bool = False
    current_next_fixture_id: str | None = None
    version: int
    model_config = {"from_attributes": True}


class RuleEnabledUpdate(BaseModel):
    enabled: bool
    expected_version: int


class FixtureOverrideRequest(BaseModel):
    protected: bool | None = None
    suppressed: bool | None = None


class FixtureBindingRead(BaseModel):
    id: str
    commitment_id: str | None
    source_provider: str
    source_fixture_id: str
    fixture_status: str
    kickoff_at: datetime | None
    suppressed: bool
    protection_overridden: bool
    normalized_json: dict[str, Any]
    version: int
    model_config = {"from_attributes": True}


class FixtureSyncSummary(BaseModel):
    rule_id: str
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    fetched: int = 0
    created: int = 0
    updated: int = 0
    cancelled: int = 0
    noop: int = 0
    suppressed: int = 0
    error: str | None = None
