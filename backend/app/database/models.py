from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, event as sqlalchemy_event, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import PortableVector
from app.integrations.models import IntegrationConfiguration  # Register additive integration metadata with Base.
from app.standing_calendar.models import FixtureSnapshotCache  # Register backend-only public fixture snapshots with Base.


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid_str() -> str:
    return str(uuid4())


class TimestampedModel:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UserProfile(TimestampedModel, Base):
    __tablename__ = "user_profiles"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Life OS User", nullable=False)
    world_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserIntelligenceSettings(TimestampedModel, Base):
    __tablename__ = "user_intelligence_settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_user_intelligence_settings_user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(String(40), default="intelligence-settings-v1", nullable=False)
    proactivity_mode: Mapped[str] = mapped_column(String(20), default="BALANCED", nullable=False, index=True)
    memory_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    patterns_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    passive_suggestions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    questions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interruptions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    prospective_resurfacing_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opportunity_suggestions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monthly_ai_budget_eur: Mapped[float | None] = mapped_column(Float)
    disabled_skills_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("proactivity_mode IN ('QUIET', 'BALANCED', 'PROACTIVE')", name="ck_intelligence_settings_proactivity"),
        CheckConstraint("monthly_ai_budget_eur IS NULL OR monthly_ai_budget_eur >= 0", name="ck_intelligence_settings_budget"),
    )


class QuickCapture(TimestampedModel, Base):
    __tablename__ = "quick_captures"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_quick_captures_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(String(40), default="quick-capture-v1", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PROPOSED", nullable=False, index=True)
    source_conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_threads.id", name="fk_quick_captures_conversation_id", ondelete="SET NULL"),
        index=True,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id", name="fk_quick_captures_message_id", ondelete="SET NULL"),
        index=True,
    )
    source_workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("active_workspaces.id", name="fk_quick_captures_workspace_id", ondelete="SET NULL"),
        index=True,
    )
    interpreted_domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    target_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    structured_payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    ambiguity_flags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    consequence_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_outcome: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason_codes_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    interpreter_provider: Mapped[str] = mapped_column(String(80), default="deterministic", nullable=False)
    interpreter_model: Mapped[str | None] = mapped_column(String(160))
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    review_item_id: Mapped[str | None] = mapped_column(String(36), index=True)
    expected_world_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_entity_type: Mapped[str | None] = mapped_column(String(80))
    canonical_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trace_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_quick_captures_user_idempotency"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_quick_captures_confidence"),
        CheckConstraint("consequence_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_quick_captures_consequence"),
        CheckConstraint(
            "policy_outcome IN ('APPLY', 'REQUEST_CONFIRMATION', 'SEND_TO_REVIEW', 'REJECT_INVALID', 'NOOP_DUPLICATE')",
            name="ck_quick_captures_policy_outcome",
        ),
        Index("ix_quick_captures_user_status_created", "user_id", "status", "created_at"),
    )


class ReviewItem(TimestampedModel, Base):
    __tablename__ = "review_items"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_review_items_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_values_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    ambiguity_reasons_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    target_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    resolution_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(60))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    expected_world_revision: Mapped[int | None] = mapped_column(Integer)
    expected_target_version: Mapped[int | None] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_review_items_priority"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_review_items_confidence"),
        CheckConstraint("status IN ('PENDING', 'RESOLVED', 'DISMISSED', 'EXPIRED', 'SUPERSEDED')", name="ck_review_items_status"),
        Index("ix_review_items_user_status_priority", "user_id", "status", "priority", "created_at"),
        Index("ix_review_items_active_fingerprint", "user_id", "fingerprint", "status"),
    )


class Goal(TimestampedModel, Base):
    __tablename__ = "goals"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(80), default="personal", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    horizon: Mapped[str | None] = mapped_column(String(80))
    target_date: Mapped[date | None] = mapped_column(Date)
    success_condition: Mapped[str | None] = mapped_column(Text)
    progress_mode: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    manual_progress: Mapped[float | None] = mapped_column(Float)
    source_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class Trajectory(TimestampedModel, Base):
    __tablename__ = "trajectories"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_name: Mapped[str | None] = mapped_column(String(120))
    target_value: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    risk: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    on_track: Mapped[bool | None] = mapped_column(Boolean)
    target_date: Mapped[date | None] = mapped_column(Date)
    current_rate: Mapped[float | None] = mapped_column(Float)
    required_rate: Mapped[float | None] = mapped_column(Float)
    source_domain: Mapped[str | None] = mapped_column(String(80), index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Milestone(TimestampedModel, Base):
    __tablename__ = "milestones"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    target_date: Mapped[date | None] = mapped_column(Date)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeeklyFocus(TimestampedModel, Base):
    __tablename__ = "weekly_focuses"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    priority_boost: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "week_start", "goal_id", "title", name="uq_weekly_focus_identity"),)


class Commitment(TimestampedModel, Base):
    __tablename__ = "commitments"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(40), default="hard", nullable=False, index=True)
    commitment_type: Mapped[str] = mapped_column(String(40), default="hard", nullable=False, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Berlin", nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class NotebookEntry(TimestampedModel, Base):
    __tablename__ = "notebook_entries"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(60), default="GENERAL", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(60), default="manual", nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    conversation_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_threads.id", ondelete="SET NULL"), index=True
    )
    workspace_ref: Mapped[str | None] = mapped_column(String(80), index=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    embedding_vector: Mapped[list[float] | None] = mapped_column(PortableVector())
    embedding_provider: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedding_version: Mapped[str | None] = mapped_column(String(80))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_notebook_entries_user_idempotency"),
        CheckConstraint("entry_type IN ('GENERAL', 'IMPLEMENTATION_IDEA')", name="ck_notebook_entries_type"),
        CheckConstraint("status IN ('ACTIVE', 'REVIEWED', 'PROMOTED', 'ARCHIVED')", name="ck_notebook_entries_status"),
        Index("ix_notebook_entries_user_status_created", "user_id", "status", "created_at"),
    )


class NotebookPromotion(TimestampedModel, Base):
    __tablename__ = "notebook_promotions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    notebook_entry_id: Mapped[str] = mapped_column(
        ForeignKey("notebook_entries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    destination_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    destination_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_notebook_promotions_user_idempotency"),
        UniqueConstraint("notebook_entry_id", "destination_type", name="uq_notebook_promotions_entry_destination"),
        CheckConstraint(
            "destination_type IN ('MANUAL_DEVELOPMENT_REVIEW')",
            name="ck_notebook_promotions_destination",
        ),
    )


class LeisureTrajectory(TimestampedModel, Base):
    __tablename__ = "leisure_trajectories"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    leisure_type: Mapped[str] = mapped_column(String(40), default="MOVIE", nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(40), default="WEEK", nullable=False)
    target_min: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    target_max: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    week_starts_on: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "leisure_type", name="uq_leisure_trajectories_user_type"),
        CheckConstraint("target_min >= 0 AND target_max >= target_min", name="ck_leisure_trajectories_targets"),
        CheckConstraint("week_starts_on >= 0 AND week_starts_on <= 6", name="ck_leisure_trajectories_week_start"),
        CheckConstraint("period IN ('WEEK')", name="ck_leisure_trajectories_period"),
        CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'ARCHIVED')", name="ck_leisure_trajectories_status"),
    )


