"""assistant boundary v0.7

Revision ID: 0007_assistant
Revises: 0006_learning_domain
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_assistant"
down_revision = "0006_learning_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_action_proposals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_role", sa.String(length=80), nullable=False, server_default="GENERAL_ASSISTANT"),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("consequence_category", sa.String(length=80), nullable=False, server_default="consequential"),
        sa.Column("expected_world_revision", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_action_proposals_user_id", "assistant_action_proposals", ["user_id"])
    op.create_index("ix_assistant_action_proposals_assistant_role", "assistant_action_proposals", ["assistant_role"])
    op.create_index("ix_assistant_action_proposals_tool_name", "assistant_action_proposals", ["tool_name"])
    op.create_index("ix_assistant_action_proposals_status", "assistant_action_proposals", ["status"])
    op.create_index("ix_assistant_action_proposals_expires_at", "assistant_action_proposals", ["expires_at"])
    op.create_index("ix_assistant_action_proposals_idempotency_key", "assistant_action_proposals", ["idempotency_key"])

    op.create_table(
        "ai_action_audits",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_role", sa.String(length=80), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="fake"),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("model_tier", sa.String(length=40), nullable=False, server_default="NO_AI"),
        sa.Column("tool_name", sa.String(length=120), nullable=True),
        sa.Column("proposal_id", sa.String(length=36), nullable=True),
        sa.Column("mutation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["proposal_id"], ["assistant_action_proposals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_action_audits_user_id", "ai_action_audits", ["user_id"])
    op.create_index("ix_ai_action_audits_assistant_role", "ai_action_audits", ["assistant_role"])
    op.create_index("ix_ai_action_audits_request_id", "ai_action_audits", ["request_id"])
    op.create_index("ix_ai_action_audits_tool_name", "ai_action_audits", ["tool_name"])
    op.create_index("ix_ai_action_audits_status", "ai_action_audits", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_action_audits_status", table_name="ai_action_audits")
    op.drop_index("ix_ai_action_audits_tool_name", table_name="ai_action_audits")
    op.drop_index("ix_ai_action_audits_request_id", table_name="ai_action_audits")
    op.drop_index("ix_ai_action_audits_assistant_role", table_name="ai_action_audits")
    op.drop_index("ix_ai_action_audits_user_id", table_name="ai_action_audits")
    op.drop_table("ai_action_audits")

    op.drop_index("ix_assistant_action_proposals_idempotency_key", table_name="assistant_action_proposals")
    op.drop_index("ix_assistant_action_proposals_expires_at", table_name="assistant_action_proposals")
    op.drop_index("ix_assistant_action_proposals_status", table_name="assistant_action_proposals")
    op.drop_index("ix_assistant_action_proposals_tool_name", table_name="assistant_action_proposals")
    op.drop_index("ix_assistant_action_proposals_assistant_role", table_name="assistant_action_proposals")
    op.drop_index("ix_assistant_action_proposals_user_id", table_name="assistant_action_proposals")
    op.drop_table("assistant_action_proposals")
