"""Add v1.6A decision trace and audit persistence.

Revision ID: 0018_decision_infrastructure
Revises: 0017_repository_integrity
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018_decision_infrastructure"
down_revision: Union[str, Sequence[str], None] = "0017_repository_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cognitive_traces",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cognitive_event_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_source", sa.String(length=80), nullable=False),
        sa.Column("source_event_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_thread_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_ref", sa.String(length=160), nullable=True),
        sa.Column("world_revision", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=160), nullable=True),
        sa.Column("causation_id", sa.String(length=160), nullable=True),
        sa.Column("question_id", sa.String(length=160), nullable=False),
        sa.Column("question_version", sa.Integer(), nullable=False),
        sa.Column("question_family", sa.String(length=80), nullable=False),
        sa.Column("output_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_version", sa.String(length=80), nullable=True),
        sa.Column("model_version", sa.String(length=160), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("skill_name", sa.String(length=120), nullable=True),
        sa.Column("skill_version", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_eur", sa.Float(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("context_refs_json", sa.JSON(), nullable=False),
        sa.Column("memory_refs_json", sa.JSON(), nullable=False),
        sa.Column("pattern_refs_json", sa.JSON(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("probabilities_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("planner_ref", sa.String(length=160), nullable=True),
        sa.Column("proposal_ref", sa.String(length=160), nullable=True),
        sa.Column("tool_call_refs_json", sa.JSON(), nullable=False),
        sa.Column("state_change_refs_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_thread_id"], ["conversation_threads.id"], name="fk_cognitive_traces_conversation_thread_id"),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"], name="fk_cognitive_traces_source_event_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_cognitive_traces_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "cognitive_event_id", "event_type", "event_source", "source_event_id",
        "conversation_thread_id", "workspace_ref", "world_revision", "correlation_id", "causation_id",
        "question_id", "question_family", "status", "provider", "model_version", "policy_version",
        "skill_name", "completed_at", "planner_ref", "proposal_ref", "error_code",
    ):
        op.create_index(f"ix_cognitive_traces_{column}", "cognitive_traces", [column])

    op.create_table(
        "decision_audits",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("audit_type", sa.String(length=80), nullable=False),
        sa.Column("downstream_action_ref", sa.String(length=160), nullable=True),
        sa.Column("outcome_json", sa.JSON(), nullable=False),
        sa.Column("correction_json", sa.JSON(), nullable=False),
        sa.Column("override_json", sa.JSON(), nullable=False),
        sa.Column("feedback_ref", sa.String(length=160), nullable=True),
        sa.Column("training_eligible", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["trace_id"], ["cognitive_traces.id"], name="fk_decision_audits_trace_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_decision_audits_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "trace_id", "audit_type", "downstream_action_ref", "feedback_ref", "training_eligible",
    ):
        op.create_index(f"ix_decision_audits_{column}", "decision_audits", [column])


def downgrade() -> None:
    for column in (
        "training_eligible", "feedback_ref", "downstream_action_ref", "audit_type", "trace_id", "user_id",
    ):
        op.drop_index(f"ix_decision_audits_{column}", table_name="decision_audits")
    op.drop_table("decision_audits")

    for column in (
        "error_code", "proposal_ref", "planner_ref", "completed_at", "skill_name", "policy_version",
        "model_version", "provider", "status", "question_family", "question_id", "causation_id",
        "correlation_id", "world_revision", "workspace_ref", "conversation_thread_id", "source_event_id",
        "event_source", "event_type", "cognitive_event_id", "user_id",
    ):
        op.drop_index(f"ix_cognitive_traces_{column}", table_name="cognitive_traces")
    op.drop_table("cognitive_traces")
