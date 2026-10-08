from __future__ import annotations

import asyncio
import threading

import httpx
import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from sqlalchemy import Column, MetaData, String, Table, TextClause, delete, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import routes_intelligence_settings
from app.api.deps import get_or_create_user
from app.agents.catalog import DEFAULT_AGENT_MODELS
from app.database.session import get_db
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.provider_models import ProviderModelCatalog
from app.main import app
from tests.conftest import AUTH_HEADERS


def test_provider_secret_store_sets_transaction_local_user_context_before_secret_calls():
    from app.intelligence_settings.provider_credentials import ProviderSecretStore

    class FakeDb:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __init__(self):
            self.calls = []

        def scalar(self, statement, params=None):
            sql = str(statement)
            self.calls.append((sql, params))
            if "to_regprocedure" in sql:
                return True
            if "private.has_lifeos_provider_secret" in sql:
                return True
            if "private.get_lifeos_provider_secret" in sql:
                return "stored-secret-value"
            raise AssertionError(f"Unexpected scalar query: {sql}")

        def execute(self, statement, params=None):
            assert isinstance(statement, TextClause)
            self.calls.append((str(statement), params))

    user = SimpleNamespace(id="user-123")
    key = "sk-test-key-that-is-long-enough-123456"
    store = ProviderSecretStore()

    for action in (
        lambda db: store.configured(db, user, "openai"),
        lambda db: store.get(db, user, "openai"),
        lambda db: store.save(db, user, "openai", key),
        lambda db: store.delete(db, user, "openai"),
    ):
        db = FakeDb()
        action(db)
        context_index = next(i for i, (sql, _) in enumerate(db.calls) if "set_config('app.user_id'" in sql)
        function_index = next(
            i for i, (sql, _) in enumerate(db.calls)
            if "private." in sql and "to_regprocedure" not in sql
        )
        assert context_index < function_index
        assert db.calls[context_index][1] == {"user_id": user.id}


def test_provider_credentials_are_write_only_and_fail_closed_until_vault_is_ready(client):
    key = "sk-proj-test-key-that-must-never-be-returned-123456"
    response = client.put(
        "/api/v1/settings/intelligence/providers/openai/credential",
        headers=AUTH_HEADERS,
        json={"api_key": key},
    )
    assert response.status_code == 503
    assert key not in response.text
    assert "Hosted secret storage" in response.text

    malformed = client.put(
        "/api/v1/settings/intelligence/providers/openai/credential",
        headers=AUTH_HEADERS,
        json={"api_key": "short-key-not-valid"},
    )
    assert malformed.status_code == 422
    assert "short-key-not-valid" not in malformed.text

    jev_key = "jev-test-key-that-must-never-be-returned-123456"
    jev_response = client.put(
        "/api/v1/settings/intelligence/providers/jev/credential",
        headers=AUTH_HEADERS,
        json={"api_key": jev_key},
    )
    assert jev_response.status_code == 503
    assert "Unsupported provider" not in jev_response.text
    assert jev_key not in jev_response.text


