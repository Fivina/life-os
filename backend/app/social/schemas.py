from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpportunityType(str, Enum):
    cinema = "CINEMA"
    concert = "CONCERT"
    football = "FOOTBALL"
    exhibition = "EXHIBITION"
    festival = "FESTIVAL"
    meetup = "MEETUP"
    restaurant = "RESTAURANT"
    social_activity = "SOCIAL_ACTIVITY"
    night_out = "NIGHT_OUT"
    museum = "MUSEUM"
    game_release = "GAME_RELEASE"
    seasonal_activity = "SEASONAL_ACTIVITY"
    trip = "TRIP"
    sport = "SPORT"
    workshop = "WORKSHOP"
    other = "OTHER"


class SocialActionType(str, Enum):
    call_friend = "CALL_FRIEND"
    message_friend = "MESSAGE_FRIEND"
    casual_drink = "CASUAL_DRINK"
    dinner_with_friend = "DINNER_WITH_FRIEND"
    walk_with_friend = "WALK_WITH_FRIEND"


class SocialTrajectoryUpdate(BaseModel):
    enabled: bool = True
    target_min: int = Field(default=2, ge=0, le=21)
    target_max: int = Field(default=3, ge=0, le=21)
    week_starts_on: int = Field(default=0, ge=0, le=6)

    @model_validator(mode="after")
    def validate_range(self) -> "SocialTrajectoryUpdate":
        if self.target_max < self.target_min:
            raise ValueError("target_max must be greater than or equal to target_min")
        return self


class SocialTrajectoryRead(BaseModel):
    goal_id: str
    trajectory_id: str
    enabled: bool
    period: Literal["WEEK"] = "WEEK"
    target_min: int
    target_max: int
    week_starts_on: int
    period_start: datetime
    period_end: datetime
    completed_count: int
    state: Literal["BELOW_RANGE", "IN_RANGE", "ABOVE_RANGE", "DISABLED"]
    remaining_to_min: int
    qualification: str


class SocialActivityCreate(BaseModel):
    activity_type: OpportunityType = OpportunityType.social_activity
    title: str = Field(min_length=1, max_length=255)
    occurred_at: datetime
    meaningful: bool = True
    source: str = Field(default="manual", max_length=80)
    source_ref: str | None = Field(default=None, max_length=180)
    idempotency_key: str | None = Field(default=None, max_length=180)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SocialActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    activity_type: str
    title: str
    occurred_at: datetime
    meaningful: bool
    source: str
    source_ref: str | None


class DiscoveryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    window_start: datetime
    window_end: datetime
    categories: tuple[OpportunityType, ...] = ()
    max_results: int = Field(default=100, ge=1, le=200)


class NormalizedOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=80)
    external_id: str = Field(min_length=1, max_length=180)
    opportunity_type: OpportunityType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20_000)
    starts_at: datetime
    ends_at: datetime | None = None
    timezone: str = Field(default="Europe/Berlin", max_length=80)
    venue: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    source_url: str | None = Field(default=None, max_length=1000)
    cost_min: Decimal | None = Field(default=None, ge=0)
    cost_max: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    pricing_source: str | None = Field(default=None, max_length=80)
    status: Literal["ACTIVE", "ENDED", "CANCELLED", "STALE", "ARCHIVED"] = "ACTIVE"
    tags: tuple[str, ...] = ()
    entities: tuple[dict[str, Any], ...] = ()
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_values(self) -> "NormalizedOpportunity":
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not precede starts_at")
        if self.cost_max is not None and self.cost_min is not None and self.cost_max < self.cost_min:
            raise ValueError("cost_max must be greater than or equal to cost_min")
        if (self.cost_min is not None or self.cost_max is not None) and not self.currency:
            raise ValueError("currency is required when a cost is known")
        return self


class OpportunityRead(BaseModel):
    id: str
    opportunity_type: OpportunityType
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    timezone: str
    venue: str | None
    city: str | None
    region: str | None
    country_code: str | None
    source_url: str | None
    cost_min: Decimal | None
    cost_max: Decimal | None
    currency: str | None
    status: str
    tags: list[str]
    user_status: str
    score_factors: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    feasibility: dict[str, Any] = Field(default_factory=dict)


class OpportunitySourceUpdate(BaseModel):
    enabled: bool
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    categories: list[OpportunityType] = Field(default_factory=list, max_length=20)
    cadence_minutes: int = Field(default=360, ge=15, le=10_080)
    horizon_days: int = Field(default=30, ge=1, le=180)


class OpportunitySourceRead(BaseModel):
    id: str
    source_id: str
    enabled: bool
    configured: bool
    city: str | None
    region: str | None
    country_code: str | None
    categories: list[str]
    cadence_minutes: int
    horizon_days: int
    last_discovery_at: datetime | None
    next_discovery_at: datetime | None
    last_status: str
    last_summary: dict[str, Any]
    last_error: str | None


class DiscoverySummary(BaseModel):
    fetched: int = 0
    normalized: int = 0
    created: int = 0
    updated: int = 0
    deduplicated: int = 0
    filtered: int = 0
    ranked: int = 0
    surfaced: int = 0
    silent: int = 0
    failed_sources: list[str] = Field(default_factory=list)


class OpportunityOutcomeCreate(BaseModel):
    recommendation_id: str
    option_id: str
    outcome: Literal["VIEWED", "SELECTED", "REJECTED", "EXECUTED", "FEEDBACK"]
    feedback_text: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)


class SocialActionCandidate(BaseModel):
    action_type: SocialActionType
    subject: str
    reason_codes: list[str]
    contact_ref: str | None = None
    executable: Literal[False] = False

