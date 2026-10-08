"""fitness specialist domain v0.5

Revision ID: 0005_fitness_domain
Revises: 0004_daily_control_loop
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_fitness_domain"
down_revision = "0004_daily_control_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fitness_body_measurements", sa.Column("muscle_mass_kg", sa.Float(), nullable=True))
    op.add_column("fitness_body_measurements", sa.Column("body_water_percentage", sa.Float(), nullable=True))
    op.add_column("fitness_body_measurements", sa.Column("visceral_fat_rating", sa.Float(), nullable=True))
    op.add_column("fitness_body_measurements", sa.Column("bmi", sa.Float(), nullable=True))
    op.add_column("fitness_body_measurements", sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    op.add_column("fitness_exercises", sa.Column("primary_muscle_group", sa.String(length=80), nullable=True))
    op.add_column("fitness_exercises", sa.Column("equipment", sa.String(length=80), nullable=True))
    op.add_column("fitness_exercises", sa.Column("default_rest_seconds", sa.Integer(), nullable=False, server_default="120"))
    op.add_column("fitness_exercises", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("fitness_exercises", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_fitness_exercises_active", "fitness_exercises", ["active"])

    op.create_table(
        "fitness_workout_programs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal_type", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_workout_programs_user_id", "fitness_workout_programs", ["user_id"])
    op.create_index("ix_fitness_workout_programs_status", "fitness_workout_programs", ["status"])
    op.create_index("ix_fitness_workout_programs_active", "fitness_workout_programs", ["active"])

    op.create_table(
        "fitness_workout_templates",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("program_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["program_id"], ["fitness_workout_programs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_workout_templates_user_id", "fitness_workout_templates", ["user_id"])
    op.create_index("ix_fitness_workout_templates_program_id", "fitness_workout_templates", ["program_id"])
    op.create_index("ix_fitness_workout_templates_active", "fitness_workout_templates", ["active"])

    op.create_table(
        "fitness_workout_template_exercises",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("exercise_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_sets", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("target_rep_min", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("target_rep_max", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("target_load_kg", sa.Float(), nullable=True),
        sa.Column("target_rpe", sa.Float(), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("progression_rule", sa.String(length=80), nullable=False, server_default="double_progression"),
        sa.Column("load_increment_kg", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["exercise_id"], ["fitness_exercises.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["fitness_workout_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_workout_template_exercises_user_id", "fitness_workout_template_exercises", ["user_id"])
    op.create_index("ix_fitness_workout_template_exercises_template_id", "fitness_workout_template_exercises", ["template_id"])
    op.create_index("ix_fitness_workout_template_exercises_exercise_id", "fitness_workout_template_exercises", ["exercise_id"])

    op.create_table(
        "fitness_workout_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("workout_template_id", sa.String(length=36), nullable=True),
        sa.Column("source_action_id", sa.String(length=36), nullable=True),
        sa.Column("source_plan_block_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="in_progress"),
        sa.Column("perceived_session_difficulty", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("runtime_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["source_action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["source_plan_block_id"], ["plan_blocks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.ForeignKeyConstraint(["workout_template_id"], ["fitness_workout_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_workout_sessions_user_id", "fitness_workout_sessions", ["user_id"])
    op.create_index("ix_fitness_workout_sessions_workout_template_id", "fitness_workout_sessions", ["workout_template_id"])
    op.create_index("ix_fitness_workout_sessions_started_at", "fitness_workout_sessions", ["started_at"])
    op.create_index("ix_fitness_workout_sessions_status", "fitness_workout_sessions", ["status"])

    op.add_column("fitness_exercise_sets", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("workout_session_id", sa.String(length=36), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("exercise_id", sa.String(length=36), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("template_exercise_id", sa.String(length=36), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("fitness_exercise_sets", sa.Column("load_kg", sa.Float(), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("rpe", sa.Float(), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("set_type", sa.String(length=40), nullable=False, server_default="working"))
    op.add_column("fitness_exercise_sets", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("fitness_exercise_sets", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.alter_column("fitness_exercise_sets", "workout_exercise_id", nullable=True)
    op.create_foreign_key("fk_fitness_exercise_sets_user_id", "fitness_exercise_sets", "user_profiles", ["user_id"], ["id"])
    op.create_foreign_key("fk_fitness_exercise_sets_session_id", "fitness_exercise_sets", "fitness_workout_sessions", ["workout_session_id"], ["id"])
    op.create_foreign_key("fk_fitness_exercise_sets_exercise_id", "fitness_exercise_sets", "fitness_exercises", ["exercise_id"], ["id"])
    op.create_foreign_key("fk_fitness_exercise_sets_template_exercise_id", "fitness_exercise_sets", "fitness_workout_template_exercises", ["template_exercise_id"], ["id"])
    op.create_index("ix_fitness_exercise_sets_user_id", "fitness_exercise_sets", ["user_id"])
    op.create_index("ix_fitness_exercise_sets_workout_session_id", "fitness_exercise_sets", ["workout_session_id"])
    op.create_index("ix_fitness_exercise_sets_exercise_id", "fitness_exercise_sets", ["exercise_id"])
    op.create_index("ix_fitness_exercise_sets_template_exercise_id", "fitness_exercise_sets", ["template_exercise_id"])
    op.create_index("ix_fitness_exercise_sets_idempotency_key", "fitness_exercise_sets", ["idempotency_key"])
    op.create_unique_constraint("uq_fitness_set_user_idempotency", "fitness_exercise_sets", ["user_id", "idempotency_key"])

    op.create_table(
        "fitness_progression_states",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("template_exercise_id", sa.String(length=36), nullable=False),
        sa.Column("exercise_id", sa.String(length=36), nullable=False),
        sa.Column("rule", sa.String(length=80), nullable=False, server_default="double_progression"),
        sa.Column("previous_load_kg", sa.Float(), nullable=True),
        sa.Column("recommended_load_kg", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.String(length=40), nullable=False, server_default="maintain"),
        sa.Column("explanation_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["exercise_id"], ["fitness_exercises.id"]),
        sa.ForeignKeyConstraint(["template_exercise_id"], ["fitness_workout_template_exercises.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_progression_states_user_id", "fitness_progression_states", ["user_id"])
    op.create_index("ix_fitness_progression_states_template_exercise_id", "fitness_progression_states", ["template_exercise_id"])
    op.create_index("ix_fitness_progression_states_exercise_id", "fitness_progression_states", ["exercise_id"])

    op.create_table(
        "fitness_recovery_observations",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("soreness", sa.Integer(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("stress", sa.Integer(), nullable=True),
        sa.Column("readiness", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_recovery_observations_user_id", "fitness_recovery_observations", ["user_id"])
    op.create_index("ix_fitness_recovery_observations_observed_at", "fitness_recovery_observations", ["observed_at"])

    op.create_table(
        "fitness_goals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_weight_kg", sa.Float(), nullable=True),
        sa.Column("target_body_fat_percentage", sa.Float(), nullable=True),
        sa.Column("target_lean_mass_kg", sa.Float(), nullable=True),
        sa.Column("direction", sa.String(length=80), nullable=False, server_default="body_recomposition"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fitness_goals_user_id", "fitness_goals", ["user_id"])
    op.create_index("ix_fitness_goals_active", "fitness_goals", ["active"])

    op.alter_column("fitness_body_measurements", "metadata_json", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_fitness_goals_active", table_name="fitness_goals")
    op.drop_index("ix_fitness_goals_user_id", table_name="fitness_goals")
    op.drop_table("fitness_goals")
    op.drop_index("ix_fitness_recovery_observations_observed_at", table_name="fitness_recovery_observations")
    op.drop_index("ix_fitness_recovery_observations_user_id", table_name="fitness_recovery_observations")
    op.drop_table("fitness_recovery_observations")
    op.drop_index("ix_fitness_progression_states_exercise_id", table_name="fitness_progression_states")
    op.drop_index("ix_fitness_progression_states_template_exercise_id", table_name="fitness_progression_states")
    op.drop_index("ix_fitness_progression_states_user_id", table_name="fitness_progression_states")
    op.drop_table("fitness_progression_states")

    op.drop_constraint("uq_fitness_set_user_idempotency", "fitness_exercise_sets", type_="unique")
    op.drop_index("ix_fitness_exercise_sets_idempotency_key", table_name="fitness_exercise_sets")
    op.drop_index("ix_fitness_exercise_sets_template_exercise_id", table_name="fitness_exercise_sets")
    op.drop_index("ix_fitness_exercise_sets_exercise_id", table_name="fitness_exercise_sets")
    op.drop_index("ix_fitness_exercise_sets_workout_session_id", table_name="fitness_exercise_sets")
    op.drop_index("ix_fitness_exercise_sets_user_id", table_name="fitness_exercise_sets")
    op.drop_constraint("fk_fitness_exercise_sets_template_exercise_id", "fitness_exercise_sets", type_="foreignkey")
    op.drop_constraint("fk_fitness_exercise_sets_exercise_id", "fitness_exercise_sets", type_="foreignkey")
    op.drop_constraint("fk_fitness_exercise_sets_session_id", "fitness_exercise_sets", type_="foreignkey")
    op.drop_constraint("fk_fitness_exercise_sets_user_id", "fitness_exercise_sets", type_="foreignkey")
    op.alter_column("fitness_exercise_sets", "workout_exercise_id", nullable=False)
    for column in [
        "idempotency_key",
        "note",
        "completed_at",
        "set_type",
        "rpe",
        "load_kg",
        "sequence",
        "template_exercise_id",
        "exercise_id",
        "workout_session_id",
        "user_id",
    ]:
        op.drop_column("fitness_exercise_sets", column)

    op.drop_index("ix_fitness_workout_sessions_status", table_name="fitness_workout_sessions")
    op.drop_index("ix_fitness_workout_sessions_started_at", table_name="fitness_workout_sessions")
    op.drop_index("ix_fitness_workout_sessions_workout_template_id", table_name="fitness_workout_sessions")
    op.drop_index("ix_fitness_workout_sessions_user_id", table_name="fitness_workout_sessions")
    op.drop_table("fitness_workout_sessions")
    op.drop_index("ix_fitness_workout_template_exercises_exercise_id", table_name="fitness_workout_template_exercises")
    op.drop_index("ix_fitness_workout_template_exercises_template_id", table_name="fitness_workout_template_exercises")
    op.drop_index("ix_fitness_workout_template_exercises_user_id", table_name="fitness_workout_template_exercises")
    op.drop_table("fitness_workout_template_exercises")
    op.drop_index("ix_fitness_workout_templates_active", table_name="fitness_workout_templates")
    op.drop_index("ix_fitness_workout_templates_program_id", table_name="fitness_workout_templates")
    op.drop_index("ix_fitness_workout_templates_user_id", table_name="fitness_workout_templates")
    op.drop_table("fitness_workout_templates")
    op.drop_index("ix_fitness_workout_programs_active", table_name="fitness_workout_programs")
    op.drop_index("ix_fitness_workout_programs_status", table_name="fitness_workout_programs")
    op.drop_index("ix_fitness_workout_programs_user_id", table_name="fitness_workout_programs")
    op.drop_table("fitness_workout_programs")

    op.drop_index("ix_fitness_exercises_active", table_name="fitness_exercises")
    for column in ["notes", "active", "default_rest_seconds", "equipment", "primary_muscle_group"]:
        op.drop_column("fitness_exercises", column)

    for column in ["metadata_json", "bmi", "visceral_fat_rating", "body_water_percentage", "muscle_mass_kg"]:
        op.drop_column("fitness_body_measurements", column)
