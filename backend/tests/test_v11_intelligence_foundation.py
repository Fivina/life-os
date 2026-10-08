from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.ai.gateway import AIGateway
from app.ai.providers import GeminiProvider
from app.ai.routing import AIBudgetState, CapabilityRouter
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest, AIResponse, AIToolCall, AIToolDefinition, AIUsageMetadata
from app.ai.usage import AIUsageService
from app.api.deps import get_or_create_user
from app.assistant.context_builder import ContextBuilderV1
from app.assistant.schemas import AssistantMessageRequest, ModelTier
from app.assistant.tools import ToolRegistry
from app.conversations.service import ConversationService
from app.core.config import Settings
from app.database.models import AIActionAudit, ConversationMessage, ConversationSummary, Event, UserProfile
from app.skills.registry import SkillConfigurationError, SkillRegistry
from app.skills.runtime import SkillRuntime
from tests.conftest import AUTH_HEADERS


def test_fake_gateway_normalizes_and_records_usage(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(ai_provider="fake")
    response = AIGateway(settings).complete(
        db_session,
        user,
        request_id="request-v11",
        assistant_role="GENERAL_ASSISTANT",
        skill_name="self-core",
        skill_version="1.0.0",
        capability=AICapability.fast,
        request=AIRequest(
            system_instruction="Return structured intent.",
            messages=[AIMessage(role="user", content="What is on today?")],
            metadata={"assistant_role": "GENERAL_ASSISTANT", "timezone": "UTC", "context": {}},
        ),
    )

    assert response.provider == "fake"
    assert json.loads(response.text or "{}")["tool_name"] == "get_today_summary"
    audit = db_session.query(AIActionAudit).filter(AIActionAudit.request_id == "request-v11").one()
    assert audit.capability == "FAST"
    assert audit.input_tokens > 0
    assert audit.skill_name == "self-core"


def test_gemini_missing_key_is_safe_and_audited(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(ai_provider="gemini", gemini_api_key=None, ai_model_fast="gemini-2.5-flash")
    with pytest.raises(AIProviderError) as raised:
        AIGateway(settings).complete(
            db_session,
            user,
            request_id="missing-key",
            assistant_role="GENERAL_ASSISTANT",
            skill_name="self-core",
            skill_version="1.0.0",
            capability=AICapability.fast,
            request=AIRequest(system_instruction="test", messages=[AIMessage(role="user", content="hello")]),
        )

    assert raised.value.code == "missing_api_key"
    audit = db_session.query(AIActionAudit).filter(AIActionAudit.request_id == "missing-key").one()
    assert audit.status == "error"
    assert audit.error_category == "missing_api_key"


def test_gemini_request_uses_json_schema_fields():
    body = GeminiProvider(api_key="test-only")._request_body(
        AIRequest(
            system_instruction="System",
            messages=[AIMessage(role="user", content="Hello")],
            response_schema={"type": "object", "$defs": {}},
            tools=[AIToolDefinition(name="read_state", description="Read state", parameters={"type": "object", "$defs": {}})],
        )
    )

    assert body["generationConfig"]["responseJsonSchema"]["type"] == "object"
    assert "responseSchema" not in body["generationConfig"]
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert declaration["parametersJsonSchema"]["type"] == "object"
    assert "parameters" not in declaration


def test_capability_routing_and_cost_calculation_are_configuration_driven(db_session):
    settings = Settings(
        ai_provider="gemini",
        ai_model_economy="gemini-economy",
        ai_model_fast="gemini-fast",
        ai_model_reasoning="gemini-reasoning",
        ai_model_pricing_json=json.dumps(
            {"gemini-fast": {"input_per_million_eur": 1, "output_per_million_eur": 2}}
        ),
    )
    router = CapabilityRouter(settings)
    fast = router.resolve(AICapability.fast)
    economy = router.resolve(
        AICapability.reasoning,
        budget=AIBudgetState(11, 12, True, True, False),
    )
    cost, estimated = AIUsageService(settings).estimate_cost(
        model="gemini-fast",
        usage=AIUsageMetadata(input_tokens=1000, output_tokens=500),
    )

    assert fast.model == "gemini-fast"
    assert economy.model == "gemini-economy"
    assert economy.capability == AICapability.economy
    assert cost == 0.002
    assert estimated is False


def test_skill_registry_validates_tools_and_disabled_skills(tmp_path):
    (tmp_path / "CONSTITUTION.md").write_text("Canonical truth only.", encoding="utf-8")
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Use bounded tools.", encoding="utf-8")
    manifest = {
        "name": "bad-skill",
        "version": "1",
        "description": "test",
        "assistant_roles": ["GENERAL_ASSISTANT"],
        "allowed_tools": ["not_registered"],
    }
    (skill_dir / "skill.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SkillConfigurationError, match="unknown tools"):
        SkillRegistry(Settings(skills_directory=str(tmp_path))).load()

    manifest["allowed_tools"] = ["get_today_summary"]
    manifest["enabled"] = False
    (skill_dir / "skill.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    registry = SkillRegistry(Settings(skills_directory=str(tmp_path))).load()
    with pytest.raises(SkillConfigurationError, match="disabled"):
        registry.for_role("GENERAL_ASSISTANT")


class _ToolCallingProvider:
    name = "fake"

    def __init__(self, calls: list[AIToolCall]):
        self.calls = calls

    def complete(self, *, model: str, request: AIRequest) -> AIResponse:
        return AIResponse(provider=self.name, model=model, tool_calls=self.calls)


def test_skill_runtime_enforces_whitelist_tool_limit_and_capability(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(ai_provider="fake")
    tools = ToolRegistry()
    skills = SkillRegistry(settings, tools).load()
    conversations = ConversationService(settings)
    context = ContextBuilderV1(settings, skills, tools, conversations)
    thread = conversations.create_thread(db_session, user, default_skill="fitness-coach")
    conversations.append_message(db_session, user, thread, role="user", content="Read learning status")
    request = AssistantMessageRequest(message="Read learning status", role="FITNESS_COACH", timezone="UTC")

    unauthorized_gateway = AIGateway(
        settings,
        providers={"fake": _ToolCallingProvider([AIToolCall(name="get_learning_status", arguments={})])},
    )
    runtime = SkillRuntime(skills, tools, context, unauthorized_gateway)
    with pytest.raises(AIProviderError, match="not allowed") as unauthorized:
        runtime.interpret(
            db_session,
            user,
            request_id="runtime-unauthorized",
            request=request,
            thread=thread,
            preferred_tier=ModelTier.standard,
        )
    assert unauthorized.value.code == "unauthorized_tool"

    too_many_gateway = AIGateway(
        settings,
        providers={
            "fake": _ToolCallingProvider(
                [AIToolCall(name="get_current_state", arguments={}), AIToolCall(name="get_fitness_status", arguments={})]
            )
        },
    )
    runtime = SkillRuntime(skills, tools, context, too_many_gateway)
    with pytest.raises(AIProviderError) as too_many:
        runtime.interpret(
            db_session,
            user,
            request_id="runtime-too-many",
            request=request,
            thread=thread,
            preferred_tier=ModelTier.standard,
        )
    assert too_many.value.code == "tool_limit_exceeded"

    fitness = skills.get("fitness-coach")
    fitness.manifest.max_capability = AICapability.economy
    with pytest.raises(AIProviderError) as escalation:
        runtime._capability(fitness, ModelTier.strong)
    assert escalation.value.code == "skill_capability_rejected"


def test_conversations_are_user_scoped_and_compacted(db_session):
    settings = Settings(conversation_compaction_threshold=4, conversation_recent_window=2)
    service = ConversationService(settings)
    first = get_or_create_user(db_session)
    second = UserProfile(email="second@example.test", display_name="Second")
    db_session.add(second)
    db_session.flush()
    thread = service.create_thread(db_session, first)
    revision = first.world_revision
    for index in range(8):
        service.append_message(db_session, first, thread, role="user" if index % 2 == 0 else "assistant", content=f"message {index}")
    summary = service.compact_if_needed(db_session, first, thread)

    assert summary is not None
    assert summary.covered_message_count == 6
    assert "MESSAGE 5" in summary.summary.upper()
    assert first.world_revision == revision + 8
    assert db_session.query(ConversationMessage).filter_by(thread_id=thread.id).count() == 8
    assert db_session.query(ConversationSummary).filter_by(thread_id=thread.id).count() == 1
    with pytest.raises(HTTPException) as raised:
        service.get_thread(db_session, second, thread.id)
    assert raised.value.status_code == 404


def test_context_builder_preserves_stable_contract_and_trims_dynamic_context(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(ai_context_max_chars=2000)
    tools = ToolRegistry()
    skills = SkillRegistry(settings, tools).load()
    conversations = ConversationService(settings)
    thread = conversations.create_thread(db_session, user)
    conversations.append_message(db_session, user, thread, role="user", content="Summarize today")
    bundle = ContextBuilderV1(settings, skills, tools, conversations).build(
        db_session,
        user,
        role="GENERAL_ASSISTANT",
        skill=skills.get("self-core"),
        thread=thread,
        user_request="Summarize today",
        now=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        timezone="UTC",
    )

    assert "Life OS Intelligence Constitution" in bundle.stable_prefix
    assert "get_today_summary" in bundle.stable_prefix
    assert bundle.dynamic_context["request"] == "Summarize today"
    assert bundle.cache_key
    assert bundle.omitted_sections

    fitness_bundle = ContextBuilderV1(settings, skills, tools, conversations).build(
        db_session,
        user,
        role="FITNESS_COACH",
        skill=skills.get("fitness-coach"),
        thread=thread,
        user_request="What workout is next?",
        now=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        timezone="UTC",
    )
    canonical = fitness_bundle.dynamic_context["canonical"]
    assert "learning" not in canonical
    assert "kitchen" not in canonical


def test_assistant_thread_api_persists_revisioned_continuity_without_domain_mutation(client, db_session):
    first = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "What workout is next?", "role": "GENERAL_ASSISTANT", "timezone": "UTC"},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["thread_id"]
    assert payload["skill_name"] == "self-core"
    assert payload["capability"] == "FAST"

    second = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "What is on today?", "thread_id": payload["thread_id"], "timezone": "UTC"},
    )
    assert second.status_code == 200
    assert second.json()["thread_id"] == payload["thread_id"]

    detail = client.get(f"/api/v1/assistant/threads/{payload['thread_id']}", headers=AUTH_HEADERS)
    assert detail.status_code == 200
    assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant", "user", "assistant"]
    user = db_session.query(UserProfile).one()
    events = db_session.query(Event).filter(Event.user_id == user.id).all()
    assert user.world_revision == len(events) == 5
    assert all(row.event_type.startswith("conversation.") for row in events)
    assert db_session.query(AIActionAudit).filter(AIActionAudit.status == "completed").count() == 4

    usage = client.get("/api/v1/assistant/usage", headers=AUTH_HEADERS)
    assert usage.status_code == 200
    assert usage.json()["by_provider"]["fake"] == 0.0

    archived = client.post(f"/api/v1/assistant/threads/{payload['thread_id']}/archive", headers=AUTH_HEADERS)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert payload["thread_id"] not in [row["id"] for row in client.get("/api/v1/assistant/threads", headers=AUTH_HEADERS).json()]


def test_provider_status_does_not_expose_secret(client):
    response = client.get("/api/v1/assistant/provider-status", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "api_key" not in response.text.lower()
