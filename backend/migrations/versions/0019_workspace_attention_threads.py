"""Add v1.6B workspaces, attention items, and structured threads.

Revision ID: 0019_workspace_attention_threads
Revises: 0018_decision_infrastructure
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0019_workspace_attention_threads"
down_revision: Union[str, Sequence[str], None] = "0018_decision_infrastructure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "active_workspaces",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("is_foreground", sa.Boolean(), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("conversation_thread_id", sa.String(length=36), nullable=True),
        sa.Column("primary_entity_type", sa.String(length=80), nullable=True),
        sa.Column("primary_entity_id", sa.String(length=160), nullable=True),
        sa.Column("current_phase", sa.String(length=80), nullable=True),
        sa.Column("current_step", sa.String(length=160), nullable=True),
        sa.Column("canonical_change_refs_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_meaningful_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("payload_version >= 1", name="ck_active_workspaces_payload_version"),
        sa.CheckConstraint("state_revision >= 1", name="ck_active_workspaces_state_revision"),
        sa.ForeignKeyConstraint(
            ["conversation_thread_id"], ["conversation_threads.id"],
            name="fk_active_workspaces_conversation_thread_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_active_workspaces_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_active_workspaces_user_idempotency"),
    )
    for column in (
        "user_id", "workspace_type", "status", "is_foreground", "conversation_thread_id",
        "primary_entity_type", "primary_entity_id", "completed_at", "abandoned_at", "last_meaningful_activity_at",
    ):
        op.create_index(f"ix_active_workspaces_{column}", "active_workspaces", [column])
    op.create_index(
        "uq_active_workspaces_user_foreground",
        "active_workspaces",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_foreground IS TRUE"),
        sqlite_where=sa.text("is_foreground = 1"),
    )
    op.create_index(
        "ix_active_workspaces_user_status_type", "active_workspaces", ["user_id", "status", "workspace_type"]
    )

    op.create_table(
        "open_threads",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("entities_json", sa.JSON(), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_ref", sa.String(length=160), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_open_threads_confidence"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_open_threads_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "domain", "category", "status", "source", "source_ref"):
        op.create_index(f"ix_open_threads_{column}", "open_threads", [column])
    op.create_index("ix_open_threads_user_status_updated", "open_threads", ["user_id", "status", "updated_at"])

    op.create_table(
        "prospective_threads",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("entities_json", sa.JSON(), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=True),
        sa.Column("trigger_type", sa.String(length=60), nullable=False),
        sa.Column("trigger_conditions_json", sa.JSON(), nullable=False),
        sa.Column("earliest_relevance", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_relevance", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_policy", sa.String(length=80), nullable=False),
        sa.Column("attention_policy", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_ref", sa.String(length=160), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_prospective_threads_confidence"),
        sa.CheckConstraint(
            "earliest_relevance IS NULL OR latest_relevance IS NULL OR earliest_relevance <= latest_relevance",
            name="ck_prospective_threads_relevance_window",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_prospective_threads_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "domain", "trigger_type", "earliest_relevance", "latest_relevance", "status", "source", "source_ref",
    ):
        op.create_index(f"ix_prospective_threads_{column}", "prospective_threads", [column])
    op.create_index(
        "ix_prospective_threads_user_status_trigger", "prospective_threads", ["user_id", "status", "trigger_type"]
    )
    op.create_index(
        "ix_prospective_threads_user_relevance",
        "prospective_threads",
        ["user_id", "earliest_relevance", "latest_relevance"],
    )

    op.create_table(
        "attention_items",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("source_cognitive_event_id", sa.String(length=160), nullable=True),
        sa.Column("source_trace_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("open_thread_id", sa.String(length=36), nullable=True),
        sa.Column("prospective_thread_id", sa.String(length=36), nullable=True),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("surfaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deduplication_key", sa.String(length=180), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("priority >= 0 AND priority <= 100", name="ck_attention_items_priority"),
        sa.CheckConstraint(
            "expires_at IS NULL OR not_before IS NULL OR not_before <= expires_at",
            name="ck_attention_items_window",
        ),
        sa.ForeignKeyConstraint(
            ["open_thread_id"], ["open_threads.id"], name="fk_attention_items_open_thread_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["prospective_thread_id"], ["prospective_threads.id"],
            name="fk_attention_items_prospective_thread_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_trace_id"], ["cognitive_traces.id"], name="fk_attention_items_source_trace_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["active_workspaces.id"], name="fk_attention_items_workspace_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_attention_items_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "deduplication_key", name="uq_attention_items_user_deduplication"),
    )
    for column in (
        "user_id", "action", "reason_code", "priority", "source_cognitive_event_id", "source_trace_id",
        "workspace_id", "open_thread_id", "prospective_thread_id", "not_before", "expires_at", "status",
    ):
        op.create_index(f"ix_attention_items_{column}", "attention_items", [column])
    op.create_index(
        "ix_attention_items_user_status_not_before", "attention_items", ["user_id", "status", "not_before"]
    )


def downgrade() -> None:
    op.drop_index("ix_attention_items_user_status_not_before", table_name="attention_items")
    for column in reversed((
        "user_id", "action", "reason_code", "priority", "source_cognitive_event_id", "source_trace_id",
        "workspace_id", "open_thread_id", "prospective_thread_id", "not_before", "expires_at", "status",
    )):
        op.drop_index(f"ix_attention_items_{column}", table_name="attention_items")
    op.drop_table("attention_items")

    op.drop_index("ix_prospective_threads_user_relevance", table_name="prospective_threads")
    op.drop_index("ix_prospective_threads_user_status_trigger", table_name="prospective_threads")
    for column in reversed((
        "user_id", "domain", "trigger_type", "earliest_relevance", "latest_relevance", "status", "source", "source_ref",
    )):
        op.drop_index(f"ix_prospective_threads_{column}", table_name="prospective_threads")
    op.drop_table("prospective_threads")

    op.drop_index("ix_open_threads_user_status_updated", table_name="open_threads")
    for column in reversed(("user_id", "domain", "category", "status", "source", "source_ref")):
        op.drop_index(f"ix_open_threads_{column}", table_name="open_threads")
    op.drop_table("open_threads")

    op.drop_index("ix_active_workspaces_user_status_type", table_name="active_workspaces")
    op.drop_index("uq_active_workspaces_user_foreground", table_name="active_workspaces")
    for column in reversed((
        "user_id", "workspace_type", "status", "is_foreground", "conversation_thread_id",
        "primary_entity_type", "primary_entity_id", "completed_at", "abandoned_at", "last_meaningful_activity_at",
    )):
        op.drop_index(f"ix_active_workspaces_{column}", table_name="active_workspaces")
    op.drop_table("active_workspaces")
