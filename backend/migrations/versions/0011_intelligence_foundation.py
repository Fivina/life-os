"""intelligence foundation v1.1

Revision ID: 0011_intelligence_foundation
Revises: 0010_daily_driver
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0011_intelligence_foundation"
down_revision = "0010_daily_driver"
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


def upgrade() -> None:
    op.create_table(
        "conversation_threads",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False, server_default="New conversation"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("default_skill", sa.String(length=120), nullable=False, server_default="self-core"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
    )
    op.create_index("ix_conversation_threads_user_id", "conversation_threads", ["user_id"])
    op.create_index("ix_conversation_threads_status", "conversation_threads", ["status"])
    op.create_index("ix_conversation_threads_default_skill", "conversation_threads", ["default_skill"])
    op.create_index("ix_conversation_threads_last_message_at", "conversation_threads", ["last_message_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("skill_name", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("thread_id", "sequence_number", name="uq_conversation_message_thread_sequence"),
    )
    for column in ["thread_id", "user_id", "role", "skill_name", "request_id"]:
        op.create_index(f"ix_conversation_messages_{column}", "conversation_messages", [column])

    op.create_table(
        "conversation_summaries",
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("covers_until_message_id", sa.String(length=36), nullable=True),
        sa.Column("covered_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["covers_until_message_id"], ["conversation_messages.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("thread_id", name="uq_conversation_summaries_thread_id"),
    )
    op.create_index("ix_conversation_summaries_thread_id", "conversation_summaries", ["thread_id"], unique=True)
    op.create_index("ix_conversation_summaries_user_id", "conversation_summaries", ["user_id"])
    op.create_index("ix_conversation_summaries_covers_until_message_id", "conversation_summaries", ["covers_until_message_id"])

    op.add_column("ai_action_audits", sa.Column("capability", sa.String(length=40), nullable=True))
    op.add_column("ai_action_audits", sa.Column("skill_name", sa.String(length=120), nullable=True))
    op.add_column("ai_action_audits", sa.Column("skill_version", sa.String(length=40), nullable=True))
    op.add_column("ai_action_audits", sa.Column("prompt_version", sa.String(length=40), nullable=True))
    op.add_column("ai_action_audits", sa.Column("conversation_thread_id", sa.String(length=36), nullable=True))
    op.add_column("ai_action_audits", sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_action_audits", sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_action_audits", sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_action_audits", sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_action_audits", sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"))
    op.add_column("ai_action_audits", sa.Column("cost_estimated", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("ai_action_audits", sa.Column("error_category", sa.String(length=120), nullable=True))
    op.create_foreign_key(
        "fk_ai_action_audits_conversation_thread_id",
        "ai_action_audits",
        "conversation_threads",
        ["conversation_thread_id"],
        ["id"],
    )
    for column in ["capability", "skill_name", "conversation_thread_id", "error_category"]:
        op.create_index(f"ix_ai_action_audits_{column}", "ai_action_audits", [column])


def downgrade() -> None:
    for column in ["error_category", "conversation_thread_id", "skill_name", "capability"]:
        op.drop_index(f"ix_ai_action_audits_{column}", table_name="ai_action_audits")
    op.drop_constraint("fk_ai_action_audits_conversation_thread_id", "ai_action_audits", type_="foreignkey")
    for column in [
        "error_category",
        "cost_estimated",
        "estimated_cost",
        "tool_call_count",
        "cached_tokens",
        "output_tokens",
        "input_tokens",
        "conversation_thread_id",
        "prompt_version",
        "skill_version",
        "skill_name",
        "capability",
    ]:
        op.drop_column("ai_action_audits", column)

    op.drop_index("ix_conversation_summaries_covers_until_message_id", table_name="conversation_summaries")
    op.drop_index("ix_conversation_summaries_user_id", table_name="conversation_summaries")
    op.drop_index("ix_conversation_summaries_thread_id", table_name="conversation_summaries")
    op.drop_table("conversation_summaries")
    for column in ["request_id", "skill_name", "role", "user_id", "thread_id"]:
        op.drop_index(f"ix_conversation_messages_{column}", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    for column in ["last_message_at", "default_skill", "status", "user_id"]:
        op.drop_index(f"ix_conversation_threads_{column}", table_name="conversation_threads")
    op.drop_table("conversation_threads")
