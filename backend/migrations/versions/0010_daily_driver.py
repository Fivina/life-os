"""daily driver v1.0

Revision ID: 0010_daily_driver
Revises: 0009_personal_learning
Create Date: 2026-09-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0010_daily_driver"
down_revision = "0009_personal_learning"
branch_labels = None
depends_on = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("auth_subject", sa.String(length=255), nullable=True))
    op.create_index("ix_user_profiles_auth_subject", "user_profiles", ["auth_subject"], unique=True)

    op.add_column("outbox_events", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])

    op.add_column("notification_intents", sa.Column("title", sa.String(length=180), nullable=True))
    op.add_column("notification_intents", sa.Column("body", sa.Text(), nullable=True))
    op.add_column("notification_intents", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_intents", sa.Column("dedupe_key", sa.String(length=180), nullable=True))
    op.add_column("notification_intents", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_intents", sa.Column("suppressed_reason", sa.String(length=120), nullable=True))
    op.create_index("ix_notification_intents_status", "notification_intents", ["status"])
    op.create_index("ix_notification_intents_expires_at", "notification_intents", ["expires_at"])
    op.create_index("ix_notification_intents_dedupe_key", "notification_intents", ["dedupe_key"])
    op.create_unique_constraint("uq_notification_intent_user_dedupe", "notification_intents", ["user_id", "dedupe_key"])

    op.create_table(
        "push_subscriptions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index("ix_push_subscriptions_status", "push_subscriptions", ["status"])

    op.create_table(
        "push_deliveries",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("notification_intent_id", sa.String(length=36), nullable=False),
        sa.Column("push_subscription_id", sa.String(length=36), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["notification_intent_id"], ["notification_intents.id"]),
        sa.ForeignKeyConstraint(["push_subscription_id"], ["push_subscriptions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"]),
        sa.UniqueConstraint("push_subscription_id", "dedupe_key", name="uq_push_delivery_subscription_dedupe"),
    )
    op.create_index("ix_push_deliveries_user_id", "push_deliveries", ["user_id"])
    op.create_index("ix_push_deliveries_notification_intent_id", "push_deliveries", ["notification_intent_id"])
    op.create_index("ix_push_deliveries_push_subscription_id", "push_deliveries", ["push_subscription_id"])
    op.create_index("ix_push_deliveries_dedupe_key", "push_deliveries", ["dedupe_key"])
    op.create_index("ix_push_deliveries_status", "push_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_push_deliveries_status", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_dedupe_key", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_push_subscription_id", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_notification_intent_id", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_user_id", table_name="push_deliveries")
    op.drop_table("push_deliveries")

    op.drop_index("ix_push_subscriptions_status", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    op.drop_constraint("uq_notification_intent_user_dedupe", "notification_intents", type_="unique")
    op.drop_index("ix_notification_intents_dedupe_key", table_name="notification_intents")
    op.drop_index("ix_notification_intents_expires_at", table_name="notification_intents")
    op.drop_index("ix_notification_intents_status", table_name="notification_intents")
    op.drop_column("notification_intents", "suppressed_reason")
    op.drop_column("notification_intents", "delivered_at")
    op.drop_column("notification_intents", "dedupe_key")
    op.drop_column("notification_intents", "expires_at")
    op.drop_column("notification_intents", "body")
    op.drop_column("notification_intents", "title")

    op.drop_index("ix_outbox_events_available_at", table_name="outbox_events")
    op.drop_column("outbox_events", "processed_at")
    op.drop_column("outbox_events", "locked_at")

    op.drop_index("ix_user_profiles_auth_subject", table_name="user_profiles")
    op.drop_column("user_profiles", "auth_subject")
