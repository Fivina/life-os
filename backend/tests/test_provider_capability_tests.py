from __future__ import annotations

from app.ai.types import AIUsageMetadata
from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.database.models import AIActionAudit
from app.intelligence_settings.provider_tests import OPENAI_TEST_RESPONSE, ProviderCapabilityTestService
from app.intelligence_settings.schemas import JevDecisionTestRead, OpenAIChatTestRead
from tests.conftest import AUTH_HEADERS


def test_openai_provider_test_uses_current_model_and_records_only_safe_usage(db_session, monkeypatch):
    user = get_or_create_user(db_session)

    class Secrets:
        def get(self, _db, _user, provider):
            assert provider == "openai"
            return "test-only-secret-value"

    service = ProviderCapabilityTestService(Settings(_env_file=None, ai_enabled=True), Secrets())
    observed = {}

    async def probe(api_key, model):
        observed.update(api_key=api_key, model=model)
        return OPENAI_TEST_RESPONSE, AIUsageMetadata(input_tokens=12, output_tokens=6, total_tokens=18)

    monkeypatch.setattr(service, "_run_openai_probe", probe)
    result = service.test_openai_chat(db_session, user)

    assert observed == {"api_key": "test-only-secret-value", "model": "gpt-5-mini"}
    assert result.model == "gpt-5-mini" and result.connected and result.passed
    assert "test-only-secret-value" not in result.model + result.response
    audit = db_session.query(AIActionAudit).one()
    assert audit.provider == "openai" and audit.model == "gpt-5-mini"
    assert audit.skill_name == "provider-test" and audit.input_tokens == 12


def test_provider_test_endpoints_are_authenticated(client):
    for path in (
        "/api/v1/settings/intelligence/providers/openai/test",
        "/api/v1/settings/intelligence/providers/jev/test",
    ):
        response = client.post(path)
        assert response.status_code == 401


def test_jev_defaults_to_the_typesafe_api():
    assert Settings(_env_file=None).jev_base_url == "https://api.typesafe.ai"


def test_settings_ui_provider_test_routes_return_bounded_results(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_intelligence_settings.ProviderCapabilityTestService.test_openai_chat",
        lambda *_: OpenAIChatTestRead(
            model="gpt-5-mini", connected=True, passed=True,
            response=OPENAI_TEST_RESPONSE, latency_ms=40,
        ),
    )
    monkeypatch.setattr(
        "app.api.routes_intelligence_settings.ProviderCapabilityTestService.test_jev_decision",
        lambda *_: JevDecisionTestRead(
            model="jev-latest", connected=True, passed=True,
            selected_answer=True, true_probability=0.9, trace_id="trace-safe-test", latency_ms=35,
        ),
    )
    openai = client.post("/api/v1/settings/intelligence/providers/openai/test", headers=AUTH_HEADERS)
    jev = client.post("/api/v1/settings/intelligence/providers/jev/test", headers=AUTH_HEADERS)

    assert openai.status_code == 200
    assert openai.json() == {
        "provider": "openai", "model": "gpt-5-mini", "connected": True, "passed": True,
        "response": OPENAI_TEST_RESPONSE, "latency_ms": 40,
    }
    assert jev.status_code == 200
    assert jev.json() == {
        "provider": "jev", "model": "jev-latest", "connected": True, "passed": True,
        "selected_answer": True, "true_probability": 0.9, "trace_id": "trace-safe-test", "latency_ms": 35,
    }
