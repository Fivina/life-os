from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.routing import AIBudgetState
from app.ai.types import AICapability, AIProviderError
from app.api.deps import get_or_create_user
from app.database.models import UserIntelligenceSettings
from app.decision.questions import COGNITION_AGENT_TIER_V1, DEFAULT_QUESTION_REGISTRY
from app.decision.schemas import CognitiveEvent
from tests.test_v21a_agent_runtime import ScriptedAgentModel, answer, send, settings, service_with_model


def budget(*, economy_only=False, optional_suppressed=False):
    return AIBudgetState(
        monthly_spend_eur=11.0 if optional_suppressed else 10.5 if economy_only else 0,
        budget_eur=12.0, warning=economy_only, economy_only=economy_only,
        optional_suppressed=optional_suppressed,
    )


@pytest.mark.parametrize("requested", ["FAST", "REASONING"])
def test_monthly_economy_policy_downgrades_sdk_models(db_session, requested):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    resolver = service.agent_runtime.resolver
    resolver.usage.budget_state = lambda *_: budget(economy_only=True)
    selection = resolver.resolve(
        service.skills.get("self-core"), "STRONG" if requested == "REASONING" else "STANDARD",
        capability=AICapability(requested), db=db_session, user=user,
        test_model_name=ScriptedAgentModel.model_name,
    )
    assert selection.capability == AICapability.economy
    assert selection.model == ScriptedAgentModel.model_name


def test_explicit_requests_are_not_suppressed_at_monthly_limit(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    resolver = service.agent_runtime.resolver
    resolver.usage.budget_state = lambda *_: budget(economy_only=True, optional_suppressed=True)
    selection = resolver.resolve(
        service.skills.get("self-core"), "STANDARD", db=db_session, user=user,
        test_model_name=ScriptedAgentModel.model_name,
    )
    assert selection.capability == AICapability.economy


def test_optional_cognition_uses_one_versioned_question_and_host_tier(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    service.agent_runtime.settings.decision_infra_enabled = True
    service.agent_runtime.resolver.usage.budget_state = lambda *_: budget()
    event = CognitiveEvent(event_type="morning.review_due", source="scheduler")

    class Gateway:
        def evaluate(self, db, passed_user, *, event, question, context, **kwargs):
            assert passed_user.id == user.id
            assert question == COGNITION_AGENT_TIER_V1
            assert question.question_version == 1
            assert context.metadata["selection_only"] is True
            assert context.metadata["explicit_user_request"] is False
            return SimpleNamespace(result=SimpleNamespace(selected_answer="FAST", confidence=0.99))

    selection = service.agent_runtime.resolver.resolve_optional(
        db_session, user, service.skills.get("self-core"), event=event,
        facts={"trigger": "review is due"}, gateway=Gateway(),
        test_model_name=ScriptedAgentModel.model_name,
    )
    assert selection is not None
    assert selection.capability == AICapability.fast
    assert DEFAULT_QUESTION_REGISTRY.get("cognition.agent_tier", 1) == COGNITION_AGENT_TIER_V1


@pytest.mark.parametrize("answer,confidence", [("NO_AGENT", 0.99), ("REASONING", 0.2)])
def test_optional_cognition_fails_closed_for_no_agent_or_weak_evidence(db_session, answer, confidence):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    service.agent_runtime.settings.decision_infra_enabled = True
    event = CognitiveEvent(event_type="morning.review_due", source="scheduler")

    class Gateway:
        def evaluate(self, *args, **kwargs):
            return SimpleNamespace(result=SimpleNamespace(selected_answer=answer, confidence=confidence))

    selection = service.agent_runtime.resolver.resolve_optional(
        db_session, user, service.skills.get("self-core"), event=event, facts={}, gateway=Gateway(),
        test_model_name=ScriptedAgentModel.model_name,
    )
    assert selection is None


def test_optional_budget_suppression_does_not_affect_explicit_calls(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    service.agent_runtime.settings.decision_infra_enabled = True
    resolver = service.agent_runtime.resolver
    resolver.usage.budget_state = lambda *_: budget(optional_suppressed=True, economy_only=True)
    event = CognitiveEvent(event_type="morning.review_due", source="scheduler")

    class Gateway:
        def evaluate(self, *args, **kwargs):
            return SimpleNamespace(result=SimpleNamespace(selected_answer="FAST", confidence=0.99))

    assert resolver.resolve_optional(
        db_session, user, service.skills.get("self-core"), event=event, facts={}, gateway=Gateway(),
        test_model_name=ScriptedAgentModel.model_name,
    ) is None


def test_gemini_provider_resolves_from_vault_and_catalog_without_network(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [], agent_provider="gemini")
    resolver = service.agent_runtime.resolver
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: True)
    selection = resolver.resolve(service.skills.get("self-core"), "STANDARD", db=db_session, user=user)
    assert selection.provider == "gemini"
    assert selection.model.startswith("gemini-")


def test_per_user_agent_preferences_override_environment_defaults(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [], agent_provider="openai", agent_model_fast="env-model")
    row = UserIntelligenceSettings(user_id=user.id, metadata_json={
        "agent_model_preferences": {
            "chef": {
                "provider": "gemini", "economy_model": "gemini-economy",
                "fast_model": "gemini-fast-custom", "reasoning_model": "gemini-reasoning",
            }
        }
    })
    db_session.add(row)
    db_session.flush()
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: True)
    selection = service.agent_runtime.resolver.resolve(
        service.skills.get("chef"), "STRONG", db=db_session, user=user,
    )
    assert selection.provider == "gemini"
    assert selection.model == "gemini-reasoning"


def test_agent_model_settings_are_persisted_without_secrets_and_enable_per_user_runtime(db_session, monkeypatch):
    from app.intelligence_settings.schemas import AgentModelPreference, AgentModelSettingsUpdate
    from app.intelligence_settings.service import IntelligenceSettingsService

    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: True)
    updated = IntelligenceSettingsService(service.settings).update_agent_models(
        db_session, user, AgentModelSettingsUpdate(agents={
            "chef": AgentModelPreference(
                provider="gemini", economy_model="gemini-economy",
                fast_model="gemini-fast", reasoning_model="gemini-reasoning",
            ),
        }),
    )
    row = db_session.query(UserIntelligenceSettings).filter_by(user_id=user.id).one()
    assert row.metadata_json["live_agents_enabled"] is True
    assert row.metadata_json["agent_model_preferences"]["chef"]["provider"] == "gemini"
    assert "api_key" not in str(row.metadata_json).lower()
    assert next(agent for agent in updated if agent.skill_name == "chef").provider == "gemini"
    service.settings.agent_runtime = "legacy"
    assert IntelligenceSettingsService(service.settings).control_surface(db_session, user).active_agent_runtime == "sdk"


