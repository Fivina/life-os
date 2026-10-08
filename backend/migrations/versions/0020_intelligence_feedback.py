"""Add v1.6C explicit intelligence feedback evidence.

Revision ID: 0020_intelligence_feedback
Revises: 0019_workspace_attention_threads
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_intelligence_feedback"
down_revision: Union[str, Sequence[str], None] = "0019_workspace_attention_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_conversation_id", sa.String(length=36), nullable=True),
        sa.Column("parent_workspace_id", sa.String(length=36), nullable=True),
        sa.Column("parent_workspace_type", sa.String(length=40), nullable=True),
        sa.Column("target_cognitive_trace_id", sa.String(length=36), nullable=False),
        sa.Column("target_decision_audit_id", sa.String(length=36), nullable=True),
        sa.Column("target_assistant_message_id", sa.String(length=36), nullable=True),
        sa.Column("frozen_world_revision", sa.Integer(), nullable=False),
        sa.Column("frozen_context_json", sa.JSON(), nullable=False),
        sa.Column("initial_user_explanation", sa.Text(), nullable=True),
        sa.Column("current_question_index", sa.Integer(), nullable=False),
        sa.Column("questions_planned_count", sa.Integer(), nullable=False),
        sa.Column("questions_answered_count", sa.Integer(), nullable=False),
        sa.Column("clarification_used", sa.Boolean(), nullable=False),
        sa.Column("clarification_question_json", sa.JSON(), nullable=False),
        sa.Column("clarification_answer", sa.Text(), nullable=True),
        sa.Column("planned_questions_json", sa.JSON(), nullable=False),
        sa.Column("feedback_summary_json", sa.JSON(), nullable=False),
        sa.Column("resume_state_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("current_question_index >= 0", name="ck_feedback_sessions_question_index"),
        sa.CheckConstraint(
            "questions_planned_count >= 0 AND questions_planned_count <= 4",
            name="ck_feedback_sessions_question_count",
        ),
        sa.CheckConstraint(
            "questions_answered_count >= 0 AND questions_answered_count <= questions_planned_count",
            name="ck_feedback_sessions_answer_count",
        ),
        sa.ForeignKeyConstraint(
            ["parent_conversation_id"], ["conversation_threads.id"],
            name="fk_feedback_sessions_parent_conversation_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_workspace_id"], ["active_workspaces.id"],
            name="fk_feedback_sessions_parent_workspace_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_assistant_message_id"], ["conversation_messages.id"],
            name="fk_feedback_sessions_target_assistant_message_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_cognitive_trace_id"], ["cognitive_traces.id"],
            name="fk_feedback_sessions_target_cognitive_trace_id",
        ),
        sa.ForeignKeyConstraint(
            ["target_decision_audit_id"], ["decision_audits.id"],
            name="fk_feedback_sessions_target_decision_audit_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_feedback_sessions_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "status", "completed_at", "cancelled_at", "expired_at", "parent_conversation_id",
        "parent_workspace_id", "parent_workspace_type", "target_cognitive_trace_id",
        "target_decision_audit_id", "target_assistant_message_id", "frozen_world_revision",
    ):
        op.create_index(f"ix_feedback_sessions_{column}", "feedback_sessions", [column])
    op.create_index(
        "uq_feedback_sessions_user_conversation_active",
        "feedback_sessions",
        ["user_id", "parent_conversation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_feedback_sessions_user_status_created",
        "feedback_sessions",
        ["user_id", "status", "created_at"],
    )

    op.create_table(
        "feedback_responses",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_session_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=160), nullable=False),
        sa.Column("question_version", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(length=60), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("is_skipped", sa.Boolean(), nullable=False),
        sa.Column("feedback_scope", sa.String(length=60), nullable=False),
        sa.Column("feedback_confidence", sa.String(length=20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("question_version >= 1", name="ck_feedback_responses_question_version"),
        sa.CheckConstraint(
            "(is_skipped = true AND score IS NULL) OR (is_skipped = false AND score BETWEEN 0 AND 5)",
            name="ck_feedback_responses_score_skip",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_session_id"], ["feedback_sessions.id"],
            name="fk_feedback_responses_feedback_session_id",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_feedback_responses_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feedback_session_id", "question_id", "question_version",
            name="uq_feedback_responses_session_question",
        ),
    )
    for column in (
        "user_id", "feedback_session_id", "question_id", "question_version", "dimension", "score",
        "is_skipped", "feedback_scope", "feedback_confidence",
    ):
        op.create_index(f"ix_feedback_responses_{column}", "feedback_responses", [column])
    op.create_index(
        "ix_feedback_responses_dimension_score", "feedback_responses", ["dimension", "score"]
    )

    op.create_table(
        "decision_training_examples",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cognitive_trace_id", sa.String(length=36), nullable=False),
        sa.Column("decision_audit_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_session_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_response_id", sa.String(length=36), nullable=False),
        sa.Column("decision_family", sa.String(length=80), nullable=False),
        sa.Column("question_id", sa.String(length=160), nullable=False),
        sa.Column("question_version", sa.Integer(), nullable=False),
        sa.Column("cognitive_event_ref", sa.String(length=160), nullable=False),
        sa.Column("conversation_thread_id", sa.String(length=36), nullable=True),
        sa.Column("active_workspace_type", sa.String(length=40), nullable=True),
        sa.Column("workspace_phase", sa.String(length=80), nullable=True),
        sa.Column("candidate_action", sa.String(length=120), nullable=True),
        sa.Column("urgency", sa.Float(), nullable=True),
        sa.Column("reversible", sa.Boolean(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("model_answer_json", sa.JSON(), nullable=False),
        sa.Column("model_confidence", sa.Float(), nullable=True),
        sa.Column("probabilities_json", sa.JSON(), nullable=False),
        sa.Column("executive_result", sa.String(length=80), nullable=True),
        sa.Column("feedback_dimension", sa.String(length=60), nullable=False),
        sa.Column("feedback_score", sa.Integer(), nullable=False),
        sa.Column("feedback_scope", sa.String(length=60), nullable=False),
        sa.Column("feedback_confidence", sa.String(length=20), nullable=False),
        sa.Column("explicit_feedback_json", sa.JSON(), nullable=False),
        sa.Column("label_json", sa.JSON(), nullable=False),
        sa.Column("label_strength", sa.String(length=20), nullable=False),
        sa.Column("label_source", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=160), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("question_version >= 1", name="ck_decision_training_examples_question_version"),
        sa.CheckConstraint(
            "feedback_score BETWEEN 0 AND 5", name="ck_decision_training_examples_feedback_score"
        ),
        sa.CheckConstraint(
            "model_confidence IS NULL OR (model_confidence >= 0 AND model_confidence <= 1)",
            name="ck_decision_training_examples_model_confidence",
        ),
        sa.CheckConstraint(
            "urgency IS NULL OR (urgency >= 0 AND urgency <= 1)",
            name="ck_decision_training_examples_urgency",
        ),
        sa.ForeignKeyConstraint(
            ["cognitive_trace_id"], ["cognitive_traces.id"],
            name="fk_decision_training_examples_cognitive_trace_id",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_thread_id"], ["conversation_threads.id"],
            name="fk_decision_training_examples_conversation_thread_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decision_audit_id"], ["decision_audits.id"],
            name="fk_decision_training_examples_decision_audit_id",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_response_id"], ["feedback_responses.id"],
            name="fk_decision_training_examples_feedback_response_id",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_session_id"], ["feedback_sessions.id"],
            name="fk_decision_training_examples_feedback_session_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_profiles.id"], name="fk_decision_training_examples_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feedback_response_id", name="uq_decision_training_examples_feedback_response_id"),
    )
    for column in (
        "user_id", "cognitive_trace_id", "decision_audit_id", "feedback_session_id", "feedback_response_id",
        "decision_family", "question_id", "question_version", "cognitive_event_ref", "conversation_thread_id",
        "active_workspace_type", "workspace_phase", "candidate_action", "executive_result", "feedback_dimension",
        "feedback_score", "feedback_scope", "feedback_confidence", "label_strength", "label_source", "provider",
        "model_version", "policy_version",
    ):
        op.create_index(f"ix_decision_training_examples_{column}", "decision_training_examples", [column])
    op.create_index(
        "ix_decision_training_examples_family_provider_policy",
        "decision_training_examples",
        ["decision_family", "provider", "model_version", "policy_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_training_examples_family_provider_policy", table_name="decision_training_examples")
    for column in reversed((
        "user_id", "cognitive_trace_id", "decision_audit_id", "feedback_session_id", "feedback_response_id",
        "decision_family", "question_id", "question_version", "cognitive_event_ref", "conversation_thread_id",
        "active_workspace_type", "workspace_phase", "candidate_action", "executive_result", "feedback_dimension",
        "feedback_score", "feedback_scope", "feedback_confidence", "label_strength", "label_source", "provider",
        "model_version", "policy_version",
    )):
        op.drop_index(f"ix_decision_training_examples_{column}", table_name="decision_training_examples")
    op.drop_table("decision_training_examples")

    op.drop_index("ix_feedback_responses_dimension_score", table_name="feedback_responses")
    for column in reversed((
        "user_id", "feedback_session_id", "question_id", "question_version", "dimension", "score",
        "is_skipped", "feedback_scope", "feedback_confidence",
    )):
        op.drop_index(f"ix_feedback_responses_{column}", table_name="feedback_responses")
    op.drop_table("feedback_responses")

    op.drop_index("ix_feedback_sessions_user_status_created", table_name="feedback_sessions")
    op.drop_index("uq_feedback_sessions_user_conversation_active", table_name="feedback_sessions")
    for column in reversed((
        "user_id", "status", "completed_at", "cancelled_at", "expired_at", "parent_conversation_id",
        "parent_workspace_id", "parent_workspace_type", "target_cognitive_trace_id",
        "target_decision_audit_id", "target_assistant_message_id", "frozen_world_revision",
    )):
        op.drop_index(f"ix_feedback_sessions_{column}", table_name="feedback_sessions")
    op.drop_table("feedback_sessions")
