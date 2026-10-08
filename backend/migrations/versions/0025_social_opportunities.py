"""Add v1.8C social trajectory evidence and opportunities.

Revision ID: 0025_social_opportunities
Revises: 0024_leisure_movies
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0025_social_opportunities"
down_revision: Union[str, Sequence[str], None] = "0024_leisure_movies"
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
        "social_activities",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("activity_type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meaningful", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_ref", sa.String(180)),
        sa.Column("recommendation_id", sa.String(36)),
        sa.Column("recommendation_option_id", sa.String(36)),
        sa.Column("idempotency_key", sa.String(180)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_social_activities_user_id"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], name="fk_social_activities_recommendation_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recommendation_option_id"], ["recommendation_options.id"], name="fk_social_activities_recommendation_option_id", ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_social_activities_user_idempotency"),
    )
    for column in ("user_id", "activity_type", "occurred_at", "source", "source_ref", "recommendation_id", "recommendation_option_id"):
        op.create_index(f"ix_social_activities_{column}", "social_activities", [column])

    op.create_table(
        "opportunities",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("opportunity_type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("canonical_title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("venue", sa.String(255)),
        sa.Column("city", sa.String(120)),
        sa.Column("region", sa.String(120)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("cost_min", sa.Numeric(12, 2)),
        sa.Column("cost_max", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("pricing_source", sa.String(80)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("entities_json", sa.JSON(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_opportunities_user_id"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_opportunities_time_order"),
        sa.CheckConstraint("cost_min IS NULL OR cost_min >= 0", name="ck_opportunities_cost_min"),
        sa.CheckConstraint("cost_max IS NULL OR cost_max >= cost_min", name="ck_opportunities_cost_max"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ENDED', 'CANCELLED', 'STALE', 'ARCHIVED')", name="ck_opportunities_status"),
    )
    for column in ("user_id", "opportunity_type", "starts_at", "ends_at", "city", "region", "status", "source_hash"):
        op.create_index(f"ix_opportunities_{column}", "opportunities", [column])
    op.create_index("ix_opportunities_user_status_start", "opportunities", ["user_id", "status", "starts_at"])
    op.create_index("ix_opportunities_dedupe", "opportunities", ["user_id", "canonical_title", "starts_at", "venue"])

    op.create_table(
        "opportunity_external_ids",
        sa.Column("opportunity_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(180), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], name="fk_opportunity_external_ids_opportunity_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_opportunity_external_ids_user_id"),
        sa.UniqueConstraint("user_id", "provider", "external_id", name="uq_opportunity_external_identity"),
    )
    for column in ("opportunity_id", "user_id", "provider"):
        op.create_index(f"ix_opportunity_external_ids_{column}", "opportunity_external_ids", [column])

    op.create_table(
        "opportunity_source_states",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("city", sa.String(120)),
        sa.Column("region", sa.String(120)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("categories_json", sa.JSON(), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("last_discovery_at", sa.DateTime(timezone=True)),
        sa.Column("next_discovery_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(40), nullable=False),
        sa.Column("last_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_opportunity_source_states_user_id"),
        sa.UniqueConstraint("user_id", "source_id", name="uq_opportunity_source_user_source"),
        sa.CheckConstraint("cadence_minutes >= 15", name="ck_opportunity_source_cadence"),
        sa.CheckConstraint("horizon_days >= 1 AND horizon_days <= 180", name="ck_opportunity_source_horizon"),
    )
    for column in ("user_id", "source_id", "enabled", "next_discovery_at", "last_status"):
        op.create_index(f"ix_opportunity_source_states_{column}", "opportunity_source_states", [column])

    op.create_table(
        "opportunity_user_states",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("opportunity_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True)),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("attended_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_opportunity_user_states_user_id"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], name="fk_opportunity_user_states_opportunity_id", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "opportunity_id", name="uq_opportunity_user_state"),
        sa.CheckConstraint("status IN ('AVAILABLE', 'INTERESTED', 'DISMISSED', 'ATTENDED')", name="ck_opportunity_user_state_status"),
    )
    for column in ("user_id", "opportunity_id", "status"):
        op.create_index(f"ix_opportunity_user_states_{column}", "opportunity_user_states", [column])


def downgrade() -> None:
    op.drop_table("opportunity_user_states")
    op.drop_table("opportunity_source_states")
    op.drop_table("opportunity_external_ids")
    op.drop_table("opportunities")
    op.drop_table("social_activities")