def test_agent_model_preferences_can_be_saved_before_provider_credentials(db_session, monkeypatch):
    from app.intelligence_settings.schemas import AgentModelPreference, AgentModelSettingsUpdate
    from app.intelligence_settings.service import IntelligenceSettingsService

    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [])
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: False)
    settings_service = IntelligenceSettingsService(service.settings)

    settings_service.update_agent_models(
        db_session, user, AgentModelSettingsUpdate(agents={
            "chef": AgentModelPreference(
                provider="gemini", economy_model="gemini-economy",
                fast_model="gemini-fast", reasoning_model="gemini-reasoning",
            ),
        }),
    )

    row = db_session.query(UserIntelligenceSettings).filter_by(user_id=user.id).one()
    assert row.metadata_json["live_agents_enabled"] is True
    assert row.metadata_json["agent_model_preferences"]["chef"]["provider"] == "gemini"
    assert settings_service.live_agents_ready(db_session, user, row) is False
    assert "api_key" not in str(row.metadata_json).lower()


def test_budget_policy_optional_suppression_comes_from_shared_capability_router():
    from app.ai.routing import CapabilityRouter

    with pytest.raises(AIProviderError) as error:
        CapabilityRouter.effective_capability(AICapability.fast, budget=budget(optional_suppressed=True), optional=True)
    assert error.value.code == "budget_restricted"


def test_missing_unrelated_provider_does_not_disable_available_agents(db_session, monkeypatch):
    from app.intelligence_settings.service import IntelligenceSettingsService

    user = get_or_create_user(db_session)
    row = UserIntelligenceSettings(user_id=user.id, metadata_json={
        "live_agents_enabled": True,
        "agent_model_preferences": {"self-core": {"provider": "openai"}, "chef": {"provider": "gemini"}},
    })
    db_session.add(row)
    db_session.flush()
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured",
                        lambda _store, _db, _user, provider: provider == "openai")
    assert IntelligenceSettingsService.live_agents_ready(db_session, user, row)


def test_saved_live_route_with_missing_key_returns_error_instead_of_fake_summary(db_session, monkeypatch):
    from app.assistant.service import AssistantService

    user = get_or_create_user(db_session)
    db_session.add(UserIntelligenceSettings(user_id=user.id, metadata_json={
        "live_agents_enabled": True, "agent_model_preferences": {"self-core": {"provider": "openai"}},
    }))
    db_session.flush()
    service = AssistantService(settings(agent_runtime="legacy"))
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: False)
    monkeypatch.setattr(service.runtime, "interpret", lambda *a, **k: pytest.fail("Live route fell back to legacy"))
    response = send(service, db_session, user, "Hello, can you help me?")
    assert response.error_code == "agent_credential_missing"
    assert "Settings" in response.message


def test_cached_sdk_instance_does_not_enable_another_accounts_live_route(db_session):
    from app.agents.runtime import AgentsSDKRuntime
    from app.assistant.service import AssistantService

    user = get_or_create_user(db_session)
    other = get_or_create_user(db_session, email="other@life-os.local", auth_subject="other-user")
    db_session.add(UserIntelligenceSettings(user_id=user.id, metadata_json={
        "live_agents_enabled": True, "agent_model_preferences": {"self-core": {"provider": "openai"}},
    }))
    db_session.flush()
    service = AssistantService(settings(agent_runtime="legacy"))
    model = ScriptedAgentModel(lambda *_: [answer("A live account response.")])
    service.agent_runtime = AgentsSDKRuntime(service.settings, service.skills, service.tools, service.context, model=model)
    assert send(service, db_session, user, "Hello there.").message == "A live account response."
    response = send(service, db_session, other, "Hello there.")
    assert response.provider == "fake"
    assert len(model.calls) == 1
