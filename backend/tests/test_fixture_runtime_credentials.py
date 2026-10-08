from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.integrations.credentials import IntegrationSecretStore
from app.standing_calendar.service import ensure_besiktas_rule, sync_rule


class RuntimeDb:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def __init__(self, *, ready=True, secret="synthetic-sports-value", fail=False):
        self.ready, self.secret, self.fail = ready, secret, fail
        self.calls = []

    def scalar(self, statement, params=None):
        self.calls.append((str(statement), params))
        if self.fail:
            raise SQLAlchemyError("sensitive-provider-payload")
        return self.ready if "to_regprocedure" in str(statement) else self.secret


def test_installation_runtime_lookup_does_not_grant_user_management_rights():
    settings = Settings(_env_file=None)
    store = IntegrationSecretStore(settings)
    user = SimpleNamespace(id="ordinary-user", auth_subject="ordinary-subject")
    db = RuntimeDb()
    assert store.fixture_runtime_key(db, user, "installation") == "synthetic-sports-value"
    assert len(db.calls) == 2
    assert all(params is None for _, params in db.calls)
    assert not any("set_config" in sql for sql, _ in db.calls)
    with pytest.raises(HTTPException) as error:
        store.get_scoped(db, user, "api-football", "installation")
    assert error.value.status_code == 403


def test_runtime_missing_function_fails_closed_and_error_is_sanitized():
    store = IntegrationSecretStore(Settings(_env_file=None))
    for db in (RuntimeDb(ready=False), RuntimeDb(fail=True)):
        with pytest.raises(HTTPException) as error:
            store.fixture_runtime_key(db, None, "installation")
        assert error.value.status_code == 503
        assert "sensitive-provider-payload" not in str(error.value.detail)


def test_runtime_selected_scope_never_falls_back(db_session, monkeypatch):
    store = IntegrationSecretStore(Settings(_env_file=None))
    assert store.fixture_runtime_key(db_session, None, "installation") is None
    assert store.fixture_runtime_key(RuntimeDb(secret=None), None, "installation") is None
    monkeypatch.setattr(store, "configured_scoped", lambda *_: False)
    monkeypatch.setattr(store, "get_scoped", lambda *_: pytest.fail("No tenant key is configured"))
    assert store.fixture_runtime_key(RuntimeDb(), None, "tenant") is None


def test_sync_rereads_vault_and_removal_prevents_environment_fallback(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    settings = Settings(_env_file=None, api_football_api_key="legacy-env-value")
    rule = ensure_besiktas_rule(db_session, user, settings=settings)
    current = ["synthetic-vault-value"]
    looked_up = []
    provider_keys = []
    def lookup(self, db, owner, scope):
        looked_up.append((owner.id, scope))
        return current[0]
    class Provider:
        def fetch(self, **kwargs):
            return []
    def configure(runtime_settings):
        provider_keys.append(runtime_settings.api_football_api_key)
        if not runtime_settings.api_football_api_key:
            from app.standing_calendar.providers import FixtureProviderError
            raise FixtureProviderError("API_FOOTBALL_API_KEY is not configured.")
        return Provider()
    monkeypatch.setattr(IntegrationSecretStore, "fixture_runtime_key", lookup)
    monkeypatch.setattr("app.standing_calendar.service.configured_provider", configure)
    assert sync_rule(db_session, user, rule, settings=settings).status == "SUCCESS"
    current[0] = None
    assert sync_rule(db_session, user, rule, settings=settings).status == "FAILED"
    assert provider_keys == ["synthetic-vault-value", None]
    assert looked_up == [(user.id, "installation"), (user.id, "installation")]
    assert settings.api_football_api_key == "legacy-env-value"


def test_sync_unexpected_errors_never_expose_secret(db_session, monkeypatch, caplog):
    user = get_or_create_user(db_session)
    settings = Settings(_env_file=None)
    rule = ensure_besiktas_rule(db_session, user, settings=settings)
    def fail(*_args):
        raise RuntimeError("sensitive-provider-payload")
    monkeypatch.setattr(IntegrationSecretStore, "fixture_runtime_key", fail)
    result = sync_rule(db_session, user, rule, settings=settings)
    assert result.status == "FAILED"
    assert "sensitive-provider-payload" not in result.model_dump_json()
    assert "sensitive-provider-payload" not in rule.last_error
    assert "sensitive-provider-payload" not in caplog.text


def test_sync_rolls_back_partial_calendar_mutation_and_can_save_failure(db_session, monkeypatch):
    from app.database.models import Commitment, FixtureBinding
    from tests.test_next_fixture_sync import normalized_fixture, RecordingProvider
    from app.standing_calendar import service
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user)
    db_session.commit()
    reconcile = service.reconcile_fixture
    def fail_after_write(*args, **kwargs):
        reconcile(*args, **kwargs)
        raise SQLAlchemyError("sensitive-provider-payload")
    monkeypatch.setattr(service, "reconcile_fixture", fail_after_write)
    result = sync_rule(db_session, user, rule, provider=RecordingProvider([normalized_fixture()]))
    assert result.status == "FAILED"
    db_session.commit()
    assert db_session.query(Commitment).count() == db_session.query(FixtureBinding).count() == 0
    assert rule.last_sync_status == "FAILED"


def test_authorized_tbd_commitment_read_is_nullable_and_tenant_isolated(client, db_session):
    from app.database.models import Commitment, UserProfile
    from app.standing_calendar.service import reconcile_fixture
    from tests.test_next_fixture_sync import normalized_fixture, NOW
    from tests.conftest import AUTH_HEADERS
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user)
    fixture = normalized_fixture().model_copy(update={"kickoff_at": None, "raw_status": "TBD"})
    reconcile_fixture(db_session, user, rule, fixture, now=NOW)
    db_session.commit()
    own = db_session.query(Commitment).one()
    response = client.get(f"/api/v1/commitments/{own.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["starts_at"] is None and response.json()["ends_at"] is None
    other = UserProfile(email="other-fixture@example.test", auth_subject="other-fixture-subject")
    db_session.add(other)
    db_session.flush()
    own.user_id = other.id
    db_session.commit()
    assert client.get(f"/api/v1/commitments/{own.id}", headers=AUTH_HEADERS).status_code == 404
    assert client.get(f"/api/v1/commitments/{own.id}").status_code == 401


def test_runtime_migration_grants_only_fixed_backend_read():
    import importlib
    migration = importlib.import_module("migrations.versions.0033_fixture_runtime_secret")
    calls = []
    class Ops:
        def get_bind(self):
            return RuntimeDb.bind
        def execute(self, sql):
            calls.append(sql)
    original = migration.op
    migration.op = Ops()
    try:
        migration.upgrade()
    finally:
        migration.op = original
    assert "SECURITY DEFINER" in calls[0] and "SET search_path = pg_catalog, vault" in calls[0]
    assert "lifeos:installation:api-football" in calls[0]
    assert "FROM PUBLIC, anon, authenticated, service_role" in calls[1]
    assert calls[2].endswith("TO CURRENT_USER")
    assert "p_provider" not in calls[0]
