from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from agents import Model
from agents.items import ModelResponse
from agents.models.interface import ModelTracing
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pydantic import ValidationError
from sqlalchemy import func, select

from app.api.deps import get_or_create_user
from app.assistant.schemas import AssistantMessageRequest, AssistantResponseType
from app.assistant.service import AssistantService
from app.core.config import Settings
from app.database.models import AIActionAudit, AssistantActionProposal, Course, PlanBlock
from app.domains.learning.schemas import CourseCreate, ExamCreate
from app.domains.learning.service import create_course, create_exam


class ScriptedAgentModel(Model):
    """No-network model exercising the installed SDK runner, not a replacement loop."""

    model_name = "life-os-test-agent"

    def __init__(self, script):
        self.script = script
        self.calls = []

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        assert tracing == ModelTracing.DISABLED
        assert not handoffs and output_schema is None
        assert model_settings.store is False
        assert model_settings.parallel_tool_calls is False
        assert kwargs.get("conversation_id") is None
        assert kwargs.get("previous_response_id") is None
        self.calls.append({"input": input, "tools": [tool.name for tool in tools],
                           "instructions": system_instructions})
        output = self.script(len(self.calls), input, tools)
        return ModelResponse(
            output=output,
            usage=Usage(requests=1, input_tokens=100, output_tokens=10, total_tokens=110,
                        input_tokens_details={"cached_tokens": 20, "cache_write_tokens": 0},
                        output_tokens_details={"reasoning_tokens": 2}),
            response_id=f"test-response-{len(self.calls)}",
        )

    async def stream_response(self, *args, **kwargs):
        raise AssertionError("Streaming is outside this pilot")
        yield  # pragma: no cover


def call(name, arguments=None, *, call_id="test-call"):
    return ResponseFunctionToolCall(type="function_call", name=name,
                                    arguments=json.dumps(arguments or {}), call_id=call_id)


def answer(text):
    return ResponseOutputMessage(
        id="test-answer", type="message", role="assistant", status="completed",
        content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
    )


def settings(**overrides):
    return Settings(_env_file=None, **{
        "agent_runtime": "sdk", "ai_enabled": True, "ai_provider": "fake",
        "agent_model_fast": "configured-fast", "openai_api_key": None,
        "agent_trace_export_enabled": False,
        "ai_model_pricing_json": json.dumps({ScriptedAgentModel.model_name: {
            "input_per_million_eur": 1, "output_per_million_eur": 2,
            "cached_input_per_million_eur": 0.5,
        }}),
        **overrides,
    })


