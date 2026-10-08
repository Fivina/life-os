"""Permit daily fixture sync while retaining legacy fourteen-day rules."""
from alembic import op
import sqlalchemy as sa

revision = "0032_daily_fixture_cadence"
down_revision = "0031_integration_credentials"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("standing_calendar_rules") as batch:
        batch.drop_constraint("ck_standing_rules_sync_interval", type_="check")
        batch.create_check_constraint("ck_standing_rules_sync_interval", "sync_interval_days IN (1, 14)")


def downgrade():
    rules = sa.table("standing_calendar_rules", sa.column("sync_interval_days", sa.Integer))
    op.execute(rules.update().where(rules.c.sync_interval_days == 1).values(sync_interval_days=14))
    with op.batch_alter_table("standing_calendar_rules") as batch:
        batch.drop_constraint("ck_standing_rules_sync_interval", type_="check")
        batch.create_check_constraint("ck_standing_rules_sync_interval", "sync_interval_days = 14")