class Movie(TimestampedModel, Base):
    __tablename__ = "movies"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    release_year: Mapped[int | None] = mapped_column(Integer, index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    genres_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String(500))
    metadata_source: Mapped[str | None] = mapped_column(String(80), index=True)
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("runtime_minutes IS NULL OR runtime_minutes > 0", name="ck_movies_runtime_positive"),
        Index("ix_movies_title_year", "title", "release_year"),
    )


class MovieExternalId(TimestampedModel, Base):
    __tablename__ = "movie_external_ids"

    movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(180), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_movie_external_ids_provider_identity"),
        UniqueConstraint("movie_id", "provider", name="uq_movie_external_ids_movie_provider"),
    )


class MovieWatchlistItem(TimestampedModel, Base):
    __tablename__ = "movie_watchlist_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(180), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_watchlist_user_movie"),
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_movie_watchlist_priority"),
        CheckConstraint("status IN ('ACTIVE', 'REMOVED', 'WATCHED')", name="ck_movie_watchlist_status"),
        Index("ix_movie_watchlist_user_status_added", "user_id", "status", "added_at"),
    )


class MovieViewing(TimestampedModel, Base):
    __tablename__ = "movie_viewings"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id", ondelete="RESTRICT"), nullable=False, index=True)
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(180), index=True)
    rewatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    rating_scale: Mapped[float | None] = mapped_column(Float)
    liked: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), index=True)
    recommendation_option_id: Mapped[str | None] = mapped_column(ForeignKey("recommendation_options.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(180))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_movie_viewings_user_idempotency"),
        CheckConstraint("rating IS NULL OR rating >= 0", name="ck_movie_viewings_rating_nonnegative"),
        CheckConstraint("rating_scale IS NULL OR rating_scale > 0", name="ck_movie_viewings_scale_positive"),
        Index("ix_movie_viewings_user_watched", "user_id", "watched_at"),
    )


class MovieImportBatch(TimestampedModel, Base):
    __tablename__ = "movie_import_batches"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PREVIEW", nullable=False, index=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "content_hash", name="uq_movie_import_batches_content"),
        CheckConstraint("status IN ('PREVIEW', 'CONFIRMED', 'PARTIAL', 'FAILED')", name="ck_movie_import_batches_status"),
    )


class MovieImportRow(TimestampedModel, Base):
    __tablename__ = "movie_import_rows"

    batch_id: Mapped[str] = mapped_column(ForeignKey("movie_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_row_key: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text)
    movie_id: Mapped[str | None] = mapped_column(ForeignKey("movies.id", ondelete="SET NULL"), index=True)
    viewing_id: Mapped[str | None] = mapped_column(ForeignKey("movie_viewings.id", ondelete="SET NULL"), index=True)
    watchlist_item_id: Mapped[str | None] = mapped_column(ForeignKey("movie_watchlist_items.id", ondelete="SET NULL"), index=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "source_row_key", name="uq_movie_import_rows_batch_key"),
        CheckConstraint("status IN ('READY', 'REVIEW_REQUIRED', 'ERROR', 'IMPORTED', 'SKIPPED')", name="ck_movie_import_rows_status"),
    )


class SocialActivity(TimestampedModel, Base):
    __tablename__ = "social_activities"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    meaningful: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(180), index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), index=True)
    recommendation_option_id: Mapped[str | None] = mapped_column(ForeignKey("recommendation_options.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(180))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_social_activities_user_idempotency"),
    )


class Opportunity(TimestampedModel, Base):
    __tablename__ = "opportunities"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    opportunity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Berlin", nullable=False)
    venue: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    cost_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cost_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    pricing_source: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    entities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_opportunities_time_order"),
        CheckConstraint("cost_min IS NULL OR cost_min >= 0", name="ck_opportunities_cost_min"),
        CheckConstraint("cost_max IS NULL OR cost_max >= cost_min", name="ck_opportunities_cost_max"),
        CheckConstraint("status IN ('ACTIVE', 'ENDED', 'CANCELLED', 'STALE', 'ARCHIVED')", name="ck_opportunities_status"),
        Index("ix_opportunities_user_status_start", "user_id", "status", "starts_at"),
        Index("ix_opportunities_dedupe", "user_id", "canonical_title", "starts_at", "venue"),
    )


class OpportunityExternalId(TimestampedModel, Base):
    __tablename__ = "opportunity_external_ids"

    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(180), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_id", name="uq_opportunity_external_identity"),
    )


class OpportunitySourceState(TimestampedModel, Base):
    __tablename__ = "opportunity_source_states"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str | None] = mapped_column(String(2))
    categories_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_status: Mapped[str] = mapped_column(String(40), default="NEVER", nullable=False, index=True)
    last_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "source_id", name="uq_opportunity_source_user_source"),
        CheckConstraint("cadence_minutes >= 15", name="ck_opportunity_source_cadence"),
        CheckConstraint("horizon_days >= 1 AND horizon_days <= 180", name="ck_opportunity_source_horizon"),
    )


class OpportunityUserState(TimestampedModel, Base):
    __tablename__ = "opportunity_user_states"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="AVAILABLE", nullable=False, index=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_opportunity_user_state"),
        CheckConstraint("status IN ('AVAILABLE', 'INTERESTED', 'DISMISSED', 'ATTENDED')", name="ck_opportunity_user_state_status"),
    )


class StandingCalendarRule(TimestampedModel, Base):
    __tablename__ = "standing_calendar_rules"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    protected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_create: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_identity: Mapped[str] = mapped_column(String(180), nullable=False)
    source_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reconciliation_policy_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sync_interval_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_sync_status: Mapped[str] = mapped_column(String(40), default="NEVER", nullable=False, index=True)
    last_sync_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "rule_type", "source_provider", "source_identity", name="uq_standing_rules_identity"),
        CheckConstraint("rule_type IN ('SPORTS_FIXTURE')", name="ck_standing_rules_type"),
        CheckConstraint("sync_interval_days IN (1, 14)", name="ck_standing_rules_sync_interval"),
        Index("ix_standing_rules_due", "enabled", "next_sync_at"),
    )

    @property
    def next_fixture_selection_known(self) -> bool:
        metadata = self.metadata_json or {}
        return metadata.get("fixture_sync_mode") == "NEXT_FIXTURE" and "current_next_fixture_id" in metadata

    @property
    def current_next_fixture_id(self) -> str | None:
        value = (self.metadata_json or {}).get("current_next_fixture_id")
        return value if isinstance(value, str) else None


class FixtureBinding(TimestampedModel, Base):
    __tablename__ = "fixture_bindings"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    standing_rule_id: Mapped[str] = mapped_column(
        ForeignKey("standing_calendar_rules.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    commitment_id: Mapped[str | None] = mapped_column(
        ForeignKey("commitments.id", ondelete="SET NULL"), unique=True, index=True
    )
    source_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_fixture_id: Mapped[str] = mapped_column(String(180), nullable=False)
    fixture_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    raw_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    protection_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "source_provider", "source_fixture_id", name="uq_fixture_bindings_source_identity"),
        CheckConstraint(
            "fixture_status IN ('SCHEDULED', 'CONFIRMED', 'POSTPONED', 'CANCELLED', 'COMPLETED')",
            name="ck_fixture_bindings_status",
        ),
    )


