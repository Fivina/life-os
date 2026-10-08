from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.config import Settings
from app.database.models import UserProfile
from app.integrations.credentials import IntegrationSecretStore
from app.standing_calendar.models import FixtureSnapshotCache
from app.standing_calendar.service import FixtureSyncWorker, ensure_besiktas_rule, sync_rule
from tests.test_next_fixture_sync import RecordingProvider, normalized_fixture


NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def _user(db, number: int) -> UserProfile:
    user = UserProfile(email=f"snapshot-{number}@example.test", auth_subject=f"snapshot-subject-{number}")
    db.add(user)
    db.flush()
    return user


def _settings(*, scope: str = "installation", base_url: str = "https://fixtures.example/v3") -> Settings:
    return Settings(
        _env_file=None,
        fixture_credential_scope=scope,
        api_football_base_url=base_url,
        api_football_api_key="synthetic-test-key",
    )


class NeverFetchProvider:
    provider_id = "api_football"

    def fetch(self, **_kwargs):
        raise AssertionError("a fresh shared snapshot should avoid a provider call")


def test_two_installation_users_share_one_scheduled_fetch(db_session):
    _user(db_session, 1)
    _user(db_session, 2)
    provider = RecordingProvider([normalized_fixture()])

    processed = FixtureSyncWorker().run_due(db_session, now=NOW, provider=provider)

    assert processed == 2
    assert provider.calls == [{"team_id": "549"}]
    assert db_session.query(FixtureSnapshotCache).count() == 1


def test_manual_refresh_updates_snapshot_and_next_scheduled_sync_reuses_it(db_session):
    first_user, second_user = _user(db_session, 1), _user(db_session, 2)
    settings = _settings()
    first_rule = ensure_besiktas_rule(db_session, first_user, settings=settings, now=NOW)
    second_rule = ensure_besiktas_rule(db_session, second_user, settings=settings, now=NOW)
    refreshed = normalized_fixture(fixture_id="9002", raw_hash="new")

    manual = sync_rule(
        db_session, first_user, first_rule,
        provider=RecordingProvider([refreshed]), settings=settings, now=NOW,
    )
    scheduled = sync_rule(
        db_session, second_user, second_rule,
        provider=NeverFetchProvider(), settings=settings, now=NOW + timedelta(minutes=5),
        use_shared_cache=True,
    )

    snapshot = db_session.query(FixtureSnapshotCache).one()
    assert manual.fetched == scheduled.fetched == 1
    assert snapshot.fixtures_json[0]["source_fixture_id"] == "9002"
    assert second_rule.metadata_json["current_next_fixture_id"] == "9002"


def test_tenant_scope_bypasses_shared_snapshot(db_session):
    settings = _settings(scope="tenant")
    provider = RecordingProvider([normalized_fixture()])
    for number in (1, 2):
        user = _user(db_session, number)
        rule = ensure_besiktas_rule(db_session, user, settings=settings, now=NOW)
        assert sync_rule(
            db_session, user, rule, provider=provider, settings=settings, now=NOW,
            use_shared_cache=True,
        ).status == "SUCCESS"

    assert provider.calls == [{"team_id": "549"}, {"team_id": "549"}]
    assert db_session.query(FixtureSnapshotCache).count() == 0


def test_successful_empty_snapshot_is_reused(db_session):
    settings = _settings()
    first_user, second_user = _user(db_session, 1), _user(db_session, 2)
    first_rule = ensure_besiktas_rule(db_session, first_user, settings=settings, now=NOW)
    second_rule = ensure_besiktas_rule(db_session, second_user, settings=settings, now=NOW)

    sync_rule(db_session, first_user, first_rule, provider=RecordingProvider([]), settings=settings, now=NOW)
    result = sync_rule(
        db_session, second_user, second_rule, provider=NeverFetchProvider(), settings=settings,
        now=NOW + timedelta(hours=1), use_shared_cache=True,
    )

    assert result.status == "SUCCESS" and result.fetched == 0
    assert db_session.query(FixtureSnapshotCache).one().fixtures_json == []


