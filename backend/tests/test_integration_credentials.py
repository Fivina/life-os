from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, delete, insert, select
from sqlalchemy.exc import SQLAlchemyError

from app.api import routes_integrations
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.integrations.credentials import IntegrationSecretStore
from app.integrations.models import IntegrationConfiguration
from app.integrations.provider_tests import IntegrationConnectionTester
from app.integrations.schemas import CredentialWrite
from app.integrations.service import IntegrationService


KEY = "test-key-never-return-or-log-1234567890"
OTHER_KEY = "replacement-key-never-return-1234567890"
SETTINGS = SimpleNamespace(integration_installation_admin_subjects="trusted-subject")


@pytest.fixture
def user(db_session):
    profile = UserProfile(email="integration@example.test", auth_subject="tenant-subject")
    db_session.add(profile)
    db_session.commit()
    return profile


@pytest.fixture
def integration_client(db_session, user):
    application = FastAPI()
    application.include_router(routes_integrations.router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: db_session
    application.dependency_overrides[get_current_user] = lambda: user
    application.dependency_overrides[get_settings] = lambda: SETTINGS
    with TestClient(application) as client:
        yield client


@pytest.mark.parametrize("payload", [
    {"api_key": "short-private-value"},
    {"api_key": KEY + "\n"},
    {"api_key": {"secret": KEY}},
    {"api_key": KEY, "scope": KEY},
    {"api_key": KEY, "language": KEY},
    {"api_key": KEY, "client_id": KEY},
    {"api_key": KEY, "unexpected": KEY},
])
def test_manual_validation_never_reflects_secret(integration_client, payload):
    response = integration_client.put("/api/v1/settings/integrations/tmdb/credentials", json=payload)
    assert response.status_code == 422
    assert KEY not in response.text
    assert "short-private-value" not in response.text
    assert "input" not in response.text


def test_malformed_json_is_sanitized(integration_client):
    response = integration_client.put("/api/v1/settings/integrations/tmdb/credentials", content='{"api_key":"' + KEY)
    assert response.status_code == 422
    assert KEY not in response.text


def test_sqlite_fails_closed_and_import_status_is_not_connected(integration_client, db_session):
    response = integration_client.put("/api/v1/settings/integrations/tmdb/credentials", json={"api_key": KEY})
    assert response.status_code == 503
    assert KEY not in response.text
    assert db_session.query(IntegrationConfiguration).count() == 0
    status = integration_client.get("/api/v1/settings/integrations").json()
    assert status["credential_management_available"] is False
    providers = {item["id"]: item for item in status["providers"]}
    assert providers["letterboxd"]["kind"] == "import"
    assert providers["letterboxd"]["configured"] is False
    assert providers["tmdb"]["attribution"] == "This product uses the TMDB API but is not endorsed or certified by TMDB."
    for item in providers.values():
        assert item["configured"] is False
        assert item["credential_management_available"] is False
    for provider in ("letterboxd", "wger", "open-food-facts"):
        assert integration_client.put(f"/api/v1/settings/integrations/{provider}/credentials", json={"api_key": KEY}).status_code == 409


def test_authentication_required(db_session):
    application = FastAPI()
    application.include_router(routes_integrations.router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: db_session
    with TestClient(application) as client:
        for method, path in (("get", ""), ("put", "/tmdb/credentials"), ("delete", "/tmdb/credentials"), ("post", "/tmdb/test")):
            assert getattr(client, method)("/api/v1/settings/integrations" + path).status_code == 401


def test_installation_scope_denies_ordinary_users_even_with_claimed_scope(integration_client):
    root = "/api/v1/settings/integrations"
    assert integration_client.put(root + "/tmdb/credentials", json={"api_key": KEY, "scope": "installation"}).status_code == 403
    assert integration_client.delete(root + "/tmdb/credentials?scope=installation").status_code == 403
    assert integration_client.post(root + "/tmdb/test?scope=installation").status_code == 403
    assert integration_client.get(root + "?scope=installation").status_code == 403
    assert integration_client.get(root + "?scope=connection").status_code == 422


class FakePostgres:
    """Record actual SQL calls without a provider or production database."""
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))

    def scalar(self, statement, params=None):
        self.calls.append((str(statement), params))
        if "to_regprocedure" in str(statement):
            return True
        if "get_lifeos" in str(statement):
            return KEY
        return True


def test_openai_reuses_existing_tenant_function_and_namespace(user):
    db = FakePostgres()
    store = IntegrationSecretStore(SETTINGS)
    store.save_scoped(db, user, "openai", KEY)
    assert store.get_scoped(db, user, "openai") == KEY
    writes = [(sql, params) for sql, params in db.calls if "set_lifeos_provider_secret(:" in sql]
    assert len(writes) == 1
    assert writes[0][1] == {"user_id": user.id, "provider": "openai", "secret": KEY}
    assert not any("scoped_provider_secret(:" in sql for sql, _ in db.calls)