class Action(TimestampedModel, Base):
    __tablename__ = "actions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(40), default="maintenance", nullable=False, index=True)
    earliest_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    context: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_min_minutes: Mapped[int | None] = mapped_column(Integer)
    duration_max_minutes: Mapped[int | None] = mapped_column(Integer)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidate_group_id: Mapped[str | None] = mapped_column(String(120), index=True)
    variant_type: Mapped[str] = mapped_column(String(40), default="standard", nullable=False, index=True)
    variant_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mutually_exclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    variant_quality: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    requirement_key: Mapped[str | None] = mapped_column(String(255), index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), index=True)
    trajectory_id: Mapped[str | None] = mapped_column(ForeignKey("trajectories.id"), index=True)
    generated_reason: Mapped[str | None] = mapped_column(Text)
    generation_version: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    planning_priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)


class Constraint(TimestampedModel, Base):
    __tablename__ = "constraints"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strength: Mapped[str] = mapped_column(String(20), default="hard", nullable=False, index=True)
    provenance: Mapped[str] = mapped_column(String(40), default="canonical", nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(80), index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    penalty: Mapped[float] = mapped_column(Float, default=12.0, nullable=False)


class Plan(TimestampedModel, Base):
    __tablename__ = "plans"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    planner_version: Mapped[str] = mapped_column(String(40), default="v0", nullable=False)
    generated_from_world_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    planning_day: Mapped[date | None] = mapped_column(Date)
    horizon_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horizon_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    previous_plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"))
    replan_reason: Mapped[str | None] = mapped_column(String(120))
    control_loop_version: Mapped[str] = mapped_column(String(40), default="v0.4-control-loop", nullable=False)
    plan_diff: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_replanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decision_factors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    personal_model_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    personal_model_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overload_status: Mapped[str] = mapped_column(String(40), default="feasible", nullable=False, index=True)
    shortfall_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    blocks: Mapped[list["PlanBlock"]] = relationship("PlanBlock", cascade="all, delete-orphan", back_populates="plan")


class PlanBlock(TimestampedModel, Base):
    __tablename__ = "plan_blocks"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False, index=True)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    commitment_id: Mapped[str | None] = mapped_column(ForeignKey("commitments.id"))
    source_type: Mapped[str] = mapped_column(String(80), default="planner", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), index=True)
    domain: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    block_type: Mapped[str] = mapped_column(String(80), default="generated_action", nullable=False, index=True)
    commitment_level: Mapped[str | None] = mapped_column(String(40))
    movable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="planner", nullable=False)
    decision_factors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    outcome_reason: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    action_group_id: Mapped[str | None] = mapped_column(String(120), index=True)
    variant_type: Mapped[str | None] = mapped_column(String(40), index=True)
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    user_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    residual_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    plan: Mapped[Plan] = relationship("Plan", back_populates="blocks")


class PlanProposal(TimestampedModel, Base):
    __tablename__ = "plan_proposals"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("learning_exams.id"), nullable=False, index=True)
    source_trace_id: Mapped[str | None] = mapped_column(ForeignKey("cognitive_traces.id"), index=True)
    parent_proposal_id: Mapped[str | None] = mapped_column(ForeignKey("plan_proposals.id"), index=True)
    current_plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False, index=True)
    current_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_world_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    deviation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deduplication_key: Mapped[str] = mapped_column(String(180), nullable=False)
    trajectory_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    deviation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidate_plan_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    changes_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_effects_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tradeoffs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    modification_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    authority_level: Mapped[int] = mapped_column(Integer, nullable=False)
    attention_action: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(80), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("authority_level >= 0 AND authority_level <= 4", name="ck_plan_proposals_authority_level"),
        CheckConstraint("current_plan_version >= 1", name="ck_plan_proposals_current_plan_version"),
        CheckConstraint("current_world_revision >= 0", name="ck_plan_proposals_world_revision"),
        CheckConstraint(
            "status IN ('DRAFT', 'PRESENTED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'EXPIRED', 'APPLY_FAILED')",
            name="ck_plan_proposals_status",
        ),
        UniqueConstraint("user_id", "deduplication_key", name="uq_plan_proposals_user_deduplication"),
        Index("ix_plan_proposals_user_status_created", "user_id", "status", "created_at"),
        Index("ix_plan_proposals_exam_status", "exam_id", "status"),
    )


class PlanningAllocation(TimestampedModel, Base):
    __tablename__ = "planning_allocations"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    planning_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    action_group_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    required_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allocated_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    debt_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), default="allocated", nullable=False, index=True)
    risk_status: Mapped[str] = mapped_column(String(40), default="feasible", nullable=False, index=True)
    reason_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "planning_date", "action_group_id", name="uq_planning_allocation_user_day_group"),)


class PlanningDebt(TimestampedModel, Base):
    __tablename__ = "planning_debts"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    action_group_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    source_plan_block_id: Mapped[str | None] = mapped_column(ForeignKey("plan_blocks.id"), index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    residual_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "source_plan_block_id", name="uq_planning_debt_user_block"),)


class StateObservation(TimestampedModel, Base):
    __tablename__ = "state_observations"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    observation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Event(TimestampedModel, Base):
    __tablename__ = "events"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    world_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OutboxStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    retry = "retry"
    published = "published"
    failed = "failed"
    dead_letter = "dead_letter"


class OutboxEvent(TimestampedModel, Base):
    __tablename__ = "outbox_events"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=OutboxStatus.pending.value, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorldRevision(TimestampedModel, Base):
    __tablename__ = "world_revisions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "revision", name="uq_world_revision_user_revision"),)


class NotificationIntent(TimestampedModel, Base):
    __tablename__ = "notification_intents"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[str] = mapped_column(String(40), default="normal", nullable=False)
    title: Mapped[str | None] = mapped_column(String(180))
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppressed_reason: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notification_intent_user_dedupe"),)


class PushSubscription(TimestampedModel, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
    auth_key: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    device_label: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),)


class PushDelivery(TimestampedModel, Base):
    __tablename__ = "push_deliveries"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    notification_intent_id: Mapped[str] = mapped_column(ForeignKey("notification_intents.id"), nullable=False, index=True)
    push_subscription_id: Mapped[str] = mapped_column(ForeignKey("push_subscriptions.id"), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("push_subscription_id", "dedupe_key", name="uq_push_delivery_subscription_dedupe"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    mutation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "mutation_key", name="uq_idempotency_user_key"),)


class AssistantActionProposal(TimestampedModel, Base):
    __tablename__ = "assistant_action_proposals"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    assistant_role: Mapped[str] = mapped_column(String(80), default="GENERAL_ASSISTANT", nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    arguments_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    consequence_category: Mapped[str] = mapped_column(String(80), default="consequential", nullable=False)
    expected_world_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)