def test_provider_secret_routes_require_authentication(client):
    response = client.put(
        "/api/v1/settings/intelligence/providers/gemini/credential",
        json={"api_key": "AIza-test-key-that-is-long-enough-123456"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token."


def test_async_credential_save_runs_database_work_off_the_event_loop(monkeypatch):
    event_loop_thread = threading.get_ident()
    calls = []

    class Request:
        async def json(self):
            return {"api_key": "sk-test-key-that-is-long-enough-123456"}

    class Db:
        def commit(self):
            calls.append(("commit", threading.get_ident()))

    def save(self, db, user, provider, api_key):
        calls.append(("save", threading.get_ident()))

    monkeypatch.setattr(ProviderSecretStore, "save", save)
    result = asyncio.run(routes_intelligence_settings.save_provider_credential(
        "openai", Request(), Db(), SimpleNamespace(id="user-123"),
    ))

    assert result.configured is True
    assert [name for name, _ in calls] == ["save", "commit"]
    assert all(thread_id != event_loop_thread for _, thread_id in calls)
    assert calls[0][1] == calls[1][1]


@pytest.mark.parametrize("action", ["save", "delete"])
def test_credential_routes_rollback_and_sanitize_commit_failures(monkeypatch, action):
    key = "sk-test-key-that-is-long-enough-123456"

    class Request:
        async def json(self):
            return {"api_key": key}

    class Db:
        rolled_back = False

        def commit(self):
            raise SQLAlchemyError(f"Database error echoed {key}")

        def rollback(self):
            self.rolled_back = True

    monkeypatch.setattr(ProviderSecretStore, "save", lambda *args: None)
    monkeypatch.setattr(ProviderSecretStore, "delete", lambda *args: None)
    db = Db()
    user = SimpleNamespace(id="user-123")
    with pytest.raises(HTTPException) as error:
        if action == "save":
            asyncio.run(routes_intelligence_settings.save_provider_credential("openai", Request(), db, user))
        else:
            routes_intelligence_settings.delete_provider_credential("openai", db, user)

    assert error.value.status_code == 503
    assert key not in error.value.detail
    assert db.rolled_back is True


@pytest.mark.parametrize("provider", ["openai", "gemini", "jev"])
def test_credential_writes_commit_before_fresh_request_reads(client, db_session, monkeypatch, provider):
    get_or_create_user(db_session)
    engine = db_session.get_bind()
    credentials = Table(
        "test_credential_presence", MetaData(),
        Column("user_id", String, primary_key=True),
        Column("provider", String, primary_key=True),
    )
    credentials.create(engine)

    def request_db():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    # Substitute Vault with a transactional presence marker, never a stored key.
    def save(self, db, user, provider, api_key):
        db.execute(insert(credentials).values(user_id=user.id, provider=provider))

    def remove(self, db, user, provider):
        db.execute(delete(credentials).where(
            credentials.c.user_id == user.id, credentials.c.provider == provider,
        ))

    def configured(self, db, user, provider):
        return db.scalar(select(credentials.c.provider).where(
            credentials.c.user_id == user.id, credentials.c.provider == provider,
        )) is not None

    app.dependency_overrides[get_db] = request_db
    monkeypatch.setattr(ProviderSecretStore, "available", staticmethod(lambda db: True))
    monkeypatch.setattr(ProviderSecretStore, "provider_available", lambda *args: True)
    monkeypatch.setattr(ProviderSecretStore, "save", save)
    monkeypatch.setattr(ProviderSecretStore, "delete", remove)
    monkeypatch.setattr(ProviderSecretStore, "configured", configured)
    key = "sk-test-key-that-is-long-enough-123456"
    response = client.put(
        f"/api/v1/settings/intelligence/providers/{provider}/credential",
        headers=AUTH_HEADERS, json={"api_key": key},
    )
    assert response.status_code == 200
    assert response.json() == {"provider": provider, "configured": True}
    assert key not in response.text

    for _ in range(2):
        surface = client.get("/api/v1/settings/intelligence", headers=AUTH_HEADERS)
        assert surface.status_code == 200
        state = next(item for item in surface.json()["providers"] if item["id"] == provider and "credential_configured" in item)
        assert state["credential_configured"] is True
        assert key not in surface.text

    response = client.delete(
        f"/api/v1/settings/intelligence/providers/{provider}/credential", headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"provider": provider, "configured": False}
    with Session(engine) as db:
        assert db.scalar(select(credentials.c.provider)) is None


def test_settings_surface_shows_agent_catalog_but_never_provider_secrets(client):
    response = client.get("/api/v1/settings/intelligence", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["credential_management_available"] is False
    assert {agent["skill_name"] for agent in payload["agents"]}
    assert all(agent["credential_configured"] is False for agent in payload["agents"])
    assert "api_key" not in str(payload).lower()
    jev = next(provider for provider in payload["providers"] if provider["id"] == "jev")
    assert jev["kind"] == "decision"
    assert jev["credential_configured"] is False
    assert "jev-latest" in jev["models"]


def test_provider_model_catalog_filters_results_and_never_returns_keys(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    requested = {}

    class Secrets:
        def get(self, _db, _user, provider):
            assert provider == "openai"
            return "sk-secret-do-not-return-to-ui"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [
                {"id": "gpt-5-mini"}, {"id": "text-embedding-3-small"}, {"id": "whisper-1"},
            ]}

    def get(url, *, headers, timeout):
        requested.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(httpx, "get", get)
    result = ProviderModelCatalog(Secrets()).list_models(db_session, user, "openai")
    assert result == ["gpt-5-mini"]
    assert requested["url"] == "https://api.openai.com/v1/models"
    assert requested["headers"]["Authorization"] == "Bearer sk-secret-do-not-return-to-ui"
    assert "sk-secret-do-not-return-to-ui" not in str(result)


def test_provider_model_catalog_sanitizes_upstream_errors(db_session, monkeypatch):
    user = get_or_create_user(db_session)

    class Secrets:
        def get(self, *_):
            return "sk-secret-do-not-return-to-ui"

    def fail(*args, **kwargs):
        raise httpx.ConnectError("upstream echoed sk-secret-do-not-return-to-ui")

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(HTTPException) as error:
        ProviderModelCatalog(Secrets()).list_models(db_session, user, "openai")
    assert error.value.status_code == 502
    assert "sk-secret-do-not-return-to-ui" not in error.value.detail


def test_model_catalog_defaults_exist_for_each_supported_provider():
    assert set(DEFAULT_AGENT_MODELS) == {"openai", "gemini"}
    assert all(set(tiers) == {"ECONOMY", "FAST", "REASONING"} for tiers in DEFAULT_AGENT_MODELS.values())
    assert DEFAULT_AGENT_MODELS["openai"] == {
        "ECONOMY": "gpt-5-nano", "FAST": "gpt-5-mini", "REASONING": "gpt-5.1",
    }