def test_scoped_calls_bind_owner_and_reset_admin_context(user):
    admin = SimpleNamespace(id=user.id, auth_subject="trusted-subject")
    db = FakePostgres()
    store = IntegrationSecretStore(SETTINGS)
    store.save_scoped(db, admin, "tmdb", KEY, "installation")
    connection_id = str(uuid4())
    store.save_connection_token(db, user, connection_id, OTHER_KEY)
    store.get_connection_token(db, user, connection_id)
    store.delete_connection_token(db, user, connection_id)
    functions = [(sql, params) for sql, params in db.calls if "scoped_provider_secret(:" in sql]
    assert functions[0][1]["scope"] == "installation"
    for _, params in functions[1:]:
        assert params["scope"] == "connection"
        assert params["user_id"] == user.id
        assert params["provider"] == "plaid"
        assert params["connection_id"] == connection_id
    flags = [params["value"] for sql, params in db.calls if "app.integration_installation_admin" in sql]
    assert flags == ["true", "false", "false", "false"]
    for bad in ("other:connection", "installation", "../../connection", None, str(uuid4()).upper()):
        with pytest.raises(HTTPException) as exc:
            store.save_connection_token(db, user, bad, KEY)
        assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        store.get_scoped(db, user, "tmdb", "installation")
    assert exc.value.status_code == 403


def test_vault_exception_details_are_sanitized(user):
    class FailingDb(FakePostgres):
        def execute(self, statement, params=None):
            if "set_lifeos_provider_secret" in str(statement):
                raise SQLAlchemyError(KEY)
            return super().execute(statement, params)
    with pytest.raises(HTTPException) as exc:
        IntegrationSecretStore(SETTINGS).save_scoped(FailingDb(), user, "tmdb", KEY)
    assert exc.value.status_code == 503
    assert KEY not in str(exc.value.detail)


@pytest.fixture
def injected_vault(db_session):
    # Test-only transactional stand-in. Production SQLite storage remains forbidden.
    table = Table("test_vault", MetaData(), Column("namespace", String, primary_key=True), Column("secret", String))
    table.create(db_session.bind)

    class TransactionalTestStore:
        @staticmethod
        def available(db):
            return True

        @staticmethod
        def namespace(user, provider, scope):
            return f"{scope}:{user.id if scope == 'tenant' else 'installation'}:{provider}"

        def get_scoped(self, db, user, provider, scope="tenant"):
            return db.scalar(select(table.c.secret).where(table.c.namespace == self.namespace(user, provider, scope)))

        def configured_scoped(self, db, user, provider, scope="tenant"):
            return self.get_scoped(db, user, provider, scope) is not None

        def save_scoped(self, db, user, provider, secret, scope="tenant"):
            self.delete_scoped(db, user, provider, scope)
            db.execute(insert(table).values(namespace=self.namespace(user, provider, scope), secret=secret))

        def delete_scoped(self, db, user, provider, scope="tenant"):
            db.execute(delete(table).where(table.c.namespace == self.namespace(user, provider, scope)))

    return TransactionalTestStore()


def test_credential_and_configuration_roll_back_together(db_session, user, injected_vault):
    service = IntegrationService(SETTINGS, store=injected_vault)
    service.save(db_session, user, "tmdb", CredentialWrite(api_key=KEY, language="en-US", region="US"))
    db_session.commit()
    service.save(db_session, user, "tmdb", CredentialWrite(api_key=OTHER_KEY, language="de-DE"))
    db_session.rollback()
    assert injected_vault.get_scoped(db_session, user, "tmdb") == KEY
    row = db_session.get(IntegrationConfiguration, ("tenant", user.id, "tmdb"))
    assert row.language == "en-US"
    service.delete(db_session, user, "tmdb")
    db_session.rollback()
    assert injected_vault.get_scoped(db_session, user, "tmdb") == KEY
    service.delete(db_session, user, "tmdb")
    db_session.commit()
    assert injected_vault.get_scoped(db_session, user, "tmdb") is None
    assert db_session.get(IntegrationConfiguration, ("tenant", user.id, "tmdb")).language == "en-US"


def test_route_transaction_errors_are_sanitized_and_rolled_back(integration_client, db_session, user, injected_vault, monkeypatch):
    from app.integrations import service as module
    monkeypatch.setattr(module, "IntegrationSecretStore", lambda settings: injected_vault)
    real_commit = db_session.commit
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError(KEY)))
    response = integration_client.put("/api/v1/settings/integrations/tmdb/credentials", json={"api_key": KEY})
    assert response.status_code == 503
    assert KEY not in response.text
    monkeypatch.setattr(db_session, "commit", real_commit)
    assert injected_vault.get_scoped(db_session, user, "tmdb") is None
    assert db_session.query(IntegrationConfiguration).count() == 0