class AIActionAudit(TimestampedModel, Base):
    __tablename__ = "ai_action_audits"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    assistant_role: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="fake", nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    model_tier: Mapped[str] = mapped_column(String(40), default="NO_AI", nullable=False)
    capability: Mapped[str | None] = mapped_column(String(40), index=True)
    skill_name: Mapped[str | None] = mapped_column(String(120), index=True)
    skill_version: Mapped[str | None] = mapped_column(String(40))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    conversation_thread_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_threads.id"), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    cost_estimated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(120), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("assistant_action_proposals.id"))
    mutation_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_category: Mapped[str | None] = mapped_column(String(120), index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ConversationThread(TimestampedModel, Base):
    __tablename__ = "conversation_threads"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), default="New conversation", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    default_skill: Mapped[str] = mapped_column(String(120), default="self-core", nullable=False, index=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class ConversationMessage(TimestampedModel, Base):
    __tablename__ = "conversation_messages"

    thread_id: Mapped[str] = mapped_column(ForeignKey("conversation_threads.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    skill_name: Mapped[str | None] = mapped_column(String(120), index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("thread_id", "sequence_number", name="uq_conversation_message_thread_sequence"),)


class ConversationSummary(TimestampedModel, Base):
    __tablename__ = "conversation_summaries"

    thread_id: Mapped[str] = mapped_column(ForeignKey("conversation_threads.id"), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    covers_until_message_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_messages.id"), index=True)
    covered_message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CognitiveTrace(TimestampedModel, Base):
    __tablename__ = "cognitive_traces"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    cognitive_event_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    conversation_thread_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_threads.id"), index=True)
    workspace_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    world_revision: Mapped[int | None] = mapped_column(Integer, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(160), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(160), index=True)
    question_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    output_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_version: Mapped[str | None] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(160), index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skill_name: Mapped[str | None] = mapped_column(String(120), index=True)
    skill_version: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_eur: Mapped[float | None] = mapped_column(Float)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    context_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    memory_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    pattern_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    probabilities_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    planner_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    proposal_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    tool_call_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    state_change_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


@sqlalchemy_event.listens_for(CognitiveTrace, "before_update", propagate=True)
def _prevent_cognitive_trace_update(mapper, connection, target) -> None:  # noqa: ANN001
    del mapper, connection, target
    raise ValueError("CognitiveTrace rows are immutable; append a DecisionAudit instead.")


class DecisionAudit(TimestampedModel, Base):
    __tablename__ = "decision_audits"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(ForeignKey("cognitive_traces.id"), nullable=False, index=True)
    audit_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    downstream_action_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    outcome_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    correction_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    override_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feedback_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    training_eligible: Mapped[bool | None] = mapped_column(Boolean, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DecisionProviderUsage(TimestampedModel, Base):
    __tablename__ = "decision_provider_usage"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_decision_provider_usage_user_id"), nullable=False, index=True
    )
    cognitive_trace_id: Mapped[str | None] = mapped_column(
        ForeignKey("cognitive_traces.id", name="fk_decision_provider_usage_trace_id", ondelete="SET NULL"), index=True
    )
    cognitive_event_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_version: Mapped[str | None] = mapped_column(String(160), index=True)
    provider_role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    routing_policy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    routing_reason: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_eur: Mapped[float | None] = mapped_column(Float)
    request_id: Mapped[str | None] = mapped_column(String(160), index=True)
    error_code: Mapped[str | None] = mapped_column(String(120), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("question_version >= 1", name="ck_decision_provider_usage_question_version"),
        CheckConstraint("question_count >= 1", name="ck_decision_provider_usage_question_count"),
        CheckConstraint("latency_ms >= 0", name="ck_decision_provider_usage_latency"),
        CheckConstraint("input_units >= 0 AND output_units >= 0", name="ck_decision_provider_usage_units"),
        CheckConstraint(
            "estimated_cost_eur IS NULL OR estimated_cost_eur >= 0",
            name="ck_decision_provider_usage_cost",
        ),
        Index(
            "ix_decision_provider_usage_provider_family_created",
            "provider", "question_family", "created_at",
        ),
    )


class DecisionDisagreement(TimestampedModel, Base):
    __tablename__ = "decision_disagreements"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_decision_disagreements_user_id"), nullable=False, index=True
    )
    cognitive_trace_id: Mapped[str | None] = mapped_column(
        ForeignKey("cognitive_traces.id", name="fk_decision_disagreements_trace_id", ondelete="SET NULL"), index=True
    )
    cognitive_event_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_audit_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_audits.id", name="fk_decision_disagreements_decision_audit_id", ondelete="SET NULL"),
        index=True,
    )
    comparison_role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    disagreement_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    primary_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    primary_model_version: Mapped[str | None] = mapped_column(String(160), index=True)
    primary_answer_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    primary_probabilities_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    primary_confidence: Mapped[float | None] = mapped_column(Float)
    comparison_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    comparison_model_version: Mapped[str | None] = mapped_column(String(160), index=True)
    comparison_answer_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    comparison_probabilities_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    comparison_confidence: Mapped[float | None] = mapped_column(Float)
    operational_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operational_answer_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    routing_policy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    training_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(40), default="UNREVIEWED", nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("question_version >= 1", name="ck_decision_disagreements_question_version"),
        CheckConstraint(
            "primary_confidence IS NULL OR (primary_confidence >= 0 AND primary_confidence <= 1)",
            name="ck_decision_disagreements_primary_confidence",
        ),
        CheckConstraint(
            "comparison_confidence IS NULL OR (comparison_confidence >= 0 AND comparison_confidence <= 1)",
            name="ck_decision_disagreements_comparison_confidence",
        ),
        Index(
            "ix_decision_disagreements_family_type_created",
            "question_family", "disagreement_type", "created_at",
        ),
    )


class ActiveWorkspace(TimestampedModel, Base):
    __tablename__ = "active_workspaces"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_active_workspaces_user_id"), nullable=False, index=True
    )
    workspace_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_foreground: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    payload_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    conversation_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "conversation_threads.id",
            name="fk_active_workspaces_conversation_thread_id",
            ondelete="SET NULL",
        ),
        index=True,
    )
    primary_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    primary_entity_id: Mapped[str | None] = mapped_column(String(160), index=True)
    current_phase: Mapped[str | None] = mapped_column(String(80))
    current_step: Mapped[str | None] = mapped_column(String(160))
    canonical_change_refs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_meaningful_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    state_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_active_workspaces_user_idempotency"),
        CheckConstraint("payload_version >= 1", name="ck_active_workspaces_payload_version"),
        CheckConstraint("state_revision >= 1", name="ck_active_workspaces_state_revision"),
        Index(
            "uq_active_workspaces_user_foreground",
            "user_id",
            unique=True,
            postgresql_where=text("is_foreground = true"),
            sqlite_where=text("is_foreground = 1"),
        ),
        Index("ix_active_workspaces_user_status_type", "user_id", "status", "workspace_type"),
    )


class OpenThread(TimestampedModel, Base):
    __tablename__ = "open_threads"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_open_threads_user_id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    entities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(80), index=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_open_threads_confidence"),
        Index("ix_open_threads_user_status_updated", "user_id", "status", "updated_at"),
    )


