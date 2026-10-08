"""daily control loop v0.4

Revision ID: 0004_daily_control_loop
Revises: 0003_core_planner
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_daily_control_loop"
down_revision = "0003_core_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("actions", sa.Column("completed_minutes", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("plans", sa.Column("previous_plan_id", sa.String(length=36), nullable=True))
    op.add_column("plans", sa.Column("replan_reason", sa.String(length=120), nullable=True))
    op.add_column("plans", sa.Column("control_loop_version", sa.String(length=40), nullable=False, server_default="v0.4-control-loop"))
    op.add_column("plans", sa.Column("plan_diff", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("plans", sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plans", sa.Column("last_replanned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_plans_previous_plan_id", "plans", "plans", ["previous_plan_id"], ["id"])

    op.add_column("plan_blocks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_blocks", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_blocks", sa.Column("actual_duration_minutes", sa.Integer(), nullable=True))
    op.add_column("plan_blocks", sa.Column("outcome_reason", sa.String(length=120), nullable=True))
    op.add_column("plan_blocks", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("plan_blocks", "note")
    op.drop_column("plan_blocks", "outcome_reason")
    op.drop_column("plan_blocks", "actual_duration_minutes")
    op.drop_column("plan_blocks", "finished_at")
    op.drop_column("plan_blocks", "started_at")

    op.drop_constraint("fk_plans_previous_plan_id", "plans", type_="foreignkey")
    op.drop_column("plans", "last_replanned_at")
    op.drop_column("plans", "last_evaluated_at")
    op.drop_column("plans", "plan_diff")
    op.drop_column("plans", "control_loop_version")
    op.drop_column("plans", "replan_reason")
    op.drop_column("plans", "previous_plan_id")

    op.drop_column("actions", "completed_minutes")
