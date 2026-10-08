"""Add v1.6D provider routing evidence.

Revision ID: 0021_provider_routing_evidence
Revises: 0020_intelligence_feedback
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0021_provider_routing_evidence"
down_revision: Union[str, Sequence[str], None] = "0020_intelligence_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "decision_provider_usage",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cognitive_trace_id", sa.String(length=36), nullable=True),
        sa.Column("cognitive_event_id", sa.String(length=160), nullable=False),
        sa.Column("question_id", sa.String(length=160), nullable=False),
        sa.Column("question_version", sa.Integer(), nullable=False),
        sa.Column("question_family", sa.String(length=80), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=160), nullable=True),
        sa.Column("provider_role", sa.String(length=20), nullable=False),
        sa.Column("routing_policy_version", sa.String(length=80), nullable=False),
        sa.Column("routing_reason", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_units", sa.Integer(), nullable=False),
        sa.Column("output_units", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_eur", sa.Float(), nullable=True),
        sa.Column("request_id", sa.String(length=160), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("question_version >= 1", name="ck_decision_provider_usage_question_version"),
        sa.CheckConstraint("question_count >= 1", name="ck_decision_provider_usage_question_count"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_decision_provider_usage_latency"),
        sa.CheckConstraint("input_units >= 0 AND output_units >= 0", name="ck_decision_provider_usage_units"),
        sa.CheckConstraint(
            "estimated_cost_eur IS NULL OR estimated_cost_eur >= 0",
            name="ck_decision_provider_usage_cost",
        ),
        sa.ForeignKeyConstraint(
            ["cognitive_trace_id"], ["cognitive_traces.id"],
            name="fk_decision_provider_usage_trace_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_profiles.id"], name="fk_decision_provider_usage_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "cognitive_trace_id", "cognitive_event_id", "question_id", "question_family",
        "provider", "model_version", "provider_role", "routing_policy_version", "routing_reason",
        "status", "request_id", "error_code",
    ):
        op.create_index(f"ix_decision_provider_usage_{column}", "decision_provider_usage", [column])
    op.create_index(
        "ix_decision_provider_usage_provider_family_created",
        "decision_provider_usage", ["provider", "question_family", "created_at"],
    )

    op.create_table(
        "decision_disagreements",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cognitive_trace_id", sa.String(length=36), nullable=True),
        sa.Column("cognitive_event_id", sa.String(length=160), nullable=False),
        sa.Column("question_id", sa.String(length=160), nullable=False),
        sa.Column("question_version", sa.Integer(), nullable=False),
        sa.Column("question_family", sa.String(length=80), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("decision_audit_id", sa.String(length=36), nullable=True),
        sa.Column("comparison_role", sa.String(length=20), nullable=False),
        sa.Column("disagreement_type", sa.String(length=80), nullable=False),
        sa.Column("primary_provider", sa.String(length=80), nullable=False),
        sa.Column("primary_model_version", sa.String(length=160), nullable=True),
        sa.Column("primary_answer_json", sa.JSON(), nullable=False),
        sa.Column("primary_probabilities_json", sa.JSON(), nullable=False),
        sa.Column("primary_confidence", sa.Float(), nullable=True),
        sa.Column("comparison_provider", sa.String(length=80), nullable=False),
        sa.Column("comparison_model_version", sa.String(length=160), nullable=True),
        sa.Column("comparison_answer_json", sa.JSON(), nullable=False),
        sa.Column("comparison_probabilities_json", sa.JSON(), nullable=False),
        sa.Column("comparison_confidence", sa.Float(), nullable=True),
        sa.Column("operational_provider", sa.String(length=80), nullable=False),
        sa.Column("operational_answer_json", sa.JSON(), nullable=False),
        sa.Column("routing_policy_version", sa.String(length=80), nullable=False),
        sa.Column("training_eligible", sa.Boolean(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("question_version >= 1", name="ck_decision_disagreements_question_version"),
        sa.CheckConstraint(
            "primary_confidence IS NULL OR (primary_confidence >= 0 AND primary_confidence <= 1)",
            name="ck_decision_disagreements_primary_confidence",
        ),
        sa.CheckConstraint(
            "comparison_confidence IS NULL OR (comparison_confidence >= 0 AND comparison_confidence <= 1)",
            name="ck_decision_disagreements_comparison_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["decision_audit_id"], ["decision_audits.id"],
            name="fk_decision_disagreements_decision_audit_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cognitive_trace_id"], ["cognitive_traces.id"],
            name="fk_decision_disagreements_trace_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_profiles.id"], name="fk_decision_disagreements_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "user_id", "cognitive_trace_id", "cognitive_event_id", "question_id", "question_family",
        "context_hash", "decision_audit_id",
        "comparison_role", "disagreement_type", "primary_provider", "primary_model_version",
        "comparison_provider", "comparison_model_version", "operational_provider",
        "routing_policy_version", "training_eligible", "review_status",
    ):
        op.create_index(f"ix_decision_disagreements_{column}", "decision_disagreements", [column])
    op.create_index(
        "ix_decision_disagreements_family_type_created",
        "decision_disagreements", ["question_family", "disagreement_type", "created_at"],
    )

    with op.batch_alter_table("decision_training_examples") as batch_op:
        batch_op.add_column(sa.Column("decision_disagreement_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_decision_training_examples_decision_disagreement_id",
            "decision_disagreements",
            ["decision_disagreement_id"], ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_decision_training_examples_decision_disagreement_id",
            ["decision_disagreement_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("decision_training_examples") as batch_op:
        batch_op.drop_index("ix_decision_training_examples_decision_disagreement_id")
        batch_op.drop_constraint(
            "fk_decision_training_examples_decision_disagreement_id", type_="foreignkey"
        )
        batch_op.drop_column("decision_disagreement_id")

    op.drop_index("ix_decision_disagreements_family_type_created", table_name="decision_disagreements")
    for column in reversed((
        "user_id", "cognitive_trace_id", "cognitive_event_id", "question_id", "question_family",
        "context_hash", "decision_audit_id",
        "comparison_role", "disagreement_type", "primary_provider", "primary_model_version",
        "comparison_provider", "comparison_model_version", "operational_provider",
        "routing_policy_version", "training_eligible", "review_status",
    )):
        op.drop_index(f"ix_decision_disagreements_{column}", table_name="decision_disagreements")
    op.drop_table("decision_disagreements")

    op.drop_index("ix_decision_provider_usage_provider_family_created", table_name="decision_provider_usage")
    for column in reversed((
        "user_id", "cognitive_trace_id", "cognitive_event_id", "question_id", "question_family",
        "provider", "model_version", "provider_role", "routing_policy_version", "routing_reason",
        "status", "request_id", "error_code",
    )):
        op.drop_index(f"ix_decision_provider_usage_{column}", table_name="decision_provider_usage")
    op.drop_table("decision_provider_usage")
