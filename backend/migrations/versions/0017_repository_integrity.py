"""Normalize v1.5 constraints and retire empty legacy Kitchen tables.

Revision ID: 0017_repository_integrity
Revises: 0016_kitchen_staple_thresholds
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_repository_integrity"
down_revision: Union[str, Sequence[str], None] = "0016_kitchen_staple_thresholds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_NAMES = {
    ("kitchen_inventory_items", ("ingredient_id",), "kitchen_ingredients"): "fk_kitchen_inventory_items_ingredient_id",
    ("kitchen_meal_history", ("recommendation_id",), "recommendations"): "fk_kitchen_meal_history_recommendation_id",
    ("kitchen_meal_history", ("recommendation_option_id",), "recommendation_options"): "fk_kitchen_meal_history_recommendation_option_id",
    ("kitchen_meal_history", ("meal_plan_id",), "kitchen_meal_plans"): "fk_kitchen_meal_history_meal_plan_id",
    ("kitchen_recipe_ingredients", ("ingredient_id",), "kitchen_ingredients"): "fk_kitchen_recipe_ingredients_ingredient_id",
    ("kitchen_shopping_needs", ("meal_plan_id",), "kitchen_meal_plans"): "fk_kitchen_shopping_needs_meal_plan_id",
    ("kitchen_shopping_needs", ("action_id",), "actions"): "fk_kitchen_shopping_needs_action_id",
}

LEGACY_TABLES = [
    "kitchen_shopping_list_items",
    "kitchen_shopping_lists",
    "kitchen_food_preferences",
    "kitchen_nutrition_logs",
    "kitchen_meals",
]


def _normalize_foreign_keys() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    preparer = bind.dialect.identifier_preparer
    for (table, columns, referred_table), canonical in FK_NAMES.items():
        matches = [
            fk for fk in inspector.get_foreign_keys(table)
            if tuple(fk.get("constrained_columns") or ()) == columns and fk.get("referred_table") == referred_table
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one foreign key for {table}{columns} -> {referred_table}, found {len(matches)}.")
        current = matches[0].get("name")
        if current == canonical:
            continue
        if not current:
            raise RuntimeError(f"Cannot normalize unnamed foreign key for {table}{columns}.")
        if bind.dialect.name != "postgresql":
            raise RuntimeError(f"Foreign-key renaming requires PostgreSQL; found {bind.dialect.name}.")
        op.execute(sa.text(
            f"ALTER TABLE {preparer.quote(table)} RENAME CONSTRAINT "
            f"{preparer.quote(current)} TO {preparer.quote(canonical)}"
        ))


def _drop_empty_legacy_tables() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in LEGACY_TABLES:
        if table not in existing:
            continue
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
        if count:
            raise RuntimeError(f"Refusing to drop legacy table {table}: it contains {count} rows.")
    for table in LEGACY_TABLES:
        if table in existing:
            op.drop_table(table)


def upgrade() -> None:
    _normalize_foreign_keys()
    _drop_empty_legacy_tables()


def downgrade() -> None:
    op.create_table(
        "kitchen_meals",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_meals_user_id"),
        sa.PrimaryKeyConstraint("id"),
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
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_nutrition_logs_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_nutrition_logs_user_id", "kitchen_nutrition_logs", ["user_id"])
    op.create_table(
        "kitchen_food_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("preference_type", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("strength", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_food_preferences_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_food_preferences_user_id", "kitchen_food_preferences", ["user_id"])
    op.create_table(
        "kitchen_shopping_lists",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_kitchen_shopping_lists_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_shopping_lists_user_id", "kitchen_shopping_lists", ["user_id"])
    op.create_table(
        "kitchen_shopping_list_items",
        sa.Column("shopping_list_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_name", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["kitchen_shopping_lists.id"], name="fk_kitchen_shopping_list_items_shopping_list_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_shopping_list_items_shopping_list_id", "kitchen_shopping_list_items", ["shopping_list_id"])
