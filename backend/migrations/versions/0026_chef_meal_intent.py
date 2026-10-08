"""Chef MealIntent execution support.

Revision ID: 0026_chef_meal_intent
Revises: 0025_social_opportunities
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_chef_meal_intent"
down_revision = "0025_social_opportunities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kitchen_meal_history", sa.Column("actual_usage_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("kitchen_meal_plans", sa.Column("planned_ingredients_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("kitchen_meal_plans", sa.Column("modifications_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.alter_column("kitchen_meal_plans", "planned_ingredients_json", server_default=None)
    op.alter_column("kitchen_meal_plans", "modifications_json", server_default=None)
    op.alter_column("kitchen_meal_history", "actual_usage_json", server_default=None)


def downgrade() -> None:
    op.drop_column("kitchen_meal_plans", "modifications_json")
    op.drop_column("kitchen_meal_plans", "planned_ingredients_json")
    op.drop_column("kitchen_meal_history", "actual_usage_json")
