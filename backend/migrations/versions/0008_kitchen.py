"""kitchen domain v0.8

Revision ID: 0008_kitchen
Revises: 0007_assistant
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_kitchen"
down_revision = "0007_assistant"
branch_labels = None
depends_on = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.add_column("kitchen_inventory_items", sa.Column("category", sa.String(length=80), nullable=True))
    op.add_column("kitchen_inventory_items", sa.Column("canonical_unit", sa.String(length=40), nullable=False, server_default="count"))
    op.add_column("kitchen_inventory_items", sa.Column("default_storage_location", sa.String(length=80), nullable=True))
    op.add_column("kitchen_inventory_items", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("kitchen_inventory_items", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_kitchen_inventory_items_active", "kitchen_inventory_items", ["active"])

    op.create_table(
        "kitchen_inventory_lots",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="count"),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_location", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["kitchen_inventory_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_inventory_lots_user_id", "kitchen_inventory_lots", ["user_id"])
    op.create_index("ix_kitchen_inventory_lots_inventory_item_id", "kitchen_inventory_lots", ["inventory_item_id"])
    op.create_index("ix_kitchen_inventory_lots_purchased_at", "kitchen_inventory_lots", ["purchased_at"])
    op.create_index("ix_kitchen_inventory_lots_expires_at", "kitchen_inventory_lots", ["expires_at"])
    op.create_index("ix_kitchen_inventory_lots_status", "kitchen_inventory_lots", ["status"])

    op.create_table(
        "kitchen_recipes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("preparation_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("cooking_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("calories_per_serving", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g_per_serving", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g_per_serving", sa.Float(), nullable=True),
        sa.Column("fat_g_per_serving", sa.Float(), nullable=True),
        sa.Column("protein_family", sa.String(length=80), nullable=True),
        sa.Column("difficulty", sa.String(length=40), nullable=False, server_default="easy"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_recipes_user_id", "kitchen_recipes", ["user_id"])
    op.create_index("ix_kitchen_recipes_protein_family", "kitchen_recipes", ["protein_family"])
    op.create_index("ix_kitchen_recipes_active", "kitchen_recipes", ["active"])

    op.create_table(
        "kitchen_recipe_ingredients",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("recipe_id", sa.String(length=36), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=36), nullable=True),
        sa.Column("ingredient_name", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="count"),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("substitution_group", sa.String(length=80), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["kitchen_inventory_items.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["kitchen_recipes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_recipe_ingredients_user_id", "kitchen_recipe_ingredients", ["user_id"])
    op.create_index("ix_kitchen_recipe_ingredients_recipe_id", "kitchen_recipe_ingredients", ["recipe_id"])
    op.create_index("ix_kitchen_recipe_ingredients_inventory_item_id", "kitchen_recipe_ingredients", ["inventory_item_id"])

    op.create_table(
        "kitchen_meal_history",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("recipe_id", sa.String(length=36), nullable=True),
        sa.Column("name_snapshot", sa.String(length=180), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("calories_snapshot", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g_snapshot", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g_snapshot", sa.Float(), nullable=True),
        sa.Column("fat_g_snapshot", sa.Float(), nullable=True),
        sa.Column("satisfaction", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("source_plan_block_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["recipe_id"], ["kitchen_recipes.id"]),
        sa.ForeignKeyConstraint(["source_plan_block_id"], ["plan_blocks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_meal_history_user_id", "kitchen_meal_history", ["user_id"])
    op.create_index("ix_kitchen_meal_history_recipe_id", "kitchen_meal_history", ["recipe_id"])
    op.create_index("ix_kitchen_meal_history_consumed_at", "kitchen_meal_history", ["consumed_at"])
    op.create_index("ix_kitchen_meal_history_source_plan_block_id", "kitchen_meal_history", ["source_plan_block_id"])

    op.create_table(
        "kitchen_nutrition_targets",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("calories_target", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_g_target", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_nutrition_targets_user_id", "kitchen_nutrition_targets", ["user_id"])
    op.create_index("ix_kitchen_nutrition_targets_effective_from", "kitchen_nutrition_targets", ["effective_from"])
    op.create_index("ix_kitchen_nutrition_targets_effective_to", "kitchen_nutrition_targets", ["effective_to"])
    op.create_index("ix_kitchen_nutrition_targets_status", "kitchen_nutrition_targets", ["status"])

    op.create_table(
        "kitchen_preference_evidence",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("recipe_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("protein_family", sa.String(length=80), nullable=True),
        sa.Column("signal", sa.String(length=80), nullable=False, server_default="explicit"),
        sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["recipe_id"], ["kitchen_recipes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_preference_evidence_user_id", "kitchen_preference_evidence", ["user_id"])
    op.create_index("ix_kitchen_preference_evidence_recipe_id", "kitchen_preference_evidence", ["recipe_id"])
    op.create_index("ix_kitchen_preference_evidence_protein_family", "kitchen_preference_evidence", ["protein_family"])
    op.create_index("ix_kitchen_preference_evidence_observed_at", "kitchen_preference_evidence", ["observed_at"])

    op.create_table(
        "kitchen_shopping_needs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("required_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="forecast"),
        sa.Column("forecast_window_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_shopping_needs_user_id", "kitchen_shopping_needs", ["user_id"])
    op.create_index("ix_kitchen_shopping_needs_status", "kitchen_shopping_needs", ["status"])
    op.create_index("ix_kitchen_shopping_needs_required_by", "kitchen_shopping_needs", ["required_by"])

    op.create_table(
        "kitchen_shopping_need_items",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("shopping_need_id", sa.String(length=36), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=36), nullable=True),
        sa.Column("ingredient_name", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="count"),
        sa.Column("satisfied", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["kitchen_inventory_items.id"]),
        sa.ForeignKeyConstraint(["shopping_need_id"], ["kitchen_shopping_needs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchen_shopping_need_items_user_id", "kitchen_shopping_need_items", ["user_id"])
    op.create_index("ix_kitchen_shopping_need_items_shopping_need_id", "kitchen_shopping_need_items", ["shopping_need_id"])
    op.create_index("ix_kitchen_shopping_need_items_inventory_item_id", "kitchen_shopping_need_items", ["inventory_item_id"])
    op.create_index("ix_kitchen_shopping_need_items_satisfied", "kitchen_shopping_need_items", ["satisfied"])


def downgrade() -> None:
    op.drop_index("ix_kitchen_shopping_need_items_satisfied", table_name="kitchen_shopping_need_items")
    op.drop_index("ix_kitchen_shopping_need_items_inventory_item_id", table_name="kitchen_shopping_need_items")
    op.drop_index("ix_kitchen_shopping_need_items_shopping_need_id", table_name="kitchen_shopping_need_items")
    op.drop_index("ix_kitchen_shopping_need_items_user_id", table_name="kitchen_shopping_need_items")
    op.drop_table("kitchen_shopping_need_items")

    op.drop_index("ix_kitchen_shopping_needs_required_by", table_name="kitchen_shopping_needs")
    op.drop_index("ix_kitchen_shopping_needs_status", table_name="kitchen_shopping_needs")
    op.drop_index("ix_kitchen_shopping_needs_user_id", table_name="kitchen_shopping_needs")
    op.drop_table("kitchen_shopping_needs")

    op.drop_index("ix_kitchen_preference_evidence_observed_at", table_name="kitchen_preference_evidence")
    op.drop_index("ix_kitchen_preference_evidence_protein_family", table_name="kitchen_preference_evidence")
    op.drop_index("ix_kitchen_preference_evidence_recipe_id", table_name="kitchen_preference_evidence")
    op.drop_index("ix_kitchen_preference_evidence_user_id", table_name="kitchen_preference_evidence")
    op.drop_table("kitchen_preference_evidence")

    op.drop_index("ix_kitchen_nutrition_targets_status", table_name="kitchen_nutrition_targets")
    op.drop_index("ix_kitchen_nutrition_targets_effective_to", table_name="kitchen_nutrition_targets")
    op.drop_index("ix_kitchen_nutrition_targets_effective_from", table_name="kitchen_nutrition_targets")
    op.drop_index("ix_kitchen_nutrition_targets_user_id", table_name="kitchen_nutrition_targets")
    op.drop_table("kitchen_nutrition_targets")

    op.drop_index("ix_kitchen_meal_history_source_plan_block_id", table_name="kitchen_meal_history")
    op.drop_index("ix_kitchen_meal_history_consumed_at", table_name="kitchen_meal_history")
    op.drop_index("ix_kitchen_meal_history_recipe_id", table_name="kitchen_meal_history")
    op.drop_index("ix_kitchen_meal_history_user_id", table_name="kitchen_meal_history")
    op.drop_table("kitchen_meal_history")

    op.drop_index("ix_kitchen_recipe_ingredients_inventory_item_id", table_name="kitchen_recipe_ingredients")
    op.drop_index("ix_kitchen_recipe_ingredients_recipe_id", table_name="kitchen_recipe_ingredients")
    op.drop_index("ix_kitchen_recipe_ingredients_user_id", table_name="kitchen_recipe_ingredients")
    op.drop_table("kitchen_recipe_ingredients")

    op.drop_index("ix_kitchen_recipes_active", table_name="kitchen_recipes")
    op.drop_index("ix_kitchen_recipes_protein_family", table_name="kitchen_recipes")
    op.drop_index("ix_kitchen_recipes_user_id", table_name="kitchen_recipes")
    op.drop_table("kitchen_recipes")

    op.drop_index("ix_kitchen_inventory_lots_status", table_name="kitchen_inventory_lots")
    op.drop_index("ix_kitchen_inventory_lots_expires_at", table_name="kitchen_inventory_lots")
    op.drop_index("ix_kitchen_inventory_lots_purchased_at", table_name="kitchen_inventory_lots")
    op.drop_index("ix_kitchen_inventory_lots_inventory_item_id", table_name="kitchen_inventory_lots")
    op.drop_index("ix_kitchen_inventory_lots_user_id", table_name="kitchen_inventory_lots")
    op.drop_table("kitchen_inventory_lots")

    op.drop_index("ix_kitchen_inventory_items_active", table_name="kitchen_inventory_items")
    for column in ["notes", "active", "default_storage_location", "canonical_unit", "category"]:
        op.drop_column("kitchen_inventory_items", column)
