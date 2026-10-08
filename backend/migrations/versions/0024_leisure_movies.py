"""Add v1.8B leisure trajectory and movie continuity.

Revision ID: 0024_leisure_movies
Revises: 0023_notebook_standing_calendar
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0024_leisure_movies"
down_revision: Union[str, Sequence[str], None] = "0023_notebook_standing_calendar"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "leisure_trajectories",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("leisure_type", sa.String(40), nullable=False),
        sa.Column("period", sa.String(40), nullable=False),
        sa.Column("target_min", sa.Integer(), nullable=False),
        sa.Column("target_max", sa.Integer(), nullable=False),
        sa.Column("week_starts_on", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_leisure_trajectories_user_id"),
        sa.UniqueConstraint("user_id", "leisure_type", name="uq_leisure_trajectories_user_type"),
        sa.CheckConstraint("target_min >= 0 AND target_max >= target_min", name="ck_leisure_trajectories_targets"),
        sa.CheckConstraint("week_starts_on >= 0 AND week_starts_on <= 6", name="ck_leisure_trajectories_week_start"),
        sa.CheckConstraint("period IN ('WEEK')", name="ck_leisure_trajectories_period"),
        sa.CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'ARCHIVED')", name="ck_leisure_trajectories_status"),
    )
    op.create_index("ix_leisure_trajectories_user_id", "leisure_trajectories", ["user_id"])
    op.create_index("ix_leisure_trajectories_leisure_type", "leisure_trajectories", ["leisure_type"])
    op.create_index("ix_leisure_trajectories_status", "leisure_trajectories", ["status"])

    op.create_table(
        "movies",
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_title", sa.String(255)),
        sa.Column("release_year", sa.Integer()),
        sa.Column("release_date", sa.Date()),
        sa.Column("runtime_minutes", sa.Integer()),
        sa.Column("genres_json", sa.JSON(), nullable=False),
        sa.Column("overview", sa.Text()),
        sa.Column("poster_url", sa.String(500)),
        sa.Column("metadata_source", sa.String(80)),
        sa.Column("metadata_updated_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("runtime_minutes IS NULL OR runtime_minutes > 0", name="ck_movies_runtime_positive"),
    )
    for column in ("title", "release_year", "release_date", "metadata_source"):
        op.create_index(f"ix_movies_{column}", "movies", [column])
    op.create_index("ix_movies_title_year", "movies", ["title", "release_year"])

    op.create_table(
        "movie_external_ids",
        sa.Column("movie_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(180), nullable=False),
        sa.Column("source_url", sa.String(500)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], name="fk_movie_external_ids_movie_id", ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "external_id", name="uq_movie_external_ids_provider_identity"),
        sa.UniqueConstraint("movie_id", "provider", name="uq_movie_external_ids_movie_provider"),
    )
    op.create_index("ix_movie_external_ids_movie_id", "movie_external_ids", ["movie_id"])
    op.create_index("ix_movie_external_ids_provider", "movie_external_ids", ["provider"])

    op.create_table(
        "movie_watchlist_items",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("movie_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_ref", sa.String(180)),
        sa.Column("notes", sa.Text()),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_movie_watchlist_items_user_id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], name="fk_movie_watchlist_items_movie_id", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_movie_watchlist_user_movie"),
        sa.CheckConstraint("priority >= 0 AND priority <= 100", name="ck_movie_watchlist_priority"),
        sa.CheckConstraint("status IN ('ACTIVE', 'REMOVED', 'WATCHED')", name="ck_movie_watchlist_status"),
    )
    for column in ("user_id", "movie_id", "status", "source", "source_ref"):
        op.create_index(f"ix_movie_watchlist_items_{column}", "movie_watchlist_items", [column])
    op.create_index("ix_movie_watchlist_user_status_added", "movie_watchlist_items", ["user_id", "status", "added_at"])

    op.create_table(
        "movie_viewings",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("movie_id", sa.String(36), nullable=False),
        sa.Column("watched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_ref", sa.String(180)),
        sa.Column("rewatch", sa.Boolean(), nullable=False),
        sa.Column("rating", sa.Float()),
        sa.Column("rating_scale", sa.Float()),
        sa.Column("liked", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("recommendation_id", sa.String(36)),
        sa.Column("recommendation_option_id", sa.String(36)),
        sa.Column("idempotency_key", sa.String(180)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_movie_viewings_user_id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], name="fk_movie_viewings_movie_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], name="fk_movie_viewings_recommendation_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recommendation_option_id"], ["recommendation_options.id"], name="fk_movie_viewings_recommendation_option_id", ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_movie_viewings_user_idempotency"),
        sa.CheckConstraint("rating IS NULL OR rating >= 0", name="ck_movie_viewings_rating_nonnegative"),
        sa.CheckConstraint("rating_scale IS NULL OR rating_scale > 0", name="ck_movie_viewings_scale_positive"),
    )
    for column in ("user_id", "movie_id", "watched_at", "source", "source_ref", "recommendation_id", "recommendation_option_id"):
        op.create_index(f"ix_movie_viewings_{column}", "movie_viewings", [column])
    op.create_index("ix_movie_viewings_user_watched", "movie_viewings", ["user_id", "watched_at"])

    op.create_table(
        "movie_import_batches",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_movie_import_batches_user_id"),
        sa.UniqueConstraint("user_id", "provider", "content_hash", name="uq_movie_import_batches_content"),
        sa.CheckConstraint("status IN ('PREVIEW', 'CONFIRMED', 'PARTIAL', 'FAILED')", name="ck_movie_import_batches_status"),
    )
    for column in ("user_id", "provider", "status"):
        op.create_index(f"ix_movie_import_batches_{column}", "movie_import_batches", [column])

    op.create_table(
        "movie_import_rows",
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("source_row_key", sa.String(180), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("movie_id", sa.String(36)),
        sa.Column("viewing_id", sa.String(36)),
        sa.Column("watchlist_item_id", sa.String(36)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["batch_id"], ["movie_import_batches.id"], name="fk_movie_import_rows_batch_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_movie_import_rows_user_id"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], name="fk_movie_import_rows_movie_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["viewing_id"], ["movie_viewings.id"], name="fk_movie_import_rows_viewing_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["watchlist_item_id"], ["movie_watchlist_items.id"], name="fk_movie_import_rows_watchlist_item_id", ondelete="SET NULL"),
        sa.UniqueConstraint("batch_id", "source_row_key", name="uq_movie_import_rows_batch_key"),
        sa.CheckConstraint("status IN ('READY', 'REVIEW_REQUIRED', 'ERROR', 'IMPORTED', 'SKIPPED')", name="ck_movie_import_rows_status"),
    )
    for column in ("batch_id", "user_id", "source_kind", "status", "movie_id", "viewing_id", "watchlist_item_id"):
        op.create_index(f"ix_movie_import_rows_{column}", "movie_import_rows", [column])


def downgrade() -> None:
    op.drop_table("movie_import_rows")
    op.drop_table("movie_import_batches")
    op.drop_table("movie_viewings")
    op.drop_table("movie_watchlist_items")
    op.drop_table("movie_external_ids")
    op.drop_table("movies")
    op.drop_table("leisure_trajectories")