@pytest.fixture(autouse=True)
def no_live_openai(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not create a network model client")
    monkeypatch.setattr("app.agents.runtime.AsyncOpenAI", forbidden)


def service_with_model(script, **overrides):
    service = AssistantService(settings(**overrides))
    model = ScriptedAgentModel(script)
    if service.agent_runtime is not None:
        service.agent_runtime.model = model
    return service, model


def send(service, db, user, message="Help me review my priorities.", **kwargs):
    return service.handle_message(db, user, AssistantMessageRequest(message=message, **kwargs))


def sdk_audit(db, request_id):
    rows = list(db.scalars(select(AIActionAudit).where(AIActionAudit.request_id == request_id)))
    return [row for row in rows if row.metadata_json.get("runtime") == "sdk"]


def test_sdk_sequential_reads_use_observation_persist_answer_and_aggregate_usage(db_session):
    user = get_or_create_user(db_session)
    course = create_course(db_session, user, CourseCreate(name="Algorithms"))
    exam = create_exam(db_session, user, ExamCreate(
        course_id=course.id, title="Algorithms final", target_preparation_minutes=120,
        exam_at=datetime.now(UTC) + timedelta(days=7),
    ))
    block_count = db_session.scalar(select(func.count(PlanBlock.id)))

    def script(turn, input, tools):
        observations = [item for item in input if isinstance(item, dict) and item.get("type") == "function_call_output"]
        if turn == 1:
            return [call("get_learning_status", call_id="learning")]
        if turn == 2:
            observed = json.loads(observations[-1]["output"])["result"]["active_exam"]
            assert observed["id"] == exam.id
            return [call("get_exam_status", {"exam_id": observed["id"]}, call_id="exam")]
        assert len(observations) == 2
        return [answer("Algorithms final is the exam to review.")]

    service, model = service_with_model(script)
    response = send(service, db_session, user)
    assert response.error_code is None
    assert response.message == "Algorithms final is the exam to review."
    assert len(model.calls) == 3
    assert '"runtime":"sdk"' in model.calls[0]["instructions"]
    assert "Return exactly one AssistantIntent" not in model.calls[0]["instructions"]
    assert "Use create_commitment for appointments" in model.calls[0]["instructions"]
    manifest = service.skills.get("self-core").manifest
    assert set(model.calls[0]["tools"]) == set(manifest.allowed_tools) | {
        f"consult_{name.replace('-', '_')}" for name in manifest.allowed_agents
    }
    assert db_session.scalar(select(func.count(PlanBlock.id))) == block_count
    assert response.mutation_result is None
    assert response.assistant_message_id
    db_session.commit()
    fresh = AssistantService(settings())
    messages = fresh.conversations.messages(db_session, user, response.thread_id)
    assert [item.role for item in messages] == ["user", "assistant"]
    assert messages[-1].content == response.message
    audits = sdk_audit(db_session, response.request_id)
    assert len(audits) == 1
    audit = audits[0]
    assert (audit.input_tokens, audit.output_tokens, audit.cached_tokens, audit.tool_call_count) == (300, 30, 60, 2)
    assert audit.estimated_cost == pytest.approx(0.00033)
    assert audit.provider == "fake" and audit.model == model.model_name
    assert audit.skill_name == "self-core" and audit.skill_version == manifest.version
    assert audit.metadata_json["model_requests"] == 3
    assert audit.metadata_json["reasoning_tokens"] == 6
    assert "Algorithms" not in json.dumps(audit.metadata_json)


def test_unlisted_tool_is_not_exposed_or_executed(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [call("finance_get_overview")])
    monkeypatch.setattr(service.tools, "execute", lambda *a, **k: pytest.fail("Unauthorized handler ran"))
    response = send(service, db_session, user)
    assert "finance_get_overview" not in model.calls[0]["tools"]
    assert response.response_type == AssistantResponseType.error
    assert response.error_code == "agent_invalid_output"
    assert sdk_audit(db_session, response.request_id)[0].tool_call_count == 0


def test_role_authorization_is_rechecked_at_execution(db_session, monkeypatch):
    user = get_or_create_user(db_session)

    def script(*_):
        service.tools.get("get_current_state").allowed_roles.clear()
        return [call("get_current_state")]

    service, _ = service_with_model(script)
    monkeypatch.setattr(service.tools, "execute", lambda *a, **k: pytest.fail("Unauthorized handler ran"))
    response = send(service, db_session, user)
    assert response.error_code == "unauthorized_tool"


def test_invalid_mutation_arguments_rejected_before_proposal(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [call("create_course", {"name": ""})])
    response = send(service, db_session, user)
    assert response.error_code == "invalid_tool_arguments"
    assert db_session.scalar(select(func.count(AssistantActionProposal.id))) == 0
    assert db_session.scalar(select(func.count(Course.id))) == 0


def test_mutation_stops_at_one_existing_proposal_and_confirmation_is_idempotent(db_session):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [
        call("create_course", {"name": "Algorithms"}, call_id="first"),
        call("create_course", {"name": "Must not be created"}, call_id="second"),
    ])
    response = send(service, db_session, user)
    assert response.response_type == AssistantResponseType.proposal
    assert len(model.calls) == 1
    assert response.proposed_action.tool_name == "create_course"
    assert response.proposed_action.arguments["name"] == "Algorithms"
    assert response.proposed_action.expected_world_revision == user.world_revision
    assert db_session.scalar(select(func.count(Course.id))) == 0
    assert db_session.scalar(select(func.count(AssistantActionProposal.id))) == 1
    audit = sdk_audit(db_session, response.request_id)[0]
    assert audit.status == "proposed" and audit.proposal_id == response.proposed_action.id
    confirmed = service.confirm_proposal(db_session, user, response.proposed_action.id)
    assert confirmed.response_type == AssistantResponseType.mutation_result
    service.confirm_proposal(db_session, user, response.proposed_action.id)
    assert db_session.scalar(select(func.count(Course.id))) == 1


def test_conditional_mutation_also_requires_confirmation_in_pilot(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [call("request_replan")])
    before = db_session.scalar(select(func.count(PlanBlock.id)))
    response = send(service, db_session, user)
    assert response.response_type == AssistantResponseType.proposal
    assert response.proposed_action.confirmation_required
    assert db_session.scalar(select(func.count(PlanBlock.id))) == before


def test_total_tool_limit_applies_even_when_model_ignores_parallel_setting(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [call("get_current_state", call_id=f"call-{i}") for i in range(7)])
    executions = []
    original = service.tools.execute

    def execute(*args, **kwargs):
        executions.append(args[2].name)
        return original(*args, **kwargs)

    monkeypatch.setattr(service.tools, "execute", execute)
    response = send(service, db_session, user)
    assert response.error_code == "agent_tool_limit"
    assert len(executions) == 6
    assert sdk_audit(db_session, response.request_id)[0].tool_call_count == 6


def test_manifest_tool_limit_is_total_across_turns(db_session):
    user = get_or_create_user(db_session)
    service, model = service_with_model(
        lambda turn, *_: [call("get_current_state", call_id=f"call-{turn}")],
    )
    service.skills.get("self-core").manifest.max_tool_calls = 2
    response = send(service, db_session, user)
    assert response.error_code == "agent_tool_limit"
    assert len(model.calls) == 3
    assert sdk_audit(db_session, response.request_id)[0].tool_call_count == 2


