"""adaptive planner v2

Revision ID: 0014_adaptive_planner_v2
Revises: 0013_memory_brain_completion
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0014_adaptive_planner_v2"
down_revision = "0013_memory_brain_completion"
branch_labels = None
depends_on = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    for name, column in [
        ("candidate_group_id", sa.Column("candidate_group_id", sa.String(length=120), nullable=True)),
        ("variant_type", sa.Column("variant_type", sa.String(length=40), nullable=False, server_default="standard")),
        ("variant_rank", sa.Column("variant_rank", sa.Integer(), nullable=False, server_default="0")),
        ("mutually_exclusive", sa.Column("mutually_exclusive", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("variant_quality", sa.Column("variant_quality", sa.Float(), nullable=False, server_default="1")),
    ]:
        op.add_column("actions", column)
        if name in {"candidate_group_id", "variant_type"}:
            op.create_index(f"ix_actions_{name}", "actions", [name])

    for name, column in [
        ("strength", sa.Column("strength", sa.String(length=20), nullable=False, server_default="hard")),
        ("provenance", sa.Column("provenance", sa.String(length=40), nullable=False, server_default="canonical")),
        ("domain", sa.Column("domain", sa.String(length=80), nullable=True)),
        ("starts_at", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True)),
        ("ends_at", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True)),
        ("penalty", sa.Column("penalty", sa.Float(), nullable=False, server_default="12")),
    ]:
        op.add_column("constraints", column)
        if name != "penalty":
            op.create_index(f"ix_constraints_{name}", "constraints", [name])

    for name, column in [
        ("overload_status", sa.Column("overload_status", sa.String(length=40), nullable=False, server_default="feasible")),
        ("shortfall_minutes", sa.Column("shortfall_minutes", sa.Integer(), nullable=False, server_default="0")),
        ("overload_json", sa.Column("overload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))),
    ]:
        op.add_column("plans", column)
    op.create_index("ix_plans_overload_status", "plans", ["overload_status"])

    for name, column in [
        ("action_group_id", sa.Column("action_group_id", sa.String(length=120), nullable=True)),
        ("variant_type", sa.Column("variant_type", sa.String(length=40), nullable=True)),
        ("frozen_until", sa.Column("frozen_until", sa.DateTime(timezone=True), nullable=True)),
        ("user_locked", sa.Column("user_locked", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("user_modified", sa.Column("user_modified", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("original_starts_at", sa.Column("original_starts_at", sa.DateTime(timezone=True), nullable=True)),
        ("residual_minutes", sa.Column("residual_minutes", sa.Integer(), nullable=False, server_default="0")),
    ]:
        op.add_column("plan_blocks", column)
        if name in {"action_group_id", "variant_type", "frozen_until"}:
            op.create_index(f"ix_plan_blocks_{name}", "plan_blocks", [name])

    op.create_table(
        "planning_allocations",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("planning_date", sa.Date(), nullable=False),
        sa.Column("action_group_id", sa.String(length=120), nullable=False),
        sa.Column("source_action_id", sa.String(length=36), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("required_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocated_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debt_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="allocated"),
        sa.Column("risk_status", sa.String(length=40), nullable=False, server_default="feasible"),
        sa.Column("reason_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.ForeignKeyConstraint(["source_action_id"], ["actions.id"]),
        sa.UniqueConstraint("user_id", "planning_date", "action_group_id", name="uq_planning_allocation_user_day_group"),
    )
    for name in ["user_id", "planning_date", "action_group_id", "source_action_id", "domain", "deadline", "status", "risk_status"]:
        op.create_index(f"ix_planning_allocations_{name}", "planning_allocations", [name])

    op.create_table(
        "planning_debts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action_group_id", sa.String(length=120), nullable=False),
        sa.Column("source_action_id", sa.String(length=36), nullable=True),
        sa.Column("source_plan_block_id", sa.String(length=36), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("residual_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.ForeignKeyConstraint(["source_action_id"], ["actions.id"]),
        sa.ForeignKeyConstraint(["source_plan_block_id"], ["plan_blocks.id"]),
        sa.UniqueConstraint("user_id", "source_plan_block_id", name="uq_planning_debt_user_block"),
    )
    for name in ["user_id", "action_group_id", "source_action_id", "source_plan_block_id", "domain", "status", "deadline"]:
        op.create_index(f"ix_planning_debts_{name}", "planning_debts", [name])


def downgrade() -> None:
    op.drop_table("planning_debts")
    op.drop_table("planning_allocations")
    for name in ["frozen_until", "variant_type", "action_group_id"]:
        op.drop_index(f"ix_plan_blocks_{name}", table_name="plan_blocks")
    for name in ["residual_minutes", "original_starts_at", "user_modified", "user_locked", "frozen_until", "variant_type", "action_group_id"]:
        op.drop_column("plan_blocks", name)
    op.drop_index("ix_plans_overload_status", table_name="plans")
    for name in ["overload_json", "shortfall_minutes", "overload_status"]:
        op.drop_column("plans", name)
    for name in ["ends_at", "starts_at", "domain", "provenance", "strength"]:
        op.drop_index(f"ix_constraints_{name}", table_name="constraints")
    for name in ["penalty", "ends_at", "starts_at", "domain", "provenance", "strength"]:
        op.drop_column("constraints", name)
    for name in ["variant_type", "candidate_group_id"]:
        op.drop_index(f"ix_actions_{name}", table_name="actions")
    for name in ["variant_quality", "mutually_exclusive", "variant_rank", "variant_type", "candidate_group_id"]:
        op.drop_column("actions", name)
