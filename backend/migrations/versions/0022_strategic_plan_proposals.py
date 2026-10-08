"""Add v1.7A strategic plan proposals.

Revision ID: 0022_strategic_plan_proposals
Revises: 0021_provider_routing_evidence
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0022_strategic_plan_proposals"
down_revision: Union[str, Sequence[str], None] = "0021_provider_routing_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_proposals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("source_trace_id", sa.String(length=36), nullable=True),
        sa.Column("parent_proposal_id", sa.String(length=36), nullable=True),
        sa.Column("current_plan_id", sa.String(length=36), nullable=False),
        sa.Column("current_plan_version", sa.Integer(), nullable=False),
        sa.Column("current_world_revision", sa.Integer(), nullable=False),
        sa.Column("applied_plan_id", sa.String(length=36), nullable=True),
        sa.Column("trigger", sa.String(length=120), nullable=False),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("deviation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("deduplication_key", sa.String(length=180), nullable=False),
        sa.Column("trajectory_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("deviation_json", sa.JSON(), nullable=False),
        sa.Column("candidate_plan_json", sa.JSON(), nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("expected_effects_json", sa.JSON(), nullable=False),
        sa.Column("tradeoffs_json", sa.JSON(), nullable=False),
        sa.Column("confidence_json", sa.JSON(), nullable=False),
        sa.Column("modification_json", sa.JSON(), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("attention_action", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("planner_version", sa.String(length=80), nullable=False),
        sa.Column("calculation_version", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("authority_level >= 0 AND authority_level <= 4", name="ck_plan_proposals_authority_level"),
        sa.CheckConstraint("current_plan_version >= 1", name="ck_plan_proposals_current_plan_version"),
        sa.CheckConstraint("current_world_revision >= 0", name="ck_plan_proposals_world_revision"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PRESENTED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'EXPIRED', 'APPLY_FAILED')",
            name="ck_plan_proposals_status",
        ),
        sa.ForeignKeyConstraint(["applied_plan_id"], ["plans.id"], name="fk_plan_proposals_applied_plan_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_plan_id"], ["plans.id"], name="fk_plan_proposals_current_plan_id"),
        sa.ForeignKeyConstraint(["exam_id"], ["learning_exams.id"], name="fk_plan_proposals_exam_id"),
        sa.ForeignKeyConstraint(["parent_proposal_id"], ["plan_proposals.id"], name="fk_plan_proposals_parent_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_trace_id"], ["cognitive_traces.id"], name="fk_plan_proposals_source_trace_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_plan_proposals_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "deduplication_key", name="uq_plan_proposals_user_deduplication"),
    )
    for column in (
        "user_id", "exam_id", "source_trace_id", "parent_proposal_id", "current_plan_id", "applied_plan_id",
        "trigger", "deviation_fingerprint", "status", "expires_at", "rejection_cooldown_until",
    ):
        op.create_index(f"ix_plan_proposals_{column}", "plan_proposals", [column])
    op.create_index("ix_plan_proposals_user_status_created", "plan_proposals", ["user_id", "status", "created_at"])
    op.create_index("ix_plan_proposals_exam_status", "plan_proposals", ["exam_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_plan_proposals_exam_status", table_name="plan_proposals")
    op.drop_index("ix_plan_proposals_user_status_created", table_name="plan_proposals")
    for column in reversed((
        "user_id", "exam_id", "source_trace_id", "parent_proposal_id", "current_plan_id", "applied_plan_id",
        "trigger", "deviation_fingerprint", "status", "expires_at", "rejection_cooldown_until",
    )):
        op.drop_index(f"ix_plan_proposals_{column}", table_name="plan_proposals")
    op.drop_table("plan_proposals")