@pytest.mark.parametrize("limit", [2, 6])
def test_turn_limit_stops_model_and_records_completed_usage(db_session, limit):
    user = get_or_create_user(db_session)
    service, model = service_with_model(
        lambda turn, *_: [call("get_current_state", call_id=f"call-{turn}")], agent_max_turns=limit,
    )
    response = send(service, db_session, user)
    assert response.error_code == "agent_turn_limit"
    assert len(model.calls) == limit
    audit = sdk_audit(db_session, response.request_id)[0]
    assert audit.input_tokens == limit * 100 and audit.status == "error"
    assert audit.tool_call_count == limit


def test_legacy_flag_keeps_existing_runtime(db_session):
    user = get_or_create_user(db_session)
    legacy, _ = service_with_model(lambda *_: pytest.fail("SDK used during rollback"), agent_runtime="legacy")
    response = send(legacy, db_session, user, message="Hello")
    assert response.response_type != AssistantResponseType.error
    assert legacy.agent_runtime is None
    assert not sdk_audit(db_session, response.request_id)


def test_deterministic_self_core_route_still_runs_first(db_session):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: pytest.fail("Exact route called SDK"))
    response = send(service, db_session, user, message="What's next?")
    assert response.orchestration_route == "workspace_next"
    assert not model.calls


def test_provider_failure_is_sanitized_and_does_not_replay_legacy(db_session, monkeypatch):
    user = get_or_create_user(db_session)

    def script(turn, *_):
        if turn == 1:
            return [call("get_current_state")]
        raise RuntimeError("secret-api-key and private prompt")

    service, _ = service_with_model(script)
    monkeypatch.setattr(service.runtime, "interpret", lambda *a, **k: pytest.fail("Unexpected legacy replay"))
    response = send(service, db_session, user)
    assert response.error_code == "agent_run_failed"
    assert "secret-api-key" not in response.model_dump_json()
    audit = sdk_audit(db_session, response.request_id)[0]
    assert audit.input_tokens == 100 and audit.tool_call_count == 1
    assert "private prompt" not in json.dumps(audit.metadata_json)


@pytest.mark.parametrize("overrides,code", [
    ({"ai_enabled": False}, "ai_disabled"),
    ({"openai_api_key": "legacy-env-key-must-not-be-used"}, "agent_credential_missing"),
])
def test_sdk_configuration_failure_is_safe_and_persisted(db_session, overrides, code):
    user = get_or_create_user(db_session)
    service = AssistantService(settings(**overrides))
    response = send(service, db_session, user)
    assert response.error_code == code
    assert response.assistant_message_id
    assert len(sdk_audit(db_session, response.request_id)) == 1


def test_config_bounds_and_secret_redaction():
    with pytest.raises(ValidationError):
        settings(agent_max_turns=7)
    with pytest.raises(ValidationError):
        settings(agent_runtime="unknown")
    configured = settings(openai_api_key="private-key")
    assert "private-key" not in repr(configured)
    assert "private-key" not in configured.model_dump_json()


def test_native_openai_adapter_serializes_tools_and_accounts_usage_without_network(db_session, monkeypatch):
    from httpx2 import MockTransport, Response
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["store"] is False
        assert body["parallel_tool_calls"] is False
        assert "conversation" not in body and "previous_response_id" not in body
        assert all(tool["type"] == "function" for tool in body["tools"])
        assert "finance_get_overview" not in {tool["name"] for tool in body["tools"]}
        if len(requests) == 1:
            output = call("get_current_state").model_dump(mode="json", exclude_none=True)
        else:
            observation = next(item for item in body["input"] if item.get("type") == "function_call_output")
            assert "result" in json.loads(observation["output"])
            output = answer("Current state reviewed.").model_dump(mode="json", exclude_none=True)
        return Response(200, json={
            "id": f"resp_test_{len(requests)}", "object": "response", "created_at": 1,
            "model": "configured-fast", "status": "completed", "output": [output],
            "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
                      "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 2}},
        })

    def mock_client(**kwargs):
        return AsyncOpenAI(**kwargs, base_url="https://agent-test.invalid/v1",
                           http_client=DefaultAsyncHttpxClient(transport=MockTransport(respond)))

    monkeypatch.setattr("app.agents.runtime.AsyncOpenAI", mock_client)
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.configured", lambda *_: True)
    monkeypatch.setattr("app.intelligence_settings.provider_credentials.ProviderSecretStore.get", lambda *_: "test-only-key")
    user = get_or_create_user(db_session)
    service = AssistantService(settings(openai_api_key="test-only-key"))
    response = send(service, db_session, user)
    assert response.error_code is None
    assert response.message == "Current state reviewed."
    assert len(requests) == 2
    audit = sdk_audit(db_session, response.request_id)[0]
    assert audit.provider == "openai" and audit.model == "gpt-5-mini"
    assert (audit.input_tokens, audit.output_tokens, audit.tool_call_count) == (200, 20, 1)
    assert audit.metadata_json["model_requests"] == 2