class ProspectiveThread(TimestampedModel, Base):
    __tablename__ = "prospective_threads"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_prospective_threads_user_id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    entities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(80), index=True)
    trigger_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    trigger_conditions_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    earliest_relevance: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    latest_relevance: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    check_policy: Mapped[str] = mapped_column(String(80), nullable=False)
    attention_policy: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_prospective_threads_confidence"),
        CheckConstraint(
            "earliest_relevance IS NULL OR latest_relevance IS NULL OR earliest_relevance <= latest_relevance",
            name="ck_prospective_threads_relevance_window",
        ),
        Index("ix_prospective_threads_user_status_trigger", "user_id", "status", "trigger_type"),
        Index(
            "ix_prospective_threads_user_relevance",
            "user_id",
            "earliest_relevance",
            "latest_relevance",
        ),
    )


class AttentionItem(TimestampedModel, Base):
    __tablename__ = "attention_items"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_attention_items_user_id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False, index=True)
    source_cognitive_event_id: Mapped[str | None] = mapped_column(String(160), index=True)
    source_trace_id: Mapped[str | None] = mapped_column(
        ForeignKey("cognitive_traces.id", name="fk_attention_items_source_trace_id", ondelete="SET NULL"),
        index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("active_workspaces.id", name="fk_attention_items_workspace_id", ondelete="SET NULL"),
        index=True,
    )
    open_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("open_threads.id", name="fk_attention_items_open_thread_id", ondelete="SET NULL"),
        index=True,
    )
    prospective_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("prospective_threads.id", name="fk_attention_items_prospective_thread_id", ondelete="SET NULL"),
        index=True,
    )
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deduplication_key: Mapped[str | None] = mapped_column(String(180))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "deduplication_key", name="uq_attention_items_user_deduplication"),
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_attention_items_priority"),
        CheckConstraint("expires_at IS NULL OR not_before IS NULL OR not_before <= expires_at", name="ck_attention_items_window"),
        Index("ix_attention_items_user_status_not_before", "user_id", "status", "not_before"),
    )


class FeedbackSession(TimestampedModel, Base):
    __tablename__ = "feedback_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_feedback_sessions_user_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    parent_conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_threads.id", name="fk_feedback_sessions_parent_conversation_id", ondelete="SET NULL"),
        index=True,
    )
    parent_workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("active_workspaces.id", name="fk_feedback_sessions_parent_workspace_id", ondelete="SET NULL"),
        index=True,
    )
    parent_workspace_type: Mapped[str | None] = mapped_column(String(40), index=True)
    target_cognitive_trace_id: Mapped[str] = mapped_column(
        ForeignKey("cognitive_traces.id", name="fk_feedback_sessions_target_cognitive_trace_id"),
        nullable=False,
        index=True,
    )
    target_decision_audit_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_audits.id", name="fk_feedback_sessions_target_decision_audit_id", ondelete="SET NULL"),
        index=True,
    )
    target_assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id", name="fk_feedback_sessions_target_assistant_message_id", ondelete="SET NULL"),
        index=True,
    )
    frozen_world_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    frozen_context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    initial_user_explanation: Mapped[str | None] = mapped_column(Text)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_planned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_answered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clarification_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    clarification_question_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    clarification_answer: Mapped[str | None] = mapped_column(Text)
    planned_questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    feedback_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    resume_state_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("current_question_index >= 0", name="ck_feedback_sessions_question_index"),
        CheckConstraint(
            "questions_planned_count >= 0 AND questions_planned_count <= 4",
            name="ck_feedback_sessions_question_count",
        ),
        CheckConstraint(
            "questions_answered_count >= 0 AND questions_answered_count <= questions_planned_count",
            name="ck_feedback_sessions_answer_count",
        ),
        Index(
            "uq_feedback_sessions_user_conversation_active",
            "user_id",
            "parent_conversation_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_feedback_sessions_user_status_created", "user_id", "status", "created_at"),
    )


class FeedbackResponse(TimestampedModel, Base):
    __tablename__ = "feedback_responses"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_feedback_responses_user_id"), nullable=False, index=True
    )
    feedback_session_id: Mapped[str] = mapped_column(
        ForeignKey("feedback_sessions.id", name="fk_feedback_responses_feedback_session_id"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    score: Mapped[int | None] = mapped_column(Integer, index=True)
    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    feedback_scope: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    feedback_confidence: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    explanation: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("question_version >= 1", name="ck_feedback_responses_question_version"),
        CheckConstraint(
            "(is_skipped = true AND score IS NULL) OR (is_skipped = false AND score BETWEEN 0 AND 5)",
            name="ck_feedback_responses_score_skip",
        ),
        UniqueConstraint(
            "feedback_session_id", "question_id", "question_version",
            name="uq_feedback_responses_session_question",
        ),
        Index("ix_feedback_responses_dimension_score", "dimension", "score"),
    )


class DecisionTrainingExample(TimestampedModel, Base):
    __tablename__ = "decision_training_examples"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", name="fk_decision_training_examples_user_id"), nullable=False, index=True
    )
    cognitive_trace_id: Mapped[str] = mapped_column(
        ForeignKey("cognitive_traces.id", name="fk_decision_training_examples_cognitive_trace_id"),
        nullable=False,
        index=True,
    )
    decision_audit_id: Mapped[str] = mapped_column(
        ForeignKey("decision_audits.id", name="fk_decision_training_examples_decision_audit_id"),
        nullable=False,
        index=True,
    )
    decision_disagreement_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "decision_disagreements.id",
            name="fk_decision_training_examples_decision_disagreement_id",
            ondelete="SET NULL",
        ),
        index=True,
    )
    feedback_session_id: Mapped[str] = mapped_column(
        ForeignKey("feedback_sessions.id", name="fk_decision_training_examples_feedback_session_id"),
        nullable=False,
        index=True,
    )
    feedback_response_id: Mapped[str] = mapped_column(
        ForeignKey("feedback_responses.id", name="fk_decision_training_examples_feedback_response_id"),
        nullable=False,
        index=True,
    )
    decision_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    question_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cognitive_event_ref: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    conversation_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_threads.id", name="fk_decision_training_examples_conversation_thread_id", ondelete="SET NULL"),
        index=True,
    )
    active_workspace_type: Mapped[str | None] = mapped_column(String(40), index=True)
    workspace_phase: Mapped[str | None] = mapped_column(String(80), index=True)
    candidate_action: Mapped[str | None] = mapped_column(String(120), index=True)
    urgency: Mapped[float | None] = mapped_column(Float)
    reversible: Mapped[bool | None] = mapped_column(Boolean)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_answer_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_confidence: Mapped[float | None] = mapped_column(Float)
    probabilities_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    executive_result: Mapped[str | None] = mapped_column(String(80), index=True)
    feedback_dimension: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    feedback_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    feedback_scope: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    feedback_confidence: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    explicit_feedback_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    label_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    label_strength: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    label_source: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_version: Mapped[str | None] = mapped_column(String(160), index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("feedback_response_id", name="uq_decision_training_examples_feedback_response_id"),
        CheckConstraint("question_version >= 1", name="ck_decision_training_examples_question_version"),
        CheckConstraint("feedback_score BETWEEN 0 AND 5", name="ck_decision_training_examples_feedback_score"),
        CheckConstraint(
            "model_confidence IS NULL OR (model_confidence >= 0 AND model_confidence <= 1)",
            name="ck_decision_training_examples_model_confidence",
        ),
        CheckConstraint("urgency IS NULL OR (urgency >= 0 AND urgency <= 1)", name="ck_decision_training_examples_urgency"),
        Index(
            "ix_decision_training_examples_family_provider_policy",
            "decision_family", "provider", "model_version", "policy_version",
        ),
    )


