"""memory and learning brain v1.2

Revision ID: 0012_memory_brain
Revises: 0011_intelligence_foundation
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision = "0012_memory_brain"
down_revision = "0011_intelligence_foundation"
branch_labels = None
depends_on = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    ]


def _indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "memory_items",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("memory_type", sa.String(length=60), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False, server_default="general"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=False),
        sa.Column("polarity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="candidate"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_kind", sa.String(length=60), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_memory_id", sa.String(length=36), nullable=True),
        sa.Column("embedding_vector", Vector(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=80), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_version", sa.String(length=80), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["supersedes_memory_id"], ["memory_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
    )
    _indexes(
        "memory_items",
        ["user_id", "memory_type", "domain", "normalized_key", "confidence", "importance", "status", "pinned", "user_confirmed", "source_kind", "last_observed_at", "deleted_at", "supersedes_memory_id"],
    )

    op.create_table(
        "memory_evidence",
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("evidence_kind", sa.String(length=60), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="supports"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("memory_id", "source_type", "source_id", "evidence_kind", "direction", name="uq_memory_evidence_source"),
    )
    _indexes("memory_evidence", ["memory_id", "user_id", "source_type", "source_id", "evidence_kind", "direction", "observed_at"])

    op.create_table(
        "memory_episodes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("source_event_start_id", sa.String(length=36), nullable=True),
        sa.Column("source_event_end_id", sa.String(length=36), nullable=True),
        sa.Column("source_summary_id", sa.String(length=36), nullable=True),
        sa.Column("related_entities_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("embedding_vector", Vector(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=80), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_version", sa.String(length=80), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["source_event_start_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["source_event_end_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["source_summary_id"], ["conversation_summaries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "normalized_key", name="uq_memory_episode_user_key"),
    )
    _indexes("memory_episodes", ["user_id", "domain", "normalized_key", "start_at", "end_at", "importance", "status", "source_event_start_id", "source_event_end_id", "source_summary_id"])

    op.create_table(
        "recommendation_outcomes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("source_entity_type", sa.String(length=80), nullable=True),
        sa.Column("source_entity_id", sa.String(length=36), nullable=True),
        sa.Column("recommendation_summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=60), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
    )
    _indexes("recommendation_outcomes", ["user_id", "domain", "recommendation_type", "source_entity_id", "outcome", "accepted", "observed_at"])

    op.create_table(
        "memory_consolidation_runs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("source_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("episode_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "period_start", "period_end", name="uq_memory_consolidation_period"),
    )
    _indexes("memory_consolidation_runs", ["user_id", "period_start", "period_end", "status"])


def downgrade() -> None:
    for table, columns in [
        ("memory_consolidation_runs", ["status", "period_end", "period_start", "user_id"]),
        ("recommendation_outcomes", ["observed_at", "accepted", "outcome", "source_entity_id", "recommendation_type", "domain", "user_id"]),
        ("memory_episodes", ["source_summary_id", "source_event_end_id", "source_event_start_id", "status", "importance", "end_at", "start_at", "normalized_key", "domain", "user_id"]),
        ("memory_evidence", ["observed_at", "direction", "evidence_kind", "source_id", "source_type", "user_id", "memory_id"]),
        ("memory_items", ["supersedes_memory_id", "deleted_at", "last_observed_at", "source_kind", "user_confirmed", "pinned", "status", "importance", "confidence", "normalized_key", "domain", "memory_type", "user_id"]),
    ]:
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    # Keep the shared vector extension installed; another application table may use it later.
