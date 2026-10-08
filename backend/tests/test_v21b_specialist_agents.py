from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.api.deps import get_or_create_user
from app.ai.gateway import AIGateway
from app.ai.types import AIToolCall
from app.assistant.schemas import AssistantResponseType
from app.database.models import AIActionAudit, AssistantActionProposal, Course, PlanBlock
from app.domains.learning.schemas import CourseCreate, ExamCreate
from app.domains.learning.service import create_course, create_exam
from app.skills.models import SkillManifest
from app.skills.registry import SkillConfigurationError, SkillRegistry
from tests.test_v21a_agent_runtime import (
    ScriptedAgentModel, answer, call, no_live_openai, sdk_audit, send, service_with_model, settings,
)
from tests.test_v11_intelligence_foundation import _ToolCallingProvider


SPECIALISTS = [
    ("CHEF", "chef"), ("LEARNING_COACH", "learning-coach"),
    ("FITNESS_COACH", "fitness-coach"), ("HOME_MANAGER", "home-manager"),
    ("FINANCE_ADVISOR", "finance"),
]


def observations(input):
    return [item for item in input if isinstance(item, dict) and item.get("type") == "function_call_output"]


def test_direct_chef_reads_twice_before_answer(db_session):
    user = get_or_create_user(db_session)

    def script(turn, input, tools):
        if turn == 1:
            return [call("get_kitchen_status", call_id="kitchen")]
        if turn == 2:
            assert "result" in json.loads(observations(input)[-1]["output"])
            return [call("get_shopping_needs", call_id="shopping")]
        assert len(observations(input)) == 2
        return [answer("Kitchen and shopping reviewed.")]

    service, model = service_with_model(script)
    response = send(service, db_session, user, role="CHEF")
    assert response.error_code is None
    assert response.message == "Kitchen and shopping reviewed."
    assert len(model.calls) == 3
    assert sdk_audit(db_session, response.request_id)[0].tool_call_count == 2


def test_direct_learning_uses_first_observation_for_second_read(db_session):
    user = get_or_create_user(db_session)
    course = create_course(db_session, user, CourseCreate(name="Algorithms"))
    exam = create_exam(db_session, user, ExamCreate(
        course_id=course.id, title="Final", target_preparation_minutes=120,
        exam_at=datetime.now(UTC) + timedelta(days=7),
    ))

    def script(turn, input, tools):
        if turn == 1:
            return [call("get_learning_status", call_id="learning")]
        if turn == 2:
            observed = json.loads(observations(input)[-1]["output"])["result"]["active_exam"]
            assert observed["id"] == exam.id
            return [call("get_exam_status", {"exam_id": observed["id"]}, call_id="exam")]
        assert len(observations(input)) == 2
        return [answer("Study this exam next.")]

    service, model = service_with_model(script)
    response = send(service, db_session, user, role="LEARNING_COACH")
    assert response.error_code is None
    assert len(model.calls) == 3
    assert db_session.scalar(select(func.count(PlanBlock.id))) == 0


@pytest.mark.parametrize("role,name", SPECIALISTS)
def test_direct_roles_have_only_manifest_tools_and_scoped_context(db_session, role, name):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [answer("Specialist response.")])
    response = send(service, db_session, user, role=role)
    assert response.error_code is None
    assert response.role_used == role and response.skill_name == name
    manifest = service.skills.get(name).manifest
    assert set(model.calls[0]["tools"]) == set(manifest.allowed_tools)
    assert not any(tool.startswith("consult_") for tool in model.calls[0]["tools"])
    dynamic = json.loads(model.calls[0]["instructions"].split("# Dynamic Context\n")[1])
    assert not ({"kitchen", "learning", "fitness", "home", "finance"} - set(manifest.read_scopes)) & dynamic["canonical"].keys()
    assert "recent_events" not in dynamic["global_workspace"]
    assert dynamic["conversation"]["summary"] is None
    assert sdk_audit(db_session, response.request_id)[0].skill_name == name


def test_manager_delegates_with_fresh_scoped_context_and_separate_usage(db_session):
    user = get_or_create_user(db_session)

    def manager(turn, input, tools):
        if turn == 1:
            return [call("consult_chef", {"task": "Compare practical dinner options."})]
        result = json.loads(observations(input)[-1]["output"])
        assert result == {"specialist": "chef", "answer": "Chef assessment.", "proposal_pending": False}
        return [answer("Manager's final answer.")]

    def chef(turn, input, tools):
        if turn == 1:
            return [call("get_kitchen_status")]
        return [answer("Chef assessment.")]

    service, manager_model = service_with_model(manager)
    child = ScriptedAgentModel(chef)
    service.agent_runtime.models["chef"] = child
    response = send(service, db_session, user, message="PRIVATE_MANAGER_DETAIL: assess dinner trade-offs.")
    assert response.error_code is None
    assert response.message == "Manager's final answer."
    assert len(manager_model.calls) == 2 and len(child.calls) == 2
    assert "PRIVATE_MANAGER_DETAIL" not in json.dumps(child.calls)
    assert "Compare practical dinner options." in json.dumps(child.calls)
    assert not any(tool.startswith("consult_") for tool in child.calls[0]["tools"])
    db_session.flush()
    rows = [row for row in db_session.scalars(select(AIActionAudit)) if row.metadata_json.get("runtime") == "sdk"]
    assert len(rows) == 2
    assert sum(row.input_tokens for row in rows) == 400
    assert sum(row.cached_tokens for row in rows) == 80
    assert sum(row.tool_call_count for row in rows) == 2
    child_audit = next(row for row in rows if row.skill_name == "chef")
    assert child_audit.metadata_json["parent_request_id"] == response.request_id
    messages = service.conversations.messages(db_session, user, response.thread_id)
    assert len(messages) == 2
    assert messages[-1].content == response.message