class MemoryItem(TimestampedModel, Base):
    __tablename__ = "memory_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(60), default="general", nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    polarity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="candidate", nullable=False, index=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    supersedes_memory_id: Mapped[str | None] = mapped_column(ForeignKey("memory_items.id"), index=True)
    embedding_vector: Mapped[list[float] | None] = mapped_column(PortableVector())
    embedding_provider: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedding_version: Mapped[str | None] = mapped_column(String(80))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MemoryEvidence(TimestampedModel, Base):
    __tablename__ = "memory_evidence"

    memory_id: Mapped[str] = mapped_column(ForeignKey("memory_items.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    evidence_kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), default="supports", nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    excerpt: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("memory_id", "source_type", "source_id", "evidence_kind", "direction", name="uq_memory_evidence_source"),
    )


class Episode(TimestampedModel, Base):
    __tablename__ = "memory_episodes"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    source_event_start_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    source_event_end_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    source_summary_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_summaries.id"), index=True)
    related_entities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(PortableVector())
    embedding_provider: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedding_version: Mapped[str | None] = mapped_column(String(80))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "normalized_key", name="uq_memory_episode_user_key"),)


class MemorySuppression(TimestampedModel, Base):
    __tablename__ = "memory_suppressions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    suppression_key: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(60), index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    reason: Mapped[str] = mapped_column(String(80), default="user_forgot", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    suppressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (UniqueConstraint("user_id", "suppression_key", name="uq_memory_suppression_user_key"),)


class MemoryProcessingJob(TimestampedModel, Base):
    __tablename__ = "memory_processing_jobs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "job_type", "source_type", "source_id", name="uq_memory_job_source"),
    )


class MemoryRetrievalAudit(TimestampedModel, Base):
    __tablename__ = "memory_retrieval_audits"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    retrieval_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domains_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    returned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class Recommendation(TimestampedModel, Base):
    __tablename__ = "recommendations"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created", nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_recommendation_user_idempotency"),)


class RecommendationOption(TimestampedModel, Base):
    __tablename__ = "recommendation_options"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(220), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(80))
    reference_id: Mapped[str | None] = mapped_column(String(36), index=True)

    __table_args__ = (UniqueConstraint("recommendation_id", "rank", name="uq_recommendation_option_rank"),)


class RecommendationOutcome(TimestampedModel, Base):
    __tablename__ = "recommendation_outcomes"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), index=True)
    option_id: Mapped[str | None] = mapped_column(ForeignKey("recommendation_options.id"), index=True)
    domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80))
    source_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    recommendation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, index=True)
    feedback_text: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_recommendation_outcome_user_idempotency"),)


class MemoryConsolidationRun(TimestampedModel, Base):
    __tablename__ = "memory_consolidation_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False, index=True)
    source_event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    episode_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "period_start", "period_end", name="uq_memory_consolidation_period"),)


class MemoryLearningBridgeRun(TimestampedModel, Base):
    __tablename__ = "memory_learning_bridge_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", nullable=False, index=True)
    memory_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pattern_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommendation_outcome_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "period_start", "period_end", name="uq_memory_learning_bridge_period"),)


class BodyMeasurement(TimestampedModel, Base):
    __tablename__ = "fitness_body_measurements"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    body_weight_kg: Mapped[float | None] = mapped_column(Float)
    body_fat_percentage: Mapped[float | None] = mapped_column(Float)
    lean_mass_kg: Mapped[float | None] = mapped_column(Float)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)
    body_water_percentage: Mapped[float | None] = mapped_column(Float)
    visceral_fat_rating: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class WorkoutProgram(TimestampedModel, Base):
    __tablename__ = "fitness_workout_programs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    weekly_frequency: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    minimum_recovery_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), default="gym")


