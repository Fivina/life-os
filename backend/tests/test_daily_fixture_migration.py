import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_daily_cadence_migration_preserves_rules_and_restores_legacy_constraint():
    migration = importlib.import_module("migrations.versions.0032_daily_fixture_cadence")
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    rules = sa.Table("standing_calendar_rules", metadata,
                     sa.Column("id", sa.String, primary_key=True),
                     sa.Column("sync_interval_days", sa.Integer, nullable=False),
                     sa.CheckConstraint("sync_interval_days = 14", name="ck_standing_rules_sync_interval"))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(rules.insert().values(id="existing", sync_interval_days=14))
        original = migration.op
        migration.op = Operations(MigrationContext.configure(connection))
        try:
            migration.upgrade()
            assert connection.scalar(sa.select(rules.c.sync_interval_days)) == 14
            connection.execute(rules.update().values(sync_interval_days=1))
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(rules.insert().values(id="unsupported", sync_interval_days=2))
            migration.downgrade()
            assert connection.execute(sa.select(rules)).one() == ("existing", 14)
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(rules.update().values(sync_interval_days=1))
        finally:
            migration.op = original
