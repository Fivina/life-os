"""core planner v0.3

Revision ID: 0003_core_planner
Revises: 0002_commitments_intentions
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_core_planner"
down_revision = "0002_commitments_intentions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plans", sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plans", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("plans", sa.Column("summary_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    op.add_column("plan_blocks", sa.Column("commitment_id", sa.String(length=36), nullable=True))
    op.add_column("plan_blocks", sa.Column("source_type", sa.String(length=80), nullable=False, server_default="planner"))
    op.add_column("plan_blocks", sa.Column("source_id", sa.String(length=36), nullable=True))
    op.add_column("plan_blocks", sa.Column("domain", sa.String(length=80), nullable=True))
    op.add_column("plan_blocks", sa.Column("title", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("plan_blocks", sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("plan_blocks", sa.Column("block_type", sa.String(length=80), nullable=False, server_default="generated_action"))
    op.add_column("plan_blocks", sa.Column("commitment_level", sa.String(length=40), nullable=True))
    op.add_column("plan_blocks", sa.Column("movable", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("plan_blocks", sa.Column("decision_factors", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_index("ix_plan_blocks_source_id", "plan_blocks", ["source_id"])
    op.create_index("ix_plan_blocks_block_type", "plan_blocks", ["block_type"])
    op.create_foreign_key("fk_plan_blocks_commitment_id", "plan_blocks", "commitments", ["commitment_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_plan_blocks_commitment_id", "plan_blocks", type_="foreignkey")
    op.drop_index("ix_plan_blocks_block_type", table_name="plan_blocks")
    op.drop_index("ix_plan_blocks_source_id", table_name="plan_blocks")
    op.drop_column("plan_blocks", "decision_factors")
    op.drop_column("plan_blocks", "movable")
    op.drop_column("plan_blocks", "commitment_level")
    op.drop_column("plan_blocks", "block_type")
    op.drop_column("plan_blocks", "duration_minutes")
    op.drop_column("plan_blocks", "title")
    op.drop_column("plan_blocks", "domain")
    op.drop_column("plan_blocks", "source_id")
    op.drop_column("plan_blocks", "source_type")
    op.drop_column("plan_blocks", "commitment_id")

    op.drop_column("plans", "summary_metrics")
    op.drop_column("plans", "generated_at")
    op.drop_column("plans", "horizon_end")
    op.drop_column("plans", "horizon_start")
