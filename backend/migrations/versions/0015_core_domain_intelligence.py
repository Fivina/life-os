"""core domain intelligence

Revision ID: 0015_core_domain_intelligence
Revises: 0014_adaptive_planner_v2
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0015_core_domain_intelligence"
down_revision = "0014_adaptive_planner_v2"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    for name, column, indexed in [
        ("domain", sa.Column("domain", sa.String(length=80), nullable=False, server_default="personal"), True),
        ("priority", sa.Column("priority", sa.Integer(), nullable=False, server_default="50"), False),
        ("success_condition", sa.Column("success_condition", sa.Text(), nullable=True), False),
        ("progress_mode", sa.Column("progress_mode", sa.String(length=40), nullable=False, server_default="manual"), False),
        ("manual_progress", sa.Column("manual_progress", sa.Float(), nullable=True), False),
        ("source_entity_type", sa.Column("source_entity_type", sa.String(length=80), nullable=True), True),
        ("source_entity_id", sa.Column("source_entity_id", sa.String(length=36), nullable=True), True),
        ("active", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), True),
    ]:
        op.add_column("goals", column)
        if indexed:
            op.create_index(f"ix_goals_{name}", "goals", [name])

    for name, column, indexed in [
        ("unit", sa.Column("unit", sa.String(length=40), nullable=True), False),
        ("status", sa.Column("status", sa.String(length=40), nullable=False, server_default="unknown"), True),
        ("risk", sa.Column("risk", sa.String(length=40), nullable=False, server_default="unknown"), True),
        ("on_track", sa.Column("on_track", sa.Boolean(), nullable=True), False),
        ("target_date", sa.Column("target_date", sa.Date(), nullable=True), False),
        ("current_rate", sa.Column("current_rate", sa.Float(), nullable=True), False),
        ("required_rate", sa.Column("required_rate", sa.Float(), nullable=True), False),
        ("source_domain", sa.Column("source_domain", sa.String(length=80), nullable=True), True),
        ("source_entity_type", sa.Column("source_entity_type", sa.String(length=80), nullable=True), True),
        ("source_entity_id", sa.Column("source_entity_id", sa.String(length=36), nullable=True), True),
        ("calculated_at", sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True), False),
    ]:
        op.add_column("trajectories", column)
        if indexed:
            op.create_index(f"ix_trajectories_{name}", "trajectories", [name])

    for name, column, indexed in [
        ("requirement_key", sa.Column("requirement_key", sa.String(length=255), nullable=True), True),
        ("source_entity_type", sa.Column("source_entity_type", sa.String(length=80), nullable=True), True),
        ("source_entity_id", sa.Column("source_entity_id", sa.String(length=36), nullable=True), True),
        ("goal_id", sa.Column("goal_id", sa.String(length=36), nullable=True), True),
        ("trajectory_id", sa.Column("trajectory_id", sa.String(length=36), nullable=True), True),
        ("generated_reason", sa.Column("generated_reason", sa.Text(), nullable=True), False),
        ("generation_version", sa.Column("generation_version", sa.String(length=40), nullable=False, server_default="manual"), False),
        ("planning_priority", sa.Column("planning_priority", sa.Integer(), nullable=False, server_default="50"), False),
    ]:
        op.add_column("actions", column)
        if indexed:
            op.create_index(f"ix_actions_{name}", "actions", [name])
    op.create_foreign_key("fk_actions_goal_id", "actions", "goals", ["goal_id"], ["id"])
    op.create_foreign_key("fk_actions_trajectory_id", "actions", "trajectories", ["trajectory_id"], ["id"])

    for name, column in [
        ("weekly_frequency", sa.Column("weekly_frequency", sa.Integer(), nullable=False, server_default="3")),
        ("minimum_recovery_hours", sa.Column("minimum_recovery_hours", sa.Integer(), nullable=False, server_default="24")),
        ("location", sa.Column("location", sa.String(length=120), nullable=True, server_default="gym")),
    ]:
        op.add_column("fitness_workout_programs", column)
    for name, column in [
        ("planned_snapshot_json", sa.Column("planned_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))),
        ("actual_duration_minutes", sa.Column("actual_duration_minutes", sa.Integer(), nullable=True)),
        ("modified", sa.Column("modified", sa.Boolean(), nullable=False, server_default=sa.false())),
    ]:
        op.add_column("fitness_workout_sessions", column)
    for name, column in [
        ("planned_duration_minutes", sa.Column("planned_duration_minutes", sa.Integer(), nullable=True)),
        ("completion_status", sa.Column("completion_status", sa.String(length=40), nullable=False, server_default="completed")),
        ("location", sa.Column("location", sa.String(length=120), nullable=True)),
        ("context_json", sa.Column("context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))),
    ]:
        op.add_column("learning_study_sessions", column)
    op.create_index("ix_learning_study_sessions_completion_status", "learning_study_sessions", ["completion_status"])

    op.create_table(
        "milestones",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
    )
    op.create_index("ix_milestones_user_id", "milestones", ["user_id"])
    op.create_index("ix_milestones_goal_id", "milestones", ["goal_id"])
    op.create_index("ix_milestones_status", "milestones", ["status"])

    op.create_table(
        "weekly_focuses",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("goal_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("priority_boost", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.UniqueConstraint("user_id", "week_start", "goal_id", "title", name="uq_weekly_focus_identity"),
    )
    op.create_index("ix_weekly_focuses_user_id", "weekly_focuses", ["user_id"])
    op.create_index("ix_weekly_focuses_week_start", "weekly_focuses", ["week_start"])
    op.create_index("ix_weekly_focuses_goal_id", "weekly_focuses", ["goal_id"])
    op.create_index("ix_weekly_focuses_active", "weekly_focuses", ["active"])

    op.create_table(
        "household_tasks",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False, server_default="chore"),
        sa.Column("recurrence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("minimum_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("location", sa.String(length=120), nullable=False, server_default="home"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("user_id", "title", name="uq_household_task_user_title"),
    )
    for name in ("user_id", "category", "last_completed_at", "next_due_at", "active"):
        op.create_index(f"ix_household_tasks_{name}", "household_tasks", [name])


def downgrade() -> None:
    op.drop_table("household_tasks")
    op.drop_table("weekly_focuses")
    op.drop_table("milestones")
    op.drop_index("ix_learning_study_sessions_completion_status", table_name="learning_study_sessions")
    for name in ("context_json", "location", "completion_status", "planned_duration_minutes"):
        op.drop_column("learning_study_sessions", name)
    for name in ("modified", "actual_duration_minutes", "planned_snapshot_json"):
        op.drop_column("fitness_workout_sessions", name)
    for name in ("location", "minimum_recovery_hours", "weekly_frequency"):
        op.drop_column("fitness_workout_programs", name)
    op.drop_constraint("fk_actions_trajectory_id", "actions", type_="foreignkey")
    op.drop_constraint("fk_actions_goal_id", "actions", type_="foreignkey")
    for name in ("planning_priority", "generation_version", "generated_reason", "trajectory_id", "goal_id", "source_entity_id", "source_entity_type", "requirement_key"):
        if name in {"trajectory_id", "goal_id", "source_entity_id", "source_entity_type", "requirement_key"}:
            op.drop_index(f"ix_actions_{name}", table_name="actions")
        op.drop_column("actions", name)
    for name in ("calculated_at", "source_entity_id", "source_entity_type", "source_domain", "required_rate", "current_rate", "target_date", "on_track", "risk", "status", "unit"):
        if name in {"source_entity_id", "source_entity_type", "source_domain", "risk", "status"}:
            op.drop_index(f"ix_trajectories_{name}", table_name="trajectories")
        op.drop_column("trajectories", name)
    for name in ("active", "source_entity_id", "source_entity_type", "manual_progress", "progress_mode", "success_condition", "priority", "domain"):
        if name in {"active", "source_entity_id", "source_entity_type", "domain"}:
            op.drop_index(f"ix_goals_{name}", table_name="goals")
        op.drop_column("goals", name)