@pytest.mark.parametrize("tool", ["finance_get_overview", "consult_learning_coach"])
def test_specialist_unlisted_tool_or_agent_is_impossible(db_session, monkeypatch, tool):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [call(tool)])
    monkeypatch.setattr(service.tools, "execute", lambda *a, **k: pytest.fail("Unauthorized handler ran"))
    response = send(service, db_session, user, role="CHEF")
    assert tool not in model.calls[0]["tools"]
    assert response.error_code == "agent_invalid_output"


@pytest.mark.parametrize("tool", ["consult_planner", "consult_memory_curator"])
def test_manager_cannot_delegate_to_unlisted_background_skills(db_session, tool):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [call(tool, {"task": "Run"})])
    response = send(service, db_session, user)
    assert tool not in model.calls[0]["tools"]
    assert response.error_code == "agent_invalid_output"


@pytest.mark.parametrize("delegated", [False, True])
def test_specialist_mutation_uses_shared_confirmation_without_domain_write(db_session, delegated):
    user = get_or_create_user(db_session)
    mutation = lambda *_: [call("create_course", {"name": "Algorithms"})]
    script = (lambda *_: [call("consult_learning_coach", {"task": "Create Algorithms course."})]) if delegated else mutation
    service, model = service_with_model(script)
    if delegated:
        service.agent_runtime.models["learning-coach"] = ScriptedAgentModel(mutation)
    response = send(service, db_session, user, role="GENERAL_ASSISTANT" if delegated else "LEARNING_COACH")
    assert response.error_code is None
    assert response.response_type == AssistantResponseType.proposal
    assert response.proposed_action.tool_name == "create_course"
    assert len(model.calls) == 1
    assert db_session.scalar(select(func.count(Course.id))) == 0
    assert db_session.scalar(select(func.count(AssistantActionProposal.id))) == 1
    assert db_session.scalar(select(func.count(PlanBlock.id))) == 0
    confirmed = service.confirm_proposal(db_session, user, response.proposed_action.id)
    assert confirmed.response_type == AssistantResponseType.mutation_result
    assert db_session.scalar(select(func.count(Course.id))) == 1


@pytest.mark.parametrize("during_run", [False, True])
def test_disabled_specialist_is_hidden_and_rechecked_at_invocation(db_session, during_run):
    user = get_or_create_user(db_session)

    def manager(*_):
        if during_run:
            controls.disabled_skills_json = ["chef"]
        return [call("consult_chef", {"task": "Assess dinner options."})]

    service, model = service_with_model(manager)
    service.agent_runtime.models["chef"] = ScriptedAgentModel(lambda *_: pytest.fail("Disabled specialist ran"))
    controls = service.intelligence_settings.get_model(db_session, user)
    if not during_run:
        controls.disabled_skills_json = ["chef"]
    response = send(service, db_session, user)
    assert ("consult_chef" in model.calls[0]["tools"]) is during_run
    assert response.error_code == ("agent_unavailable" if during_run else "agent_invalid_output")


def test_shared_turn_limit_counts_manager_and_child(db_session):
    user = get_or_create_user(db_session)
    service, manager = service_with_model(
        lambda *_: [call("consult_chef", {"task": "Review dinner."})], agent_max_turns=2,
    )
    child = ScriptedAgentModel(lambda *_: [answer("Chef assessment.")])
    service.agent_runtime.models["chef"] = child
    response = send(service, db_session, user)
    assert response.error_code == "agent_turn_limit"
    assert len(manager.calls) + len(child.calls) == 2


def test_shared_tool_limit_cannot_be_reset_by_delegation(db_session):
    user = get_or_create_user(db_session)
    service, _ = service_with_model(lambda *_: [
        *[call("get_current_state", call_id=f"read-{i}") for i in range(5)],
        call("consult_chef", {"task": "Review dinner."}, call_id="chef"),
    ])
    service.agent_runtime.models["chef"] = ScriptedAgentModel(lambda *_: [call("get_kitchen_status")])
    response = send(service, db_session, user)
    assert response.error_code == "agent_tool_limit"
    db_session.flush()
    audits = [row for row in db_session.scalars(select(AIActionAudit)) if row.metadata_json.get("runtime") == "sdk"]
    assert sum(row.tool_call_count for row in audits) == 6
    assert next(row for row in audits if row.skill_name == "chef").tool_call_count == 0