def test_tenant_and_installation_configuration_are_separate(db_session, user, injected_vault):
    second = UserProfile(email="second@example.test", auth_subject="other-subject")
    db_session.add(second)
    db_session.commit()
    admin = SimpleNamespace(id=user.id, auth_subject="trusted-subject")
    service = IntegrationService(SETTINGS, store=injected_vault)
    service.save(db_session, user, "tmdb", CredentialWrite(api_key=KEY, language="en-US"))
    service.save(db_session, admin, "tmdb", CredentialWrite(api_key=OTHER_KEY, scope="installation", language="de-DE"))
    db_session.commit()
    assert injected_vault.get_scoped(db_session, second, "tmdb") is None
    tenant = next(p for p in service.list(db_session, second).providers if p.id == "tmdb")
    assert tenant.configured is False
    assert tenant.language is None
    assert next(p for p in service.list(db_session, admin, "installation").providers if p.id == "tmdb").language == "de-DE"
    assert injected_vault.get_scoped(db_session, user, "tmdb") == KEY
    with pytest.raises(HTTPException) as exc:
        service.save(db_session, second, "tmdb", CredentialWrite(api_key=KEY, scope="installation"))
    assert exc.value.status_code == 403


@pytest.mark.parametrize("provider,payload,path,header", [
    ("tmdb", {"images": {}}, "/3/configuration", "authorization"),
    ("api-football", {"errors": [], "response": {}}, "/status", "x-apisports-key"),
    ("usda", [], "/fdc/v1/foods/list", "x-api-key"),
    ("plaid", {"institutions": []}, "/institutions/get", "plaid-secret"),
    ("openai", {"data": []}, "/v1/models", "authorization"),
])
def test_connection_adapters_are_bounded_and_use_header_secrets(provider, payload, path, header):
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.path == path
        assert KEY in request.headers[header]
        assert KEY not in str(request.url)
        assert KEY.encode() not in request.content
        assert request.extensions["timeout"]["read"] == 10.0
        if provider == "plaid":
            assert request.url.host == "sandbox.plaid.com"
            assert b'"count":1' in request.content
        return httpx.Response(200, json=payload)
    tester = IntegrationConnectionTester(transport=httpx.MockTransport(handle))
    assert tester.test(provider, KEY, environment="sandbox", client_id="a" * 24) is None
    assert len(calls) == 1


@pytest.mark.parametrize("status,code", [(401, "authentication_failed"), (403, "authentication_failed"), (429, "rate_limited"), (503, "provider_unavailable"), (302, "provider_rejected"), (400, "provider_rejected")])
def test_provider_errors_never_return_body(status, code):
    tester = IntegrationConnectionTester(transport=httpx.MockTransport(lambda request: httpx.Response(status, text=KEY)))
    assert tester.test("tmdb", KEY, environment="sandbox") == code


def test_provider_application_errors_timeout_and_large_response_are_sanitized():
    error = IntegrationConnectionTester(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"errors": {"token": KEY}, "response": {}})))
    assert error.test("api-football", KEY, environment="sandbox") == "provider_rejected"
    def timeout(request):
        raise httpx.ReadTimeout(KEY, request=request)
    assert IntegrationConnectionTester(transport=httpx.MockTransport(timeout)).test("tmdb", KEY, environment="sandbox") == "timeout"
    large = IntegrationConnectionTester(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 262145)))
    assert large.test("tmdb", KEY, environment="sandbox") == "invalid_response"
    assert IntegrationConnectionTester().test("plaid", KEY, environment="sandbox") == "client_id_required"


def test_test_metadata_is_durable_and_bank_production_not_enabled(db_session, user, injected_vault):
    tester = IntegrationConnectionTester(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"institutions": []})))
    service = IntegrationService(SETTINGS, store=injected_vault, tester=tester)
    service.save(db_session, user, "plaid", CredentialWrite(api_key=KEY, client_id="a" * 24, environment="production"))
    db_session.commit()
    result = service.test(db_session, user, "plaid")
    db_session.commit()
    assert result.success
    status = next(item for item in service.list(db_session, user).providers if item.id == "plaid")
    assert status.last_attempt_at is not None
    assert status.last_success_at is not None
    assert status.capabilities == ["credential_test"]
    assert "enabled" not in status.model_dump()
    assert KEY not in status.model_dump_json()
    service.save(db_session, user, "plaid", CredentialWrite(api_key=OTHER_KEY))
    db_session.commit()
    row = db_session.get(IntegrationConfiguration, ("tenant", user.id, "plaid"))
    assert row.last_success_at is None
    assert row.client_id == "a" * 24
    assert row.environment == "production"


def test_sqlite_additive_migration_round_trip():
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect
    migration = importlib.import_module("migrations.versions.0031_integration_credentials")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        original = migration.op
        migration.op = Operations(MigrationContext.configure(connection))
        try:
            migration.upgrade()
            columns = {item["name"] for item in inspect(connection).get_columns("integration_configurations")}
            assert "client_id" in columns
            assert not {"api_key", "secret", "token", "encrypted_secret"} & columns
            migration.downgrade()
            assert "integration_configurations" not in inspect(connection).get_table_names()
        finally:
            migration.op = original
