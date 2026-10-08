from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from app.ai.providers import GeminiProvider, OpenAIEmbeddingProvider
from app.ai.gateway import AIGateway
from app.ai.types import AIEmbeddingRequest, AIEmbeddingResponse, AIProviderError
from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.intelligence_settings.embeddings import EmbeddingSettingsService
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.schemas import EmbeddingSettingsUpdate
from app.memory.embeddings import EmbeddingService
from tests.conftest import AUTH_HEADERS


def _vector(dimensions: int) -> list[float]:
    return [1.0] + [0.0] * (dimensions - 1)


def test_openai_embeddings_use_configured_dimensions_and_validate_response(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": [
                    {"index": 1, "embedding": _vector(32)},
                    {"index": 0, "embedding": _vector(32)},
                ],
                "usage": {"prompt_tokens": 9},
            }

    def post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(httpx, "post", post)
    request = AIEmbeddingRequest(texts=["first", "second"], dimensions=32)
    result = OpenAIEmbeddingProvider(api_key="server-only-test-key").embed(model="text-embedding-3-small", request=request)

    assert captured["url"] == "https://api.openai.com/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer server-only-test-key"
    assert captured["body"]["dimensions"] == 32
    assert captured["body"]["input"] == ["first", "second"]
    assert result.provider == "openai"
    assert result.dimensions == 32
    assert result.usage.input_tokens == 9
    assert result.vectors == [_vector(32), _vector(32)]


def test_openai_embeddings_reject_malformed_vector_shapes(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [{"index": 0, "embedding": [1.0]}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    with pytest.raises(AIProviderError, match="unexpected vector"):
        OpenAIEmbeddingProvider(api_key="server-only-test-key").embed(
            model="text-embedding-3-small",
            request=AIEmbeddingRequest(texts=["sample"], dimensions=32),
        )


def test_gemini_embeddings_request_dimension_and_task_type(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"embeddings": [{"values": _vector(32)}], "usageMetadata": {"inputTokenCount": 4}}

    def post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(httpx, "post", post)
    result = GeminiProvider(api_key="gemini-server-key").embed(
        model="gemini-embedding-001",
        request=AIEmbeddingRequest(texts=["sample"], task_type="RETRIEVAL_QUERY", dimensions=32),
    )

    assert captured["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert captured["headers"]["x-goog-api-key"] == "gemini-server-key"
    assert "?key=" not in captured["url"]
    assert captured["body"]["requests"][0]["embedContentConfig"] == {
        "outputDimensionality": 32,
        "taskType": "RETRIEVAL_QUERY",
    }
    assert result.provider == "gemini"
    assert result.dimensions == 32


def test_embedding_settings_are_persisted_per_user_and_require_a_saved_key(db_session):
    class Secrets:
        configured_value = True

        def configured(self, db, user, provider):
            return self.configured_value and provider == "openai"

    user = get_or_create_user(db_session)
    service = EmbeddingSettingsService(Settings(), Secrets())
    current = service.read(db_session, user)
    assert current.provider == "default"

    updated = service.update(
        db_session,
        user,
        EmbeddingSettingsUpdate(provider="openai", model="text-embedding-3-small", expected_version=current.version),
    )
    assert updated.provider == "openai"
    assert updated.model == "text-embedding-3-small"
    assert updated.dimensions == Settings().embedding_dimensions

    with pytest.raises(HTTPException) as error:
        service.update(db_session, user, EmbeddingSettingsUpdate(provider="openai", model="gpt-4o"))
    assert error.value.status_code == 422

    no_key_service = EmbeddingSettingsService(Settings(), type("Secrets", (), {"configured": lambda *_: False})())
    with pytest.raises(HTTPException) as missing_key:
        no_key_service.update(db_session, user, EmbeddingSettingsUpdate(provider="gemini", model="gemini-embedding-001"))
    assert missing_key.value.status_code == 409


def test_saved_embedding_route_uses_per_user_vault_secret(monkeypatch, db_session):
    class Secrets:
        def configured(self, db, user, provider):
            return provider == "openai"

        def get(self, db, user, provider):
            assert provider == "openai"
            return "vault-only-openai-key"

    seen = {}

    class Provider:
        def __init__(self, *, api_key, timeout_seconds):
            seen["api_key"] = api_key

        def embed(self, *, model, request):
            seen.update(model=model, dimensions=request.dimensions)
            return AIEmbeddingResponse(
                vectors=[_vector(request.dimensions)], provider="openai", model=model,
                dimensions=request.dimensions,
            )

    monkeypatch.setattr("app.memory.embeddings.OpenAIEmbeddingProvider", Provider)
    user = get_or_create_user(db_session)
    settings = Settings(ai_provider="gemini", ai_model_embedding="gemini-embedding-001", gemini_api_key="env-gemini-key")
    settings_service = EmbeddingSettingsService(settings, Secrets())
    current = settings_service.read(db_session, user)
    settings_service.update(
        db_session,
        user,
        EmbeddingSettingsUpdate(provider="openai", model="text-embedding-3-large", expected_version=current.version),
    )

    service = EmbeddingService(settings, AIGateway(settings), Secrets())
    result = service.embed(db_session, user, ["safe test"], task_type="RETRIEVAL_QUERY")

    assert seen == {"api_key": "vault-only-openai-key", "model": "text-embedding-3-large", "dimensions": settings.embedding_dimensions}
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-large"


def test_embedding_compatibility_rejects_other_model_spaces():
    response = AIEmbeddingResponse(
        vectors=[_vector(32)], provider="openai", model="text-embedding-3-small", dimensions=32,
    )
    matching = type("StoredVector", (), {
        "embedding_provider": "openai", "embedding_model": "text-embedding-3-small", "embedding_dimension": 32,
    })()
    mismatched = type("StoredVector", (), {
        "embedding_provider": "gemini", "embedding_model": "gemini-embedding-001", "embedding_dimension": 32,
    })()
    assert EmbeddingService.compatible(response, matching)
    assert not EmbeddingService.compatible(response, mismatched)


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_authenticated_embedding_connection_test_never_returns_keys_or_vectors(client, monkeypatch, provider):
    secret = "server-only-provider-key-do-not-return"
    dimensions = Settings().embedding_dimensions

    monkeypatch.setattr(ProviderSecretStore, "configured", lambda self, db, user, selected: selected == provider)
    monkeypatch.setattr(ProviderSecretStore, "get", lambda self, db, user, selected: secret)

    class Response:
        status_code = 200

        @staticmethod
        def json():
            if provider == "openai":
                return {"data": [{"index": 0, "embedding": _vector(dimensions)}], "usage": {"prompt_tokens": 3}}
            return {"embeddings": [{"values": _vector(dimensions)}], "usageMetadata": {"inputTokenCount": 3}}

    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(httpx, "post", post)
    response = client.post(
        "/api/v1/settings/intelligence/embeddings/test",
        headers=AUTH_HEADERS,
        json={"provider": provider},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "provider": provider,
        "model": "text-embedding-3-small" if provider == "openai" else "gemini-embedding-001",
        "dimensions": dimensions,
        "connected": True,
    }
    assert secret not in response.text
    assert "vectors" not in response.json()
    if provider == "openai":
        assert captured["headers"]["Authorization"] == f"Bearer {secret}"
    else:
        assert captured["headers"]["x-goog-api-key"] == secret
        assert "?key=" not in captured["url"]


def test_embedding_settings_routes_require_authentication(client):
    response = client.get("/api/v1/settings/intelligence/embeddings")
    assert response.status_code == 401
