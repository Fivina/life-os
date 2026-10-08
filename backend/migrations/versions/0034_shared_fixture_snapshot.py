"""Add a backend-only normalized fixture snapshot cache.

Revision ID: 0034_shared_fixture_snapshot
Revises: 0033_fixture_runtime_secret
"""
from alembic import op
import sqlalchemy as sa


revision = "0034_shared_fixture_snapshot"
down_revision = "0033_fixture_runtime_secret"
branch_labels = None
depends_on = None

API_ROLES = "PUBLIC, anon, authenticated, service_role"


def upgrade() -> None:
    op.create_table(
        "fixture_snapshot_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("team_id", sa.String(80), nullable=False),
        sa.Column("base_url_hash", sa.String(64), nullable=False),
        sa.Column("fixtures_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fixture_snapshot_cache_expires_at", "fixture_snapshot_cache", ["expires_at"])
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"REVOKE ALL ON TABLE public.fixture_snapshot_cache FROM {API_ROLES}")
    op.execute("ALTER TABLE public.fixture_snapshot_cache ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_fixture_snapshot_cache_expires_at", table_name="fixture_snapshot_cache")
    op.drop_table("fixture_snapshot_cache")
