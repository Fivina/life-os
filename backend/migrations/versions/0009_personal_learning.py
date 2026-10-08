"""personal learning v0.9

Revision ID: 0009_personal_learning
Revises: 0008_kitchen
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_personal_learning"
down_revision = "0008_kitchen"
branch_labels = None
depends_on = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]


def _timestamp_columns_without_version() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("plans", sa.Column("personal_model_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("plans", sa.Column("personal_model_revision", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "personal_training_examples",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False),
        sa.Column("extraction_version", sa.String(length=80), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("plan_block_id", sa.String(length=36), nullable=True),
        sa.Column("source_action_id", sa.String(length=36), nullable=True),
        sa.Column("source_entity_type", sa.String(length=80), nullable=True),
        sa.Column("source_entity_id", sa.String(length=36), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=True),
        sa.Column("label_source", sa.String(length=120), nullable=False, server_default="plan_block"),
        sa.Column("feature_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("label_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("provenance_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["plan_block_id"], ["plan_blocks.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["source_action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "feature_schema_version", "plan_block_id", name="uq_training_example_user_schema_block"),
    )
    op.create_index("ix_personal_training_examples_user_id", "personal_training_examples", ["user_id"])
    op.create_index("ix_personal_training_examples_feature_schema_version", "personal_training_examples", ["feature_schema_version"])
    op.create_index("ix_personal_training_examples_decision_at", "personal_training_examples", ["decision_at"])
    op.create_index("ix_personal_training_examples_plan_id", "personal_training_examples", ["plan_id"])
    op.create_index("ix_personal_training_examples_plan_block_id", "personal_training_examples", ["plan_block_id"])
    op.create_index("ix_personal_training_examples_source_action_id", "personal_training_examples", ["source_action_id"])
    op.create_index("ix_personal_training_examples_source_entity_id", "personal_training_examples", ["source_entity_id"])
    op.create_index("ix_personal_training_examples_domain", "personal_training_examples", ["domain"])
    op.create_index("ix_personal_training_examples_status", "personal_training_examples", ["status"])

    op.create_table(
        "personal_model_versions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("model_type", sa.String(length=80), nullable=False),
        sa.Column("model_stage", sa.String(length=40), nullable=False, server_default="STAGE_1"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="CANDIDATE"),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evidence_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_evidence_n", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("baseline_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("promotion_reason", sa.Text(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_model_version_id", sa.String(length=36), nullable=True),
        sa.Column("refresh_run_id", sa.String(length=36), nullable=True),
        *_timestamp_columns_without_version(),
        sa.ForeignKeyConstraint(["supersedes_model_version_id"], ["personal_model_versions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "model_type", "version", name="uq_personal_model_user_type_version"),
    )
    op.create_index("ix_personal_model_versions_user_id", "personal_model_versions", ["user_id"])
    op.create_index("ix_personal_model_versions_model_type", "personal_model_versions", ["model_type"])
    op.create_index("ix_personal_model_versions_feature_schema_version", "personal_model_versions", ["feature_schema_version"])
    op.create_index("ix_personal_model_versions_status", "personal_model_versions", ["status"])
    op.create_index("ix_personal_model_versions_supersedes_model_version_id", "personal_model_versions", ["supersedes_model_version_id"])
    op.create_index("ix_personal_model_versions_refresh_run_id", "personal_model_versions", ["refresh_run_id"])

    op.create_table(
        "personal_pattern_evidence",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("pattern_type", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence_n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weighted_support", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("first_observed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="ACTIVE"),
        sa.Column("correction_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_model_version_id", sa.String(length=36), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["source_model_version_id"], ["personal_model_versions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_pattern_evidence_user_id", "personal_pattern_evidence", ["user_id"])
    op.create_index("ix_personal_pattern_evidence_pattern_type", "personal_pattern_evidence", ["pattern_type"])
    op.create_index("ix_personal_pattern_evidence_status", "personal_pattern_evidence", ["status"])
    op.create_index("ix_personal_pattern_evidence_source_model_version_id", "personal_pattern_evidence", ["source_model_version_id"])

    op.create_table(
        "personal_model_refresh_runs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False, server_default="personal-features-v1"),
        sa.Column("extraction_version", sa.String(length=80), nullable=False, server_default="personal-extractor-v1"),
        sa.Column("evidence_n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_model_refresh_runs_user_id", "personal_model_refresh_runs", ["user_id"])
    op.create_index("ix_personal_model_refresh_runs_status", "personal_model_refresh_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_personal_model_refresh_runs_status", table_name="personal_model_refresh_runs")
    op.drop_index("ix_personal_model_refresh_runs_user_id", table_name="personal_model_refresh_runs")
    op.drop_table("personal_model_refresh_runs")

    op.drop_index("ix_personal_pattern_evidence_source_model_version_id", table_name="personal_pattern_evidence")
    op.drop_index("ix_personal_pattern_evidence_status", table_name="personal_pattern_evidence")
    op.drop_index("ix_personal_pattern_evidence_pattern_type", table_name="personal_pattern_evidence")
    op.drop_index("ix_personal_pattern_evidence_user_id", table_name="personal_pattern_evidence")
    op.drop_table("personal_pattern_evidence")

    op.drop_index("ix_personal_model_versions_refresh_run_id", table_name="personal_model_versions")
    op.drop_index("ix_personal_model_versions_supersedes_model_version_id", table_name="personal_model_versions")
    op.drop_index("ix_personal_model_versions_status", table_name="personal_model_versions")
    op.drop_index("ix_personal_model_versions_feature_schema_version", table_name="personal_model_versions")
    op.drop_index("ix_personal_model_versions_model_type", table_name="personal_model_versions")
    op.drop_index("ix_personal_model_versions_user_id", table_name="personal_model_versions")
    op.drop_table("personal_model_versions")

    op.drop_index("ix_personal_training_examples_status", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_domain", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_source_entity_id", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_source_action_id", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_plan_block_id", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_plan_id", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_decision_at", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_feature_schema_version", table_name="personal_training_examples")
    op.drop_index("ix_personal_training_examples_user_id", table_name="personal_training_examples")
    op.drop_table("personal_training_examples")

    op.drop_column("plans", "personal_model_revision")
    op.drop_column("plans", "personal_model_snapshot")
