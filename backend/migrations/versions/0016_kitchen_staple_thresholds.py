"""Add deterministic staple thresholds to kitchen inventory.

Revision ID: 0016_kitchen_staple_thresholds
Revises: 5b230780f4f2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_kitchen_staple_thresholds"
down_revision: Union[str, Sequence[str], None] = "5b230780f4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kitchen_inventory_items", sa.Column("is_staple", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("kitchen_inventory_items", sa.Column("restock_threshold", sa.Float(), nullable=True))
    op.add_column("kitchen_inventory_items", sa.Column("restock_target", sa.Float(), nullable=True))
    op.create_index(op.f("ix_kitchen_inventory_items_is_staple"), "kitchen_inventory_items", ["is_staple"], unique=False)
    op.alter_column("kitchen_inventory_items", "is_staple", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_kitchen_inventory_items_is_staple"), table_name="kitchen_inventory_items")
    op.drop_column("kitchen_inventory_items", "restock_target")
    op.drop_column("kitchen_inventory_items", "restock_threshold")
    op.drop_column("kitchen_inventory_items", "is_staple")
