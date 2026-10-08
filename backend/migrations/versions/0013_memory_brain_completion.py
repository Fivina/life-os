"""complete memory and learning brain v1.2

Revision ID: 0013_memory_brain_completion
Revises: 0012_memory_brain
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0013_memory_brain_completion"
down_revision = "0012_memory_brain"
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
    op.create_table(
        "memory_suppressions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("suppression_key", sa.String(length=255), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.String(length=80), nullable=False, server_default="user_forgot"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "suppression_key", name="uq_memory_suppression_user_key"),
    )
    _indexes("memory_suppressions", ["user_id", "normalized_key", "source_type", "source_id", "active", "expires_at"])

    op.create_table(
        "memory_processing_jobs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "job_type", "source_type", "source_id", name="uq_memory_job_source"),
    )
    _indexes("memory_processing_jobs", ["user_id", "job_type", "source_type", "source_id", "status", "available_at", "processed_at"])

    op.create_table(
        "memory_retrieval_audits",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("retrieval_type", sa.String(length=40), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("domains_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("returned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
    )
    _indexes("memory_retrieval_audits", ["user_id", "retrieval_type", "query_hash", "degraded"])

    op.create_table(
        "memory_learning_bridge_runs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"),
        sa.Column("memory_change_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pattern_change_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommendation_outcome_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "period_start", "period_end", name="uq_memory_learning_bridge_period"),
    )
    _indexes("memory_learning_bridge_runs", ["user_id", "period_start", "period_end", "status"])

    op.create_table(
        "recommendations",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("domain", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="created"),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_recommendation_user_idempotency"),
    )
    _indexes("recommendations", ["user_id", "domain", "kind", "status", "idempotency_key"])

    op.create_table(
        "recommendation_options",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("recommendation_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=220), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reference_type", sa.String(length=80), nullable=True),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("recommendation_id", "rank", name="uq_recommendation_option_rank"),
    )
    _indexes("recommendation_options", ["user_id", "recommendation_id", "reference_id"])

    op.add_column("recommendation_outcomes", sa.Column("recommendation_id", sa.String(length=36), nullable=True))
    op.add_column("recommendation_outcomes", sa.Column("option_id", sa.String(length=36), nullable=True))
    op.add_column("recommendation_outcomes", sa.Column("feedback_text", sa.Text(), nullable=True))
    op.add_column("recommendation_outcomes", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.create_foreign_key("fk_recommendation_outcomes_recommendation_id", "recommendation_outcomes", "recommendations", ["recommendation_id"], ["id"])
    op.create_foreign_key("fk_recommendation_outcomes_option_id", "recommendation_outcomes", "recommendation_options", ["option_id"], ["id"])
    op.create_unique_constraint("uq_recommendation_outcome_user_idempotency", "recommendation_outcomes", ["user_id", "idempotency_key"])
    _indexes("recommendation_outcomes", ["recommendation_id", "option_id", "idempotency_key"])


def downgrade() -> None:
    for column in ["idempotency_key", "option_id", "recommendation_id"]:
        op.drop_index(f"ix_recommendation_outcomes_{column}", table_name="recommendation_outcomes")
    op.drop_constraint("uq_recommendation_outcome_user_idempotency", "recommendation_outcomes", type_="unique")
    op.drop_constraint("fk_recommendation_outcomes_option_id", "recommendation_outcomes", type_="foreignkey")
    op.drop_constraint("fk_recommendation_outcomes_recommendation_id", "recommendation_outcomes", type_="foreignkey")
    for column in ["idempotency_key", "feedback_text", "option_id", "recommendation_id"]:
        op.drop_column("recommendation_outcomes", column)

    for table, columns in [
        ("recommendation_options", ["reference_id", "recommendation_id", "user_id"]),
        ("recommendations", ["idempotency_key", "status", "kind", "domain", "user_id"]),
        ("memory_retrieval_audits", ["degraded", "query_hash", "retrieval_type", "user_id"]),
        ("memory_learning_bridge_runs", ["status", "period_end", "period_start", "user_id"]),
        ("memory_processing_jobs", ["processed_at", "available_at", "status", "source_id", "source_type", "job_type", "user_id"]),
        ("memory_suppressions", ["expires_at", "active", "source_id", "source_type", "normalized_key", "user_id"]),
    ]:
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