def test_child_turn_limit_applies_even_with_shared_budget_remaining(db_session):
    user = get_or_create_user(db_session)
    service, manager = service_with_model(lambda *_: [call("consult_chef", {"task": "Assess dinner."})])
    service.skills.get("chef").manifest.max_iterations = 2
    child = ScriptedAgentModel(lambda turn, *_: [call("get_kitchen_status", call_id=f"read-{turn}")])
    service.agent_runtime.models["chef"] = child
    response = send(service, db_session, user)
    assert response.error_code == "agent_turn_limit"
    assert len(manager.calls) == 1 and len(child.calls) == 2


def test_specialist_small_cap_is_enforced(db_session):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [call("get_home_status", call_id=str(i)) for i in range(3)])
    response = send(service, db_session, user, role="HOME_MANAGER")
    assert response.error_code == "agent_tool_limit"
    assert sdk_audit(db_session, response.request_id)[0].tool_call_count == 2
    assert len(model.calls) == 1


@pytest.mark.parametrize("role,name", SPECIALISTS)
def test_legacy_rollback_still_handles_each_specialist(db_session, role, name):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: pytest.fail("SDK used during rollback"), agent_runtime="legacy")
    tool = {"chef": "get_kitchen_status", "learning-coach": "get_learning_status",
            "fitness-coach": "get_fitness_status", "home-manager": "get_home_status",
            "finance": "finance_get_overview"}[name]
    service.runtime.gateway = AIGateway(service.settings, providers={
        "fake": _ToolCallingProvider([AIToolCall(name=tool, arguments={})]),
    })
    response = send(service, db_session, user, message="Hello", role=role)
    assert response.response_type != AssistantResponseType.error
    assert response.skill_name == name
    assert service.agent_runtime is None and not model.calls
    assert not sdk_audit(db_session, response.request_id)


def test_specialist_keeps_own_history_but_not_other_roles(db_session):
    user = get_or_create_user(db_session)
    service, model = service_with_model(lambda *_: [answer("Response.")])
    initial = send(service, db_session, user, role="FINANCE_ADVISOR", message="PRIVATE_FINANCE_DETAILS")
    chef = send(service, db_session, user, role="CHEF", thread_id=initial.thread_id, message="MY_CHEF_CONTEXT")
    followup = send(service, db_session, user, role="CHEF", thread_id=chef.thread_id, message="Continue with dinner.")
    assert followup.error_code is None
    assert "PRIVATE_FINANCE_DETAILS" not in json.dumps(model.calls[-1])
    assert "MY_CHEF_CONTEXT" in json.dumps(model.calls[-1])
    assert "Continue with dinner." in json.dumps(model.calls[-1])
    assert len(service.conversations.messages(db_session, user, initial.thread_id)) == 6


def test_specialist_failure_is_sanitized_and_not_replayed(db_session, monkeypatch):
    user = get_or_create_user(db_session)
    service, manager = service_with_model(lambda *_: [call("consult_chef", {"task": "Assess dinner."})])

    def broken(turn, *_):
        if turn == 1:
            return [call("get_kitchen_status")]
        raise RuntimeError("private-secret-provider-message")

    service.agent_runtime.models["chef"] = ScriptedAgentModel(broken)
    monkeypatch.setattr(service.runtime, "interpret", lambda *a, **k: pytest.fail("Legacy replay"))
    response = send(service, db_session, user)
    assert response.error_code == "agent_run_failed"
    assert "private-secret" not in response.model_dump_json()
    assert len(manager.calls) == 1
    db_session.flush()
    rows = [row for row in db_session.scalars(select(AIActionAudit)) if row.metadata_json.get("runtime") == "sdk"]
    assert len(rows) == 2 and sum(row.input_tokens for row in rows) == 200
    assert all(row.status == "error" for row in rows)


def test_manifest_rejects_specialist_recursion_and_duplicate_agents():
    with pytest.raises(ValidationError, match="Only Self Core"):
        SkillManifest(name="chef", version="test", description="test", assistant_roles=["CHEF"], allowed_agents=["finance"])
    with pytest.raises(ValidationError, match="duplicates"):
        SkillManifest(name="self-core", version="test", description="test", assistant_roles=["GENERAL_ASSISTANT"], allowed_agents=["chef", "chef"])


@pytest.mark.parametrize("target", ["missing", "planner", "self-core"])
def test_registry_rejects_unknown_or_nonleaf_targets(tmp_path, target):
    for name, roles, agents in [("self-core", ["GENERAL_ASSISTANT"], [target]), ("planner", [], [])]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "SKILL.md").write_text("Test instructions.", encoding="utf-8")
        (directory / "skill.yaml").write_text(json.dumps({
            "name": name, "version": "test", "description": "test", "assistant_roles": roles,
            "allowed_agents": agents,
        }), encoding="utf-8")
    with pytest.raises(SkillConfigurationError, match="unknown agent|leaf specialist"):
        SkillRegistry(settings(skills_directory=str(tmp_path))).load()