def test_expired_snapshot_is_refetched(db_session):
    settings = _settings()
    user = _user(db_session, 1)
    rule = ensure_besiktas_rule(db_session, user, settings=settings, now=NOW)
    initial = RecordingProvider([normalized_fixture()])
    replacement = RecordingProvider([normalized_fixture(fixture_id="9002", raw_hash="new")])
    sync_rule(db_session, user, rule, provider=initial, settings=settings, now=NOW)

    result = sync_rule(
        db_session, user, rule, provider=replacement, settings=settings,
        now=NOW + timedelta(days=1), use_shared_cache=True,
    )

    assert result.status == "SUCCESS"
    assert replacement.calls == [{"team_id": "549"}]
    assert db_session.query(FixtureSnapshotCache).one().fixtures_json[0]["source_fixture_id"] == "9002"


def test_vault_is_read_before_cache_hit_and_removal_fails_closed(db_session, monkeypatch):
    settings = _settings()
    user = _user(db_session, 1)
    rule = ensure_besiktas_rule(db_session, user, settings=settings, now=NOW)
    secrets = [None]
    lookups = []

    def lookup(self, db, owner, scope):
        lookups.append((owner.id, scope))
        return secrets[0]

    monkeypatch.setattr(IntegrationSecretStore, "fixture_runtime_key", lookup)
    assert sync_rule(
        db_session, user, rule, provider=RecordingProvider([normalized_fixture()]),
        settings=settings, now=NOW,
    ).status == "SUCCESS"

    result = sync_rule(
        db_session, user, rule, settings=settings,
        now=NOW + timedelta(hours=1), use_shared_cache=True,
    )

    assert result.status == "FAILED"
    assert lookups == [(user.id, "installation")]


def test_failed_reconciliation_rolls_back_snapshot_refresh_and_pointer(db_session, monkeypatch):
    from app.standing_calendar import service

    settings = _settings()
    user = _user(db_session, 1)
    rule = ensure_besiktas_rule(db_session, user, settings=settings, now=NOW)
    sync_rule(
        db_session, user, rule, provider=RecordingProvider([normalized_fixture()]),
        settings=settings, now=NOW,
    )
    db_session.commit()
    reconcile = service.reconcile_fixture

    def fail_after_reconcile(*args, **kwargs):
        reconcile(*args, **kwargs)
        raise sa.exc.SQLAlchemyError("synthetic reconciliation failure")

    monkeypatch.setattr(service, "reconcile_fixture", fail_after_reconcile)
    result = sync_rule(
        db_session, user, rule,
        provider=RecordingProvider([normalized_fixture(fixture_id="9002", raw_hash="new")]),
        settings=settings, now=NOW + timedelta(hours=1),
    )
    db_session.commit()
    snapshot = db_session.query(FixtureSnapshotCache).one()

    assert result.status == "FAILED"
    assert snapshot.fixtures_json[0]["source_fixture_id"] == "9001"
    assert rule.metadata_json["current_next_fixture_id"] == "9001"


def test_snapshot_migration_supports_sqlite_roundtrip():
    migration = importlib.import_module("migrations.versions.0034_shared_fixture_snapshot")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        original = migration.op
        migration.op = Operations(MigrationContext.configure(connection))
        try:
            migration.upgrade()
            columns = {column["name"] for column in sa.inspect(connection).get_columns("fixture_snapshot_cache")}
            assert columns == {
                "cache_key", "provider", "team_id", "base_url_hash",
                "fixtures_json", "fetched_at", "expires_at",
            }
            migration.downgrade()
            assert not sa.inspect(connection).has_table("fixture_snapshot_cache")
        finally:
            migration.op = original


def test_snapshot_migration_revokes_direct_data_api_access():
    migration = importlib.import_module("migrations.versions.0034_shared_fixture_snapshot")
    calls = []

    class Ops:
        def create_table(self, *_args, **_kwargs):
            pass

        def create_index(self, *_args, **_kwargs):
            pass

        def get_bind(self):
            return type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()

        def execute(self, sql):
            calls.append(sql)

    original = migration.op
    migration.op = Ops()
    try:
        migration.upgrade()
    finally:
        migration.op = original

    assert calls == [
        "REVOKE ALL ON TABLE public.fixture_snapshot_cache FROM PUBLIC, anon, authenticated, service_role",
        "ALTER TABLE public.fixture_snapshot_cache ENABLE ROW LEVEL SECURITY",
    ]
