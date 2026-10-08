"""commitments and intentions v0.2 fields

Revision ID: 0002_commitments_intentions
Revises: 0001_initial
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_commitments_intentions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("commitments", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("commitments", sa.Column("level", sa.String(length=40), nullable=False, server_default="hard"))
    op.add_column("commitments", sa.Column("commitment_type", sa.String(length=40), nullable=False, server_default="hard"))
    op.add_column("commitments", sa.Column("timezone", sa.String(length=80), nullable=False, server_default="Europe/Berlin"))
    op.add_column("commitments", sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("commitments", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("commitments", sa.Column("recurrence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_index("ix_commitments_level", "commitments", ["level"])
    op.create_index("ix_commitments_commitment_type", "commitments", ["commitment_type"])

    op.add_column("actions", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("actions", sa.Column("level", sa.String(length=40), nullable=False, server_default="maintenance"))
    op.add_column("actions", sa.Column("earliest_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("actions", sa.Column("latest_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("actions", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("actions", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("actions", sa.Column("context", sa.String(length=120), nullable=True))
    op.add_column("actions", sa.Column("duration_min_minutes", sa.Integer(), nullable=True))
    op.add_column("actions", sa.Column("duration_max_minutes", sa.Integer(), nullable=True))
    op.add_column("actions", sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("actions", sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_actions_level", "actions", ["level"])
    op.create_index("ix_actions_status", "actions", ["status"])
    op.create_index("ix_actions_deadline", "actions", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_actions_deadline", table_name="actions")
    op.drop_index("ix_actions_status", table_name="actions")
    op.drop_index("ix_actions_level", table_name="actions")
    op.drop_column("actions", "scheduled_end")
    op.drop_column("actions", "scheduled_start")
    op.drop_column("actions", "duration_max_minutes")
    op.drop_column("actions", "duration_min_minutes")
    op.drop_column("actions", "context")
    op.drop_column("actions", "location")
    op.drop_column("actions", "deadline")
    op.drop_column("actions", "latest_start")
    op.drop_column("actions", "earliest_start")
    op.drop_column("actions", "level")
    op.drop_column("actions", "description")

    op.drop_index("ix_commitments_commitment_type", table_name="commitments")
    op.drop_index("ix_commitments_level", table_name="commitments")
    op.drop_column("commitments", "recurrence")
    op.drop_column("commitments", "location")
    op.drop_column("commitments", "all_day")
    op.drop_column("commitments", "timezone")
    op.drop_column("commitments", "commitment_type")
    op.drop_column("commitments", "level")
    op.drop_column("commitments", "description")
