"""Add v1.9B quick capture, global review queue, and intelligence settings.

Revision ID: 0027_capture_review_settings
Revises: 0026_chef_meal_intent
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_capture_review_settings"
down_revision = "0026_chef_meal_intent"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "user_intelligence_settings",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("proactivity_mode", sa.String(20), nullable=False),
        sa.Column("memory_visible", sa.Boolean(), nullable=False),
        sa.Column("patterns_visible", sa.Boolean(), nullable=False),
        sa.Column("passive_suggestions_enabled", sa.Boolean(), nullable=False),
        sa.Column("questions_enabled", sa.Boolean(), nullable=False),
        sa.Column("interruptions_enabled", sa.Boolean(), nullable=False),
        sa.Column("prospective_resurfacing_enabled", sa.Boolean(), nullable=False),
        sa.Column("opportunity_suggestions_enabled", sa.Boolean(), nullable=False),
        sa.Column("monthly_ai_budget_eur", sa.Float()),
        sa.Column("disabled_skills_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_user_intelligence_settings_user_id", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_intelligence_settings_user_id"),
        sa.CheckConstraint("proactivity_mode IN ('QUIET', 'BALANCED', 'PROACTIVE')", name="ck_intelligence_settings_proactivity"),
        sa.CheckConstraint("monthly_ai_budget_eur IS NULL OR monthly_ai_budget_eur >= 0", name="ck_intelligence_settings_budget"),
    )
    op.create_index("ix_user_intelligence_settings_user_id", "user_intelligence_settings", ["user_id"], unique=True)
    op.create_index("ix_user_intelligence_settings_proactivity_mode", "user_intelligence_settings", ["proactivity_mode"])

    op.create_table(
        "quick_captures",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source_conversation_id", sa.String(36)),
        sa.Column("source_message_id", sa.String(36)),
        sa.Column("source_workspace_id", sa.String(36)),
        sa.Column("interpreted_domain", sa.String(60), nullable=False),
        sa.Column("intent_type", sa.String(80), nullable=False),
        sa.Column("target_entity_type", sa.String(80)),
        sa.Column("target_entity_id", sa.String(36)),
        sa.Column("structured_payload_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("ambiguity_flags_json", sa.JSON(), nullable=False),
        sa.Column("consequence_level", sa.String(20), nullable=False),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("policy_outcome", sa.String(40), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("interpreter_provider", sa.String(80), nullable=False),
        sa.Column("interpreter_model", sa.String(160)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("review_item_id", sa.String(36)),
        sa.Column("expected_world_revision", sa.Integer(), nullable=False),
        sa.Column("canonical_entity_type", sa.String(80)),
        sa.Column("canonical_entity_id", sa.String(36)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("trace_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_quick_captures_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["conversation_threads.id"], name="fk_quick_captures_conversation_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"], name="fk_quick_captures_message_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_workspace_id"], ["active_workspaces.id"], name="fk_quick_captures_workspace_id", ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_quick_captures_user_idempotency"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_quick_captures_confidence"),
        sa.CheckConstraint("consequence_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_quick_captures_consequence"),
        sa.CheckConstraint("policy_outcome IN ('APPLY', 'REQUEST_CONFIRMATION', 'SEND_TO_REVIEW', 'REJECT_INVALID', 'NOOP_DUPLICATE')", name="ck_quick_captures_policy_outcome"),
    )
    for column in ("user_id", "status", "source_conversation_id", "source_message_id", "source_workspace_id", "interpreted_domain", "intent_type", "target_entity_type", "target_entity_id", "consequence_level", "policy_outcome", "review_item_id", "canonical_entity_id"):
        op.create_index(f"ix_quick_captures_{column}", "quick_captures", [column])
    op.create_index("ix_quick_captures_user_status_created", "quick_captures", ["user_id", "status", "created_at"])

    op.create_table(
        "review_items",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("review_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("source_ref", sa.String(160), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("candidate_values_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("ambiguity_reasons_json", sa.JSON(), nullable=False),
        sa.Column("affected_domain", sa.String(60), nullable=False),
        sa.Column("target_entity_type", sa.String(80)),
        sa.Column("target_entity_id", sa.String(36)),
        sa.Column("resolution_json", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(60)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", sa.String(120)),
        sa.Column("expected_world_revision", sa.Integer()),
        sa.Column("expected_target_version", sa.Integer()),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], name="fk_review_items_user_id", ondelete="CASCADE"),
        sa.CheckConstraint("priority >= 0 AND priority <= 100", name="ck_review_items_priority"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_review_items_confidence"),
        sa.CheckConstraint("status IN ('PENDING', 'RESOLVED', 'DISMISSED', 'EXPIRED', 'SUPERSEDED')", name="ck_review_items_status"),
    )
    for column in ("user_id", "review_type", "status", "priority", "source", "source_ref", "expires_at", "affected_domain", "target_entity_type", "target_entity_id", "correlation_id"):
        op.create_index(f"ix_review_items_{column}", "review_items", [column])
    op.create_index("ix_review_items_user_status_priority", "review_items", ["user_id", "status", "priority", "created_at"])
    op.create_index("ix_review_items_active_fingerprint", "review_items", ["user_id", "fingerprint", "status"])


def downgrade() -> None:
    op.drop_table("review_items")
    op.drop_table("quick_captures")
    op.drop_table("user_intelligence_settings")