class WorkoutTemplate(TimestampedModel, Base):
    __tablename__ = "fitness_workout_templates"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("fitness_workout_programs.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Workout(TimestampedModel, Base):
    __tablename__ = "fitness_workouts"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class Exercise(TimestampedModel, Base):
    __tablename__ = "fitness_exercises"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    primary_muscle_group: Mapped[str | None] = mapped_column(String(80))
    equipment: Mapped[str | None] = mapped_column(String(80))
    default_rest_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class WorkoutTemplateExercise(TimestampedModel, Base):
    __tablename__ = "fitness_workout_template_exercises"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("fitness_workout_templates.id"), nullable=False, index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("fitness_exercises.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_sets: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    target_rep_min: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    target_rep_max: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    target_load_kg: Mapped[float | None] = mapped_column(Float)
    target_rpe: Mapped[float | None] = mapped_column(Float)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    progression_rule: Mapped[str] = mapped_column(String(80), default="double_progression", nullable=False)
    load_increment_kg: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class WorkoutSession(TimestampedModel, Base):
    __tablename__ = "fitness_workout_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    workout_template_id: Mapped[str | None] = mapped_column(ForeignKey("fitness_workout_templates.id"), index=True)
    source_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    source_plan_block_id: Mapped[str | None] = mapped_column(ForeignKey("plan_blocks.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="in_progress", nullable=False, index=True)
    perceived_session_difficulty: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    runtime_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    planned_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkoutExercise(TimestampedModel, Base):
    __tablename__ = "fitness_workout_exercises"

    workout_id: Mapped[str] = mapped_column(ForeignKey("fitness_workouts.id"), nullable=False, index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("fitness_exercises.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExerciseSet(TimestampedModel, Base):
    __tablename__ = "fitness_exercise_sets"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    workout_exercise_id: Mapped[str | None] = mapped_column(ForeignKey("fitness_workout_exercises.id"), index=True)
    workout_session_id: Mapped[str | None] = mapped_column(ForeignKey("fitness_workout_sessions.id"), index=True)
    exercise_id: Mapped[str | None] = mapped_column(ForeignKey("fitness_exercises.id"), index=True)
    template_exercise_id: Mapped[str | None] = mapped_column(ForeignKey("fitness_workout_template_exercises.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    load_kg: Mapped[float | None] = mapped_column(Float)
    perceived_exertion: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[float | None] = mapped_column(Float)
    set_type: Mapped[str] = mapped_column(String(40), default="working", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_fitness_set_user_idempotency"),)


class ProgressionState(TimestampedModel, Base):
    __tablename__ = "fitness_progression_states"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    template_exercise_id: Mapped[str] = mapped_column(ForeignKey("fitness_workout_template_exercises.id"), nullable=False, index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("fitness_exercises.id"), nullable=False, index=True)
    rule: Mapped[str] = mapped_column(String(80), default="double_progression", nullable=False)
    previous_load_kg: Mapped[float | None] = mapped_column(Float)
    recommended_load_kg: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(40), default="maintain", nullable=False)
    explanation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RecoveryObservation(TimestampedModel, Base):
    __tablename__ = "fitness_recovery_observations"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    soreness: Mapped[int | None] = mapped_column(Integer)
    sleep_quality: Mapped[int | None] = mapped_column(Integer)
    stress: Mapped[int | None] = mapped_column(Integer)
    readiness: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class FitnessGoal(TimestampedModel, Base):
    __tablename__ = "fitness_goals"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    target_body_fat_percentage: Mapped[float | None] = mapped_column(Float)
    target_lean_mass_kg: Mapped[float | None] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(80), default="body_recomposition", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Course(TimestampedModel, Base):
    __tablename__ = "learning_courses"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    institution: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)


class Exam(TimestampedModel, Base):
    __tablename__ = "learning_exams"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("learning_courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date)
    exam_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    estimated_required_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    completed_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    target_preparation_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    minimum_required_preparation_minutes: Mapped[int | None] = mapped_column(Integer)
    target_quality_adjusted_minutes: Mapped[int | None] = mapped_column(Integer)
    strategy_version: Mapped[str] = mapped_column(String(80), default="learning-trajectory-v1", nullable=False)
    importance: Mapped[str] = mapped_column(String(40), default="normal", nullable=False)
    attempts_remaining: Mapped[int | None] = mapped_column(Integer)
    final_attempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exam_format: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False)


class StudyRequirement(TimestampedModel, Base):
    __tablename__ = "learning_study_requirements"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("learning_exams.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    estimated_required_minutes: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    prerequisite_topic_id: Mapped[str | None] = mapped_column(ForeignKey("learning_study_requirements.id"))
    completed_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)


class StudySession(TimestampedModel, Base):
    __tablename__ = "learning_study_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("learning_courses.id"), index=True)
    exam_id: Mapped[str | None] = mapped_column(ForeignKey("learning_exams.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("learning_study_requirements.id"), index=True)
    source_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    source_plan_block_id: Mapped[str | None] = mapped_column(ForeignKey("plan_blocks.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_rating: Mapped[int | None] = mapped_column(Integer)
    focus_quality: Mapped[int | None] = mapped_column(Integer)
    comprehension_quality: Mapped[int | None] = mapped_column(Integer)
    quality_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    quality_adjusted_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    planned_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    completion_status: Mapped[str] = mapped_column(String(40), default="completed", nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(120))
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_learning_session_user_idempotency"),)


class HouseholdTask(TimestampedModel, Base):
    __tablename__ = "household_tasks"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="chore", nullable=False, index=True)
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    minimum_duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    location: Mapped[str] = mapped_column(String(120), default="home", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "title", name="uq_household_task_user_title"),)


class Ingredient(TimestampedModel, Base):
    __tablename__ = "kitchen_ingredients"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(180), index=True)
    default_unit: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(80), index=True)

    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_kitchen_ingredient_normalized"),)


class IngredientAlias(TimestampedModel, Base):
    __tablename__ = "kitchen_ingredient_aliases"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("kitchen_ingredients.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    merchant: Mapped[str | None] = mapped_column(String(180), index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "normalized_alias", "merchant", name="uq_kitchen_ingredient_alias"),)


class InventoryItem(TimestampedModel, Base):
    __tablename__ = "kitchen_inventory_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_ingredients.id"), index=True)
    ingredient_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="item", nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    canonical_unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    default_storage_location: Mapped[str | None] = mapped_column(String(80))
    is_staple: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    restock_threshold: Mapped[float | None] = mapped_column(Float)
    restock_target: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class InventoryLot(TimestampedModel, Base):
    __tablename__ = "kitchen_inventory_lots"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(ForeignKey("kitchen_inventory_items.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    storage_location: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    source_reference_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_reference_id: Mapped[str | None] = mapped_column(String(36), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Recipe(TimestampedModel, Base):
    __tablename__ = "kitchen_recipes"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    preparation_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    cooking_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    servings: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    calories_per_serving: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    protein_g_per_serving: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    carbs_g_per_serving: Mapped[float | None] = mapped_column(Float)
    fat_g_per_serving: Mapped[float | None] = mapped_column(Float)
    protein_family: Mapped[str | None] = mapped_column(String(80), index=True)
    difficulty: Mapped[str] = mapped_column(String(40), default="easy", nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    steps_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class RecipeIngredient(TimestampedModel, Base):
    __tablename__ = "kitchen_recipe_ingredients"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("kitchen_recipes.id"), nullable=False, index=True)
    ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_ingredients.id"), index=True)
    inventory_item_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_inventory_items.id"), index=True)
    ingredient_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    substitution_group: Mapped[str | None] = mapped_column(String(80))
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MealHistory(TimestampedModel, Base):
    __tablename__ = "kitchen_meal_history"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recipe_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_recipes.id"), index=True)
    name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    servings: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    calories_snapshot: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    protein_g_snapshot: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    carbs_g_snapshot: Mapped[float | None] = mapped_column(Float)
    fat_g_snapshot: Mapped[float | None] = mapped_column(Float)
    satisfaction: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    source_plan_block_id: Mapped[str | None] = mapped_column(ForeignKey("plan_blocks.id"), index=True)
    meal_plan_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_meal_plans.id"), index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), index=True)
    recommendation_option_id: Mapped[str | None] = mapped_column(ForeignKey("recommendation_options.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    actual_usage_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_kitchen_meal_history_idempotency"),)


class NutritionTarget(TimestampedModel, Base):
    __tablename__ = "kitchen_nutrition_targets"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    calories_target: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    protein_g_target: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class PreferenceEvidence(TimestampedModel, Base):
    __tablename__ = "kitchen_preference_evidence"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recipe_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_recipes.id"), index=True)
    category: Mapped[str | None] = mapped_column(String(80))
    protein_family: Mapped[str | None] = mapped_column(String(80), index=True)
    signal: Mapped[str] = mapped_column(String(80), default="explicit", nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ShoppingNeed(TimestampedModel, Base):
    __tablename__ = "kitchen_shopping_needs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    required_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="forecast", nullable=False)
    forecast_window_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meal_plan_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_meal_plans.id"), index=True)
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    estimated_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), index=True)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_kitchen_shopping_need_idempotency"),)


class ShoppingNeedItem(TimestampedModel, Base):
    __tablename__ = "kitchen_shopping_need_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    shopping_need_id: Mapped[str] = mapped_column(ForeignKey("kitchen_shopping_needs.id"), nullable=False, index=True)
    inventory_item_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_inventory_items.id"), index=True)
    ingredient_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    satisfied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    priority_class: Mapped[str] = mapped_column(String(40), default="optional", nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_id: Mapped[str | None] = mapped_column(String(36), index=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    purchased_quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="needed", nullable=False, index=True)


class TrainingExample(TimestampedModel, Base):
    __tablename__ = "personal_training_examples"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    extraction_version: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"), index=True)
    plan_block_id: Mapped[str | None] = mapped_column(ForeignKey("plan_blocks.id"), index=True)
    source_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80))
    source_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    domain: Mapped[str | None] = mapped_column(String(80), index=True)
    label_source: Mapped[str] = mapped_column(String(120), default="plan_block", nullable=False)
    feature_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    label_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "feature_schema_version", "plan_block_id", name="uq_training_example_user_schema_block"),
    )


class PersonalModelVersion(TimestampedModel, Base):
    __tablename__ = "personal_model_versions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_stage: Mapped[str] = mapped_column(String(40), default="STAGE_1", nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="CANDIDATE", nullable=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effective_evidence_n: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    baseline_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    promotion_reason: Mapped[str | None] = mapped_column(Text)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_model_version_id: Mapped[str | None] = mapped_column(ForeignKey("personal_model_versions.id"), index=True)
    refresh_run_id: Mapped[str | None] = mapped_column(String(36), index=True)

    __table_args__ = (UniqueConstraint("user_id", "model_type", "version", name="uq_personal_model_user_type_version"),)


class PatternEvidence(TimestampedModel, Base):
    __tablename__ = "personal_pattern_evidence"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    pattern_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weighted_support: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    first_observed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    correction_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_model_version_id: Mapped[str | None] = mapped_column(ForeignKey("personal_model_versions.id"), index=True)


class PersonalModelRefreshRun(TimestampedModel, Base):
    __tablename__ = "personal_model_refresh_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feature_schema_version: Mapped[str] = mapped_column(String(80), default="personal-features-v1", nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(80), default="personal-extractor-v1", nullable=False)
    evidence_n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class MediaAsset(TimestampedModel, Base):
    __tablename__ = "media_assets"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    storage_provider: Mapped[str] = mapped_column(String(40), default="local", nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="upload", nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    generation_version: Mapped[str | None] = mapped_column(String(80))
    linked_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    linked_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (UniqueConstraint("user_id", "kind", "content_hash", name="uq_media_asset_user_kind_hash"),)


class FinanceCategory(TimestampedModel, Base):
    __tablename__ = "finance_categories"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="expense", nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_finance_category_user_name"),)


class MerchantIdentity(TimestampedModel, Base):
    __tablename__ = "finance_merchants"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    default_category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)

    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_finance_merchant_normalized"),)


class MerchantAlias(TimestampedModel, Base):
    __tablename__ = "finance_merchant_aliases"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("finance_merchants.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(60), default="observed", nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "normalized_alias", name="uq_finance_merchant_alias"),)


class FinanceTransaction(TimestampedModel, Base):
    __tablename__ = "finance_transactions"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), default="expense", nullable=False, index=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(240))
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("finance_merchants.id"), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)
    source: Mapped[str] = mapped_column(String(60), default="manual", nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(180), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    receipt_import_id: Mapped[str | None] = mapped_column(ForeignKey("receipt_imports.id"), index=True)
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("finance_import_batches.id"), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_finance_transaction_fingerprint"),)


class FinanceImportBatch(TimestampedModel, Base):
    __tablename__ = "finance_import_batches"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(240), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    mapping_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ready_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_finance_import_batch_hash"),)


class FinanceImportRow(TimestampedModel, Base):
    __tablename__ = "finance_import_rows"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("finance_import_batches.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_on: Mapped[date | None] = mapped_column(Date, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    direction: Mapped[str | None] = mapped_column(String(20), index=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(240))
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("finance_merchants.id"), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(180))
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="ready", nullable=False, index=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("batch_id", "row_number", name="uq_finance_import_row_number"),)


class FinanceBudget(TimestampedModel, Base):
    __tablename__ = "finance_budgets"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    period: Mapped[str] = mapped_column(String(40), default="monthly", nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "name", "month_start", name="uq_finance_budget_period"),)


class RecurringExpense(TimestampedModel, Base):
    __tablename__ = "finance_recurring_expenses"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("finance_merchants.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    typical_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_expected_on: Mapped[date | None] = mapped_column(Date, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="candidate", nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "merchant_id", name="uq_finance_recurring_merchant"),)


class ReceiptImport(TimestampedModel, Base):
    __tablename__ = "receipt_imports"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False, index=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(240))
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("finance_merchants.id"), index=True)
    transaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    extraction_provider: Mapped[str | None] = mapped_column(String(80))
    extraction_model: Mapped[str | None] = mapped_column(String(160))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    finance_transaction_id: Mapped[str | None] = mapped_column(String(36), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "asset_id", name="uq_receipt_import_asset"),)


