from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LeisureTrajectoryUpdate(BaseModel):
    target_min: int = Field(default=2, ge=0, le=21)
    target_max: int = Field(default=3, ge=0, le=21)
    week_starts_on: int = Field(default=0, ge=0, le=6)
    status: Literal["ACTIVE", "PAUSED", "ARCHIVED"] = "ACTIVE"

    @model_validator(mode="after")
    def validate_range(self) -> "LeisureTrajectoryUpdate":
        if self.target_max < self.target_min:
            raise ValueError("target_max must be greater than or equal to target_min")
        return self


class LeisureTrajectoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    leisure_type: str
    period: str
    target_min: int
    target_max: int
    week_starts_on: int
    status: str
    period_start: datetime
    period_end: datetime
    completed_count: int
    state: Literal["BELOW_RANGE", "IN_RANGE", "ABOVE_RANGE", "PAUSED"]
    remaining_to_min: int


class MovieExternalIdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    external_id: str
    source_url: str | None = None


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    original_title: str | None = Field(default=None, max_length=255)
    release_year: int | None = Field(default=None, ge=1888, le=2200)
    release_date: date | None = None
    runtime_minutes: int | None = Field(default=None, ge=1, le=1000)
    genres: list[str] = Field(default_factory=list, max_length=20)
    overview: str | None = Field(default=None, max_length=10_000)
    poster_url: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=80)
    external_id: str | None = Field(default=None, max_length=180)
    source_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_external_identity(self) -> "MovieCreate":
        if bool(self.provider) != bool(self.external_id):
            raise ValueError("provider and external_id must be supplied together")
        return self


class MovieRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_title: str | None
    release_year: int | None
    release_date: date | None
    runtime_minutes: int | None
    genres: list[str]
    overview: str | None
    poster_url: str | None
    metadata_source: str | None
    external_ids: list[MovieExternalIdRead] = Field(default_factory=list)


class MetadataMovie(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    external_id: str
    title: str
    original_title: str | None = None
    release_date: date | None = None
    runtime_minutes: int | None = None
    genres: tuple[str, ...] = ()
    overview: str | None = None
    poster_url: str | None = None
    source_url: str | None = None
    provider_rating: float | None = None
    provider_vote_count: int | None = None


class WatchlistCreate(BaseModel):
    movie_id: str
    priority: int = Field(default=50, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="manual", max_length=80)
    source_ref: str | None = Field(default=None, max_length=180)


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    movie_id: str
    status: str
    priority: int
    source: str
    source_ref: str | None
    notes: str | None
    added_at: datetime
    movie: MovieRead


class ViewingCreate(BaseModel):
    movie_id: str
    watched_at: datetime
    rating: float | None = Field(default=None, ge=0, le=10)
    rating_scale: float | None = Field(default=10, gt=0, le=100)
    liked: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)
    source: str = Field(default="manual", max_length=80)
    source_ref: str | None = Field(default=None, max_length=180)
    recommendation_id: str | None = None
    recommendation_option_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=180)


class ViewingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    movie_id: str
    watched_at: datetime
    source: str
    source_ref: str | None
    rewatch: bool
    rating: float | None
    rating_scale: float | None
    liked: bool | None
    notes: str | None
    recommendation_id: str | None
    recommendation_option_id: str | None
    movie: MovieRead


class LetterboxdImportPreviewRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=8_000_000)
    source_kind: Literal["WATCHLIST", "DIARY", "WATCHED", "RATINGS"] | None = None


class MovieImportRowRead(BaseModel):
    id: str
    source_kind: str
    source_row_key: str
    status: str
    error: str | None
    normalized: dict[str, Any]
    movie_id: str | None


class MovieImportBatchRead(BaseModel):
    id: str
    provider: str
    file_name: str
    status: str
    summary: dict[str, Any]
    confirmed_at: datetime | None
    rows: list[MovieImportRowRead]


class MovieRecommendationRequest(BaseModel):
    available_minutes: int | None = Field(default=None, ge=20, le=1000)
    preferred_genres: list[str] = Field(default_factory=list, max_length=10)
    mood: Literal["LIGHT", "ENERGETIC", "TENSE", "REFLECTIVE", "ANY"] = "ANY"
    context: str | None = Field(default=None, max_length=240)
    include_rewatches: bool = False
    watchlist_only: bool = False
    limit: int = Field(default=5, ge=3, le=5)


class MovieRecommendationOutcomeCreate(BaseModel):
    option_id: str
    outcome: Literal["SELECTED", "WATCHED", "REJECTED"]
    feedback_text: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=180)


class ProspectiveMovieCreate(BaseModel):
    movie_id: str
    attention_policy: Literal["SHOW_PASSIVELY", "MENTION_WHEN_NATURAL"] = "MENTION_WHEN_NATURAL"


class Showtime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    external_id: str
    starts_at: datetime
    ends_at: datetime | None = None
    venue: str
    city: str
    booking_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ShowtimeSearchRequest(BaseModel):
    movie_id: str
    city: str = Field(min_length=1, max_length=120)
    window_start: datetime
    window_end: datetime
    manual_showtimes: list[Showtime] = Field(default_factory=list, max_length=50)


class ShowtimeOptionRead(BaseModel):
    showtime: Showtime
    feasible: bool
    reason_codes: list[str]
    conflicts: list[str]
    requires_plan_proposal: bool = False


class ProspectiveEvaluationRead(BaseModel):
    thread_id: str
    eligible: bool
    reason_code: str
    attention_action: str
    attention_item_id: str | None = None
    showtimes: list[ShowtimeOptionRead] = Field(default_factory=list)
