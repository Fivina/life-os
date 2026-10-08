"""learning exam trajectories v0.6

Revision ID: 0006_learning_domain
Revises: 0005_fitness_domain
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_learning_domain"
down_revision = "0005_fitness_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_courses", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("learning_courses", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column("learning_courses", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE learning_courses SET name = COALESCE(title, 'Course') WHERE name IS NULL")
    op.alter_column("learning_courses", "name", nullable=False)
    op.alter_column("learning_courses", "title", nullable=True)

    op.add_column("learning_exams", sa.Column("exam_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("learning_exams", sa.Column("target_preparation_minutes", sa.Integer(), nullable=True))
    op.add_column("learning_exams", sa.Column("minimum_required_preparation_minutes", sa.Integer(), nullable=True))
    op.add_column("learning_exams", sa.Column("target_quality_adjusted_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "learning_exams",
        sa.Column("strategy_version", sa.String(length=80), nullable=False, server_default="learning-trajectory-v1"),
    )
    op.add_column("learning_exams", sa.Column("exam_format", sa.String(length=120), nullable=True))
    op.add_column("learning_exams", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("learning_exams", sa.Column("notes", sa.Text(), nullable=True))
    op.execute(
        "UPDATE learning_exams SET target_preparation_minutes = "
        "GREATEST(1, ROUND(COALESCE(estimated_required_hours, 0) * 60)) "
        "WHERE target_preparation_minutes IS NULL"
    )
    op.alter_column("learning_exams", "target_preparation_minutes", nullable=False, server_default="60")
    op.create_index("ix_learning_exams_course_id", "learning_exams", ["course_id"])
    op.create_index("ix_learning_exams_exam_at", "learning_exams", ["exam_at"])

    op.add_column("learning_study_requirements", sa.Column("estimated_required_minutes", sa.Integer(), nullable=True))
    op.add_column("learning_study_requirements", sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_study_requirements", sa.Column("importance_weight", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("learning_study_requirements", sa.Column("prerequisite_topic_id", sa.String(length=36), nullable=True))
    op.add_column("learning_study_requirements", sa.Column("completed_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        "UPDATE learning_study_requirements SET estimated_required_minutes = "
        "ROUND(COALESCE(estimated_hours, 0) * 60) WHERE estimated_required_minutes IS NULL"
    )
    op.create_foreign_key(
        "fk_learning_study_requirements_prerequisite",
        "learning_study_requirements",
        "learning_study_requirements",
        ["prerequisite_topic_id"],
        ["id"],
    )
    op.create_index("ix_learning_study_requirements_status", "learning_study_requirements", ["status"])

    op.add_column("learning_study_sessions", sa.Column("course_id", sa.String(length=36), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("topic_id", sa.String(length=36), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("source_action_id", sa.String(length=36), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("source_plan_block_id", sa.String(length=36), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("quality_rating", sa.Integer(), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("focus_quality", sa.Integer(), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("comprehension_quality", sa.Integer(), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("quality_multiplier", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("learning_study_sessions", sa.Column("quality_adjusted_minutes", sa.Integer(), nullable=True))
    op.add_column("learning_study_sessions", sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"))
    op.add_column("learning_study_sessions", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.execute("UPDATE learning_study_sessions SET occurred_at = COALESCE(ended_at, started_at) WHERE occurred_at IS NULL")
    op.execute("UPDATE learning_study_sessions SET completed_at = ended_at WHERE completed_at IS NULL")
    op.execute("UPDATE learning_study_sessions SET duration_minutes = minutes WHERE duration_minutes IS NULL")
    op.execute("UPDATE learning_study_sessions SET quality_adjusted_minutes = minutes WHERE quality_adjusted_minutes IS NULL")
    op.alter_column("learning_study_sessions", "occurred_at", nullable=False)
    op.alter_column("learning_study_sessions", "duration_minutes", nullable=False, server_default="0")
    op.alter_column("learning_study_sessions", "quality_adjusted_minutes", nullable=False, server_default="0")
    op.create_foreign_key("fk_learning_study_sessions_course_id", "learning_study_sessions", "learning_courses", ["course_id"], ["id"])
    op.create_foreign_key("fk_learning_study_sessions_topic_id", "learning_study_sessions", "learning_study_requirements", ["topic_id"], ["id"])
    op.create_foreign_key("fk_learning_study_sessions_source_action_id", "learning_study_sessions", "actions", ["source_action_id"], ["id"])
    op.create_foreign_key("fk_learning_study_sessions_source_plan_block_id", "learning_study_sessions", "plan_blocks", ["source_plan_block_id"], ["id"])
    op.create_index("ix_learning_study_sessions_course_id", "learning_study_sessions", ["course_id"])
    op.create_index("ix_learning_study_sessions_exam_id", "learning_study_sessions", ["exam_id"])
    op.create_index("ix_learning_study_sessions_topic_id", "learning_study_sessions", ["topic_id"])
    op.create_index("ix_learning_study_sessions_occurred_at", "learning_study_sessions", ["occurred_at"])
    op.create_index("ix_learning_study_sessions_idempotency_key", "learning_study_sessions", ["idempotency_key"])
    op.create_unique_constraint("uq_learning_session_user_idempotency", "learning_study_sessions", ["user_id", "idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_learning_session_user_idempotency", "learning_study_sessions", type_="unique")
    op.drop_index("ix_learning_study_sessions_idempotency_key", table_name="learning_study_sessions")
    op.drop_index("ix_learning_study_sessions_occurred_at", table_name="learning_study_sessions")
    op.drop_index("ix_learning_study_sessions_topic_id", table_name="learning_study_sessions")
    op.drop_index("ix_learning_study_sessions_exam_id", table_name="learning_study_sessions")
    op.drop_index("ix_learning_study_sessions_course_id", table_name="learning_study_sessions")
    op.drop_constraint("fk_learning_study_sessions_source_plan_block_id", "learning_study_sessions", type_="foreignkey")
    op.drop_constraint("fk_learning_study_sessions_source_action_id", "learning_study_sessions", type_="foreignkey")
    op.drop_constraint("fk_learning_study_sessions_topic_id", "learning_study_sessions", type_="foreignkey")
    op.drop_constraint("fk_learning_study_sessions_course_id", "learning_study_sessions", type_="foreignkey")
    for column in [
        "idempotency_key",
        "source",
        "quality_adjusted_minutes",
        "quality_multiplier",
        "comprehension_quality",
        "focus_quality",
        "quality_rating",
        "duration_minutes",
        "completed_at",
        "occurred_at",
        "source_plan_block_id",
        "source_action_id",
        "topic_id",
        "course_id",
    ]:
        op.drop_column("learning_study_sessions", column)

    op.drop_index("ix_learning_study_requirements_status", table_name="learning_study_requirements")
    op.drop_constraint("fk_learning_study_requirements_prerequisite", "learning_study_requirements", type_="foreignkey")
    for column in ["completed_minutes", "prerequisite_topic_id", "importance_weight", "order_index", "estimated_required_minutes"]:
        op.drop_column("learning_study_requirements", column)

    op.drop_index("ix_learning_exams_exam_at", table_name="learning_exams")
    op.drop_index("ix_learning_exams_course_id", table_name="learning_exams")
    for column in [
        "notes",
        "location",
        "exam_format",
        "strategy_version",
        "target_quality_adjusted_minutes",
        "minimum_required_preparation_minutes",
        "target_preparation_minutes",
        "exam_at",
    ]:
        op.drop_column("learning_exams", column)

    op.alter_column("learning_courses", "title", nullable=False)
    for column in ["description", "code", "name"]:
        op.drop_column("learning_courses", column)