class ReceiptLine(TimestampedModel, Base):
    __tablename__ = "receipt_lines"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    receipt_import_id: Mapped[str] = mapped_column(ForeignKey("receipt_imports.id"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(180), index=True)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    category: Mapped[str] = mapped_column(String(60), default="other", nullable=False, index=True)
    confidence_name: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_price: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_ingredients.id"), index=True)
    inventory_item_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_inventory_items.id"), index=True)
    inventory_lot_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_inventory_lots.id"), index=True)
    shopping_need_item_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_shopping_need_items.id"), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("receipt_import_id", "line_number", name="uq_receipt_line_number"),)


class MealPlan(TimestampedModel, Base):
    __tablename__ = "kitchen_meal_plans"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("kitchen_recipes.id"), nullable=False, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), index=True)
    recommendation_option_id: Mapped[str | None] = mapped_column(ForeignKey("recommendation_options.id"), index=True)
    planned_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    meal_type: Mapped[str] = mapped_column(String(40), default="dinner", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="selected", nullable=False, index=True)
    planned_servings: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    nutrition_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    planned_ingredients_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    modifications_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    shopping_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    cooking_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), index=True)
    meal_history_id: Mapped[str | None] = mapped_column(String(36), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_kitchen_meal_plan_idempotency"),)


class CookingTechnique(TimestampedModel, Base):
    __tablename__ = "cooking_techniques"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_cooking_technique_key"),)


class RecipeTechnique(TimestampedModel, Base):
    __tablename__ = "kitchen_recipe_techniques"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("kitchen_recipes.id"), nullable=False, index=True)
    technique_id: Mapped[str] = mapped_column(ForeignKey("cooking_techniques.id"), nullable=False, index=True)
    required_level: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=1, nullable=False)

    __table_args__ = (UniqueConstraint("recipe_id", "technique_id", name="uq_recipe_technique"),)


class CookingCompetency(TimestampedModel, Base):
    __tablename__ = "cooking_competencies"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    technique_id: Mapped[str] = mapped_column(ForeignKey("cooking_techniques.id"), nullable=False, index=True)
    estimated_level: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "technique_id", name="uq_cooking_competency"),)


class CookingCompetencyEvidence(TimestampedModel, Base):
    __tablename__ = "cooking_competency_evidence"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    competency_id: Mapped[str] = mapped_column(ForeignKey("cooking_competencies.id"), nullable=False, index=True)
    meal_history_id: Mapped[str | None] = mapped_column(ForeignKey("kitchen_meal_history.id"), index=True)
    source: Mapped[str] = mapped_column(String(60), default="meal_completion", nullable=False)
    successful: Mapped[bool | None] = mapped_column(Boolean)
    difficulty: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_cooking_evidence_idempotency"),)


class MealFeedback(TimestampedModel, Base):
    __tablename__ = "kitchen_meal_feedback"

    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False, index=True)
    meal_history_id: Mapped[str] = mapped_column(ForeignKey("kitchen_meal_history.id"), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    interpretation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_kitchen_meal_feedback_idempotency"),)
