"""Initial explicit schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-28

This revision intentionally describes only the schema that existed at 0001.
It must never import live ORM metadata: later revisions own all later changes.
"""

import sqlalchemy as sa
from alembic import op


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("world_revision", sa.Integer(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"], unique=True)

    op.create_table(
        "commitments",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_commitments_user_id"),
    )
    op.create_index("ix_commitments_user_id", "commitments", ["user_id"])

    op.create_table(
        "constraints",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("constraint_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_constraints_user_id"),
    )
    op.create_index("ix_constraints_user_id", "constraints", ["user_id"])

    op.create_table(
        "events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("world_revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_events_user_id"),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_world_revision", "events", ["world_revision"])

    op.create_table(
        "fitness_body_measurements",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_weight_kg", sa.Float(), nullable=True),
        sa.Column("body_fat_percentage", sa.Float(), nullable=True),
        sa.Column("lean_mass_kg", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_fitness_body_measurements_user_id"),
    )
    op.create_index("ix_fitness_body_measurements_measured_at", "fitness_body_measurements", ["measured_at"])
    op.create_index("ix_fitness_body_measurements_user_id", "fitness_body_measurements", ["user_id"])

    op.create_table(
        "fitness_exercises",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_fitness_exercises_user_id"),
    )
    op.create_index("ix_fitness_exercises_user_id", "fitness_exercises", ["user_id"])

    op.create_table(
        "fitness_workouts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_fitness_workouts_user_id"),
    )
    op.create_index("ix_fitness_workouts_user_id", "fitness_workouts", ["user_id"])

    op.create_table(
        "goals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("horizon", sa.String(length=80), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_goals_user_id"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("mutation_key", sa.String(length=120), nullable=False),
        sa.Column("endpoint", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_idempotency_records_user_id"),
        sa.UniqueConstraint("user_id", "mutation_key", name="uq_idempotency_user_key"),
    )
    op.create_index("ix_idempotency_records_user_id", "idempotency_records", ["user_id"])

    op.create_table(
        "kitchen_food_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("preference_type", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("strength", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_food_preferences_user_id"),
    )
    op.create_index("ix_kitchen_food_preferences_user_id", "kitchen_food_preferences", ["user_id"])

    op.create_table(
        "kitchen_ingredients",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("default_unit", sa.String(length=40), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_ingredients_user_id"),
    )
    op.create_index("ix_kitchen_ingredients_user_id", "kitchen_ingredients", ["user_id"])

    op.create_table(
        "kitchen_meals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_meals_user_id"),
    )
    op.create_index("ix_kitchen_meals_user_id", "kitchen_meals", ["user_id"])

    op.create_table(
        "kitchen_nutrition_logs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_nutrition_logs_user_id"),
    )
    op.create_index("ix_kitchen_nutrition_logs_user_id", "kitchen_nutrition_logs", ["user_id"])

    op.create_table(
        "kitchen_shopping_lists",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_shopping_lists_user_id"),
    )
    op.create_index("ix_kitchen_shopping_lists_user_id", "kitchen_shopping_lists", ["user_id"])

    op.create_table(
        "learning_courses",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_learning_courses_user_id"),
    )
    op.create_index("ix_learning_courses_user_id", "learning_courses", ["user_id"])

    op.create_table(
        "notification_intents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("intent_type", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_notification_intents_user_id"),
    )
    op.create_index("ix_notification_intents_user_id", "notification_intents", ["user_id"])

    op.create_table(
        "plans",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("planner_version", sa.String(length=40), nullable=False),
        sa.Column("generated_from_world_revision", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("planning_day", sa.Date(), nullable=True),
        sa.Column("decision_factors", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_plans_user_id"),
    )
    op.create_index("ix_plans_user_id", "plans", ["user_id"])

    op.create_table(
        "state_observations",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("observation_type", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_state_observations_user_id"),
    )
    op.create_index("ix_state_observations_observation_type", "state_observations", ["observation_type"])
    op.create_index("ix_state_observations_observed_at", "state_observations", ["observed_at"])
    op.create_index("ix_state_observations_user_id", "state_observations", ["user_id"])

    op.create_table(
        "fitness_workout_exercises",
        sa.Column("workout_id", sa.String(length=36), nullable=False),
        sa.Column("exercise_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["exercise_id"], ["fitness_exercises.id"], name="fk_fitness_workout_exercises_exercise_id"),
        sa.ForeignKeyConstraint(["workout_id"], ["fitness_workouts.id"], name="fk_fitness_workout_exercises_workout_id"),
    )
    op.create_index("ix_fitness_workout_exercises_exercise_id", "fitness_workout_exercises", ["exercise_id"])
    op.create_index("ix_fitness_workout_exercises_workout_id", "fitness_workout_exercises", ["workout_id"])

    op.create_table(
        "kitchen_inventory_items",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_name", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_inventory_items_user_id"),
    )
    op.create_index("ix_kitchen_inventory_items_user_id", "kitchen_inventory_items", ["user_id"])

    op.create_table(
        "kitchen_shopping_list_items",
        sa.Column("shopping_list_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_name", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["kitchen_shopping_lists.id"], name="fk_kitchen_shopping_list_items_shopping_list_id"),
    )
    op.create_index("ix_kitchen_shopping_list_items_shopping_list_id", "kitchen_shopping_list_items", ["shopping_list_id"])

    op.create_table(
        "learning_exams",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("estimated_required_hours", sa.Float(), nullable=False),
        sa.Column("completed_hours", sa.Float(), nullable=False),
        sa.Column("importance", sa.String(length=40), nullable=False),
        sa.Column("attempts_remaining", sa.Integer(), nullable=True),
        sa.Column("final_attempt", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["learning_courses.id"], name="fk_learning_exams_course_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_learning_exams_user_id"),
    )
    op.create_index("ix_learning_exams_user_id", "learning_exams", ["user_id"])

    op.create_table(
        "outbox_events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_outbox_events_event_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_outbox_events_user_id"),
    )
    op.create_index("ix_outbox_events_event_id", "outbox_events", ["event_id"])
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_user_id", "outbox_events", ["user_id"])

    op.create_table(
        "trajectories",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], name="fk_trajectories_goal_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_trajectories_user_id"),
    )
    op.create_index("ix_trajectories_user_id", "trajectories", ["user_id"])

    op.create_table(
        "world_revisions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=160), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_world_revisions_event_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_world_revisions_user_id"),
        sa.UniqueConstraint("user_id", "revision", name="uq_world_revision_user_revision"),
    )
    op.create_index("ix_world_revisions_user_id", "world_revisions", ["user_id"])

    op.create_table(
        "actions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_actions_user_id"),
    )
    op.create_index("ix_actions_user_id", "actions", ["user_id"])

    op.create_table(
        "learning_study_requirements",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("estimated_hours", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["exam_id"], ["learning_exams.id"], name="fk_learning_study_requirements_exam_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_learning_study_requirements_user_id"),
    )
    op.create_index("ix_learning_study_requirements_exam_id", "learning_study_requirements", ["exam_id"])
    op.create_index("ix_learning_study_requirements_user_id", "learning_study_requirements", ["user_id"])

    op.create_table(
        "plan_blocks",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], name="fk_plan_blocks_action_id"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], name="fk_plan_blocks_plan_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_plan_blocks_user_id"),
    )
    op.create_index("ix_plan_blocks_plan_id", "plan_blocks", ["plan_id"])
    op.create_index("ix_plan_blocks_user_id", "plan_blocks", ["user_id"])

    op.create_table(
        "learning_study_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["exam_id"], ["learning_exams.id"], name="fk_learning_study_sessions_exam_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_learning_study_sessions_user_id"),
    )
    op.create_index("ix_learning_study_sessions_user_id", "learning_study_sessions", ["user_id"])

    op.create_table(
        "fitness_exercise_sets",
        sa.Column("workout_exercise_id", sa.String(length=36), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("perceived_exertion", sa.Float(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["workout_exercise_id"], ["fitness_workout_exercises.id"], name="fk_fitness_exercise_sets_workout_exercise_id"),
    )
    op.create_index("ix_fitness_exercise_sets_workout_exercise_id", "fitness_exercise_sets", ["workout_exercise_id"])


def downgrade() -> None:
    for table in [
        "fitness_exercise_sets",
        "learning_study_sessions",
        "plan_blocks",
        "learning_study_requirements",
        "actions",
        "world_revisions",
        "trajectories",
        "outbox_events",
        "learning_exams",
        "kitchen_shopping_list_items",
        "kitchen_inventory_items",
        "fitness_workout_exercises",
        "state_observations",
        "plans",
        "notification_intents",
        "learning_courses",
        "kitchen_shopping_lists",
        "kitchen_nutrition_logs",
        "kitchen_meals",
        "kitchen_ingredients",
        "kitchen_food_preferences",
        "idempotency_records",
        "goals",
        "fitness_workouts",
        "fitness_exercises",
        "fitness_body_measurements",
        "events",
        "constraints",
        "commitments",
        "user_profiles",
    ]:
        op.drop_table(table)
