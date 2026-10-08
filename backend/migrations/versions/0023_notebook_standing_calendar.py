"""Add v1.8A notebook and standing calendar fixtures.

Revision ID: 0023_notebook_standing_calendar
Revises: 0022_strategic_plan_proposals
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.database.types import PortableVector


revision: str = "0023_notebook_standing_calendar"
down_revision: Union[str, Sequence[str], None] = "0022_strategic_plan_proposals"
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
        "notebook_entries",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("entry_type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("source_ref", sa.String(160)),
        sa.Column("conversation_thread_id", sa.String(36)),
        sa.Column("workspace_ref", sa.String(80)),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(160)),
        sa.Column("embedding_vector", PortableVector()),
        sa.Column("embedding_provider", sa.String(80)),
        sa.Column("embedding_model", sa.String(160)),
        sa.Column("embedding_dimension", sa.Integer()),
        sa.Column("embedding_version", sa.String(80)),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("entry_type IN ('GENERAL', 'IMPLEMENTATION_IDEA')", name="ck_notebook_entries_type"),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVIEWED', 'PROMOTED', 'ARCHIVED')", name="ck_notebook_entries_status"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_notebook_entries_user_id"),
        sa.ForeignKeyConstraint(["conversation_thread_id"], ["conversation_threads.id"], name="fk_notebook_entries_conversation_thread_id", ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_notebook_entries_user_idempotency"),
    )
    for column in ("user_id", "entry_type", "status", "source", "source_ref", "conversation_thread_id", "workspace_ref", "reviewed_at", "archived_at", "promoted_at"):
        op.create_index(f"ix_notebook_entries_{column}", "notebook_entries", [column])
    op.create_index("ix_notebook_entries_user_status_created", "notebook_entries", ["user_id", "status", "created_at"])

    op.create_table(
        "notebook_promotions",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("notebook_entry_id", sa.String(36), nullable=False),
        sa.Column("destination_type", sa.String(80), nullable=False),
        sa.Column("destination_ref", sa.String(160)),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("destination_type IN ('MANUAL_DEVELOPMENT_REVIEW')", name="ck_notebook_promotions_destination"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_notebook_promotions_user_id"),
        sa.ForeignKeyConstraint(["notebook_entry_id"], ["notebook_entries.id"], name="fk_notebook_promotions_entry_id", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_notebook_promotions_user_idempotency"),
        sa.UniqueConstraint("notebook_entry_id", "destination_type", name="uq_notebook_promotions_entry_destination"),
    )
    for column in ("user_id", "notebook_entry_id", "destination_type", "destination_ref"):
        op.create_index(f"ix_notebook_promotions_{column}", "notebook_promotions", [column])

    op.create_table(
        "standing_calendar_rules",
        sa.Column("user_id", sa.String(36), nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("rule_type", sa.String(60), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("protected", sa.Boolean(), nullable=False), sa.Column("auto_create", sa.Boolean(), nullable=False),
        sa.Column("source_provider", sa.String(80), nullable=False), sa.Column("source_identity", sa.String(180), nullable=False),
        sa.Column("source_config_json", sa.JSON(), nullable=False), sa.Column("reconciliation_policy_json", sa.JSON(), nullable=False),
        sa.Column("sync_interval_days", sa.Integer(), nullable=False), sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("next_sync_at", sa.DateTime(timezone=True)), sa.Column("last_sync_status", sa.String(40), nullable=False),
        sa.Column("last_sync_summary_json", sa.JSON(), nullable=False), sa.Column("last_error", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False), *_timestamps(),
        sa.CheckConstraint("rule_type IN ('SPORTS_FIXTURE')", name="ck_standing_rules_type"),
        sa.CheckConstraint("sync_interval_days = 14", name="ck_standing_rules_sync_interval"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_standing_rules_user_id"),
        sa.UniqueConstraint("user_id", "rule_type", "source_provider", "source_identity", name="uq_standing_rules_identity"),
    )
    for column in ("user_id", "rule_type", "enabled", "source_provider", "last_sync_at", "next_sync_at", "last_sync_status"):
        op.create_index(f"ix_standing_calendar_rules_{column}", "standing_calendar_rules", [column])
    op.create_index("ix_standing_rules_due", "standing_calendar_rules", ["enabled", "next_sync_at"])

    op.create_table(
        "fixture_bindings",
        sa.Column("user_id", sa.String(36), nullable=False), sa.Column("standing_rule_id", sa.String(36), nullable=False),
        sa.Column("commitment_id", sa.String(36)), sa.Column("source_provider", sa.String(80), nullable=False),
        sa.Column("source_fixture_id", sa.String(180), nullable=False), sa.Column("fixture_status", sa.String(40), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True)), sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=False), sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.Column("protection_overridden", sa.Boolean(), nullable=False), sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("fixture_status IN ('SCHEDULED', 'CONFIRMED', 'POSTPONED', 'CANCELLED', 'COMPLETED')", name="ck_fixture_bindings_status"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_fixture_bindings_user_id"),
        sa.ForeignKeyConstraint(["standing_rule_id"], ["standing_calendar_rules.id"], name="fk_fixture_bindings_rule_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], name="fk_fixture_bindings_commitment_id", ondelete="SET NULL"),
        sa.UniqueConstraint("commitment_id", name="uq_fixture_bindings_commitment_id"),
        sa.UniqueConstraint("user_id", "source_provider", "source_fixture_id", name="uq_fixture_bindings_source_identity"),
    )
    for column in ("user_id", "standing_rule_id", "commitment_id", "source_provider", "fixture_status", "kickoff_at", "suppressed"):
        op.create_index(f"ix_fixture_bindings_{column}", "fixture_bindings", [column])


def downgrade() -> None:
    op.drop_table("fixture_bindings")
    op.drop_table("standing_calendar_rules")
    op.drop_table("notebook_promotions")
    op.drop_table("notebook_entries")
