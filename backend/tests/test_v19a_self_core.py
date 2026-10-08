from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.api.deps import get_or_create_user
from app.assistant.schemas import AssistantMessageRequest, AssistantResponseType
from app.assistant.service import AssistantService
from app.assistant.tools import ToolRegistry
from app.attention.schemas import AttentionAction, AttentionItemStatus
from app.core.config import Settings
from app.database.models import AttentionItem, CognitiveTrace, Commitment, ConversationMessage, Plan, PlanBlock
from app.planning.service import get_current_plan
from app.self_core.morning import MorningBriefingBuilder
from app.self_core.orchestrator import SelfCoreOrchestrator
from app.workspaces.schemas import CookingWorkspacePayload, StudyWorkspacePayload, WorkspaceType
from app.workspaces.service import ActiveWorkspaceService


NOW = datetime(2026, 9, 28, 7, 30, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, ai_enabled=False, ai_provider="fake", development_auth_enabled=True, **overrides)


def _current_plan(db, user):
    plan = Plan(
        user_id=user.id, planner_version="test", generated_from_world_revision=user.world_revision,
        status="current", planning_day=NOW.date(), horizon_start=NOW, horizon_end=NOW + timedelta(days=1),
        generated_at=NOW, summary_metrics={}, decision_factors={}, personal_model_snapshot={},
    )
    db.add(plan); db.flush()
    db.add_all([
        PlanBlock(user_id=user.id, plan_id=plan.id, title="Algorithms", domain="learning", starts_at=NOW + timedelta(hours=1, minutes=30), ends_at=NOW + timedelta(hours=2, minutes=30), duration_minutes=60, block_type="generated_action", status="planned"),
        PlanBlock(user_id=user.id, plan_id=plan.id, title="Gym", domain="fitness", starts_at=NOW + timedelta(hours=10), ends_at=NOW + timedelta(hours=11), duration_minutes=60, block_type="commitment", commitment_level="hard", movable=False, status="planned"),
    ])
    db.flush()
    return plan


def test_morning_briefing_uses_real_plan_filters_attention_and_is_idempotent(db_session):
    user = get_or_create_user(db_session)
    plan = _current_plan(db_session, user)
    db_session.add(Commitment(user_id=user.id, title="Gym", level="hard", commitment_type="hard", starts_at=NOW + timedelta(hours=10), ends_at=NOW + timedelta(hours=11), status="active"))
    db_session.add_all([
        AttentionItem(user_id=user.id, action=AttentionAction.silent.value, reason_code="quiet", subject="Do not narrate", priority=100, status=AttentionItemStatus.eligible.value),
        AttentionItem(user_id=user.id, action=AttentionAction.mention_when_natural.value, reason_code="study", subject="Review missed study", priority=80, status=AttentionItemStatus.eligible.value),
    ])
    ActiveWorkspaceService().start_workspace(db_session, user, workspace_type=WorkspaceType.study,
        payload=StudyWorkspacePayload(course_ref="algorithms", current_question_content="Dijkstra 4"), current_step="Dijkstra 4")
    before = db_session.scalar(select(func.count(PlanBlock.id)))
    first = MorningBriefingBuilder().build(db_session, user, timezone="UTC", now=NOW)
    second = MorningBriefingBuilder().build(db_session, user, timezone="UTC", now=NOW)
    assert first.context.plan_id == plan.id and first.context.plan_version == plan.version
    assert first.context.first_block.title == "Algorithms"
    assert first.context.protected_commitments[0].title == "Gym"
    assert [item.title for item in first.context.attention_items] == ["Review missed study"]
    assert first.context.active_workspace.title == "Study"
    assert first.context.fingerprint == second.context.fingerprint
    assert db_session.scalar(select(func.count(PlanBlock.id))) == before
    assert get_current_plan(db_session, user, NOW.date()).id == plan.id


def test_self_core_routes_workspace_and_gym_without_ai_and_records_explicit_trace(db_session):
    user = get_or_create_user(db_session)
    _current_plan(db_session, user)
    db_session.add(Commitment(user_id=user.id, title="Gym training", level="hard", commitment_type="hard", starts_at=NOW + timedelta(minutes=40), ends_at=NOW + timedelta(hours=2), status="active", location="Gym"))
    workspace = ActiveWorkspaceService().start_workspace(db_session, user, workspace_type=WorkspaceType.cooking,
        payload=CookingWorkspacePayload(recipe_ref="recipe:1", current_step="Simmer"), current_step="Simmer")
    service = AssistantService(_settings())
    first = service.handle_message(db_session, user, AssistantMessageRequest(message="What's next?", now=NOW, timezone="UTC"))
    assert "cooking" in first.message.lower() and "Simmer" in first.message
    assert first.model_tier.value == "NO_AI" and first.orchestration_route == "workspace_next"
    fresh = AssistantService(_settings())
    second = fresh.handle_message(db_session, user, AssistantMessageRequest(message="How long until the gym?", thread_id=first.thread_id, now=NOW, timezone="UTC"))
    assert "40 minutes" in second.message and second.thread_id == first.thread_id
    trace = db_session.scalar(select(CognitiveTrace).where(CognitiveTrace.id == second.cognitive_trace_ref))
    assert trace.provider == "host_policy" and trace.context_json["route"] == "gym_commitment"
    assert trace.metadata_json["hidden_reasoning_stored"] is False
    assert workspace.id in {item["id"] for item in first.entity_references}


def test_self_core_study_continuity_survives_fresh_service_and_server_owned_thread(db_session):
    user = get_or_create_user(db_session)
    workspace = ActiveWorkspaceService().start_workspace(db_session, user, workspace_type=WorkspaceType.study,
        payload=StudyWorkspacePayload(course_ref="algorithms", current_question_content="Question 7"), current_step="Question 7")
    service = AssistantService(_settings())
    first = service.handle_message(db_session, user, AssistantMessageRequest(message="What's next?", now=NOW, timezone="UTC"))
    db_session.commit()
    fresh = AssistantService(_settings())
    continued = fresh.handle_message(db_session, user, AssistantMessageRequest(message="Continue.", thread_id=first.thread_id, now=NOW, timezone="UTC"))
    assert "study" in continued.message.lower() and "Question 7" in continued.message
    assert fresh.conversations.get_thread(db_session, user, first.thread_id).id == first.thread_id
    messages = fresh.conversations.messages(db_session, user, first.thread_id)
    assert len(messages) == 4 and messages[-1].content == continued.message
    assert ActiveWorkspaceService().get_foreground_workspace(db_session, user).id == workspace.id


def test_self_core_api_two_clients_share_thread_and_morning_view(client, db_session):
    user = get_or_create_user(db_session)
    _current_plan(db_session, user)
    ActiveWorkspaceService().start_workspace(db_session, user, workspace_type=WorkspaceType.cooking,
        payload=CookingWorkspacePayload(recipe_ref="recipe:1", current_step="Chop"), current_step="Chop")
    headers = {"Authorization": "Bearer dev-local-token"}
    morning_a = client.post("/api/v1/self-core/morning?timezone=UTC", headers=headers)
    morning_b = client.post("/api/v1/self-core/morning?timezone=UTC", headers=headers)
    assert morning_a.status_code == 200 and morning_a.json()["context"]["fingerprint"] == morning_b.json()["context"]["fingerprint"]
    sent = client.post("/api/v1/assistant/message", headers=headers, json={"message": "What's next?", "role": "GENERAL_ASSISTANT", "timezone": "UTC", "now": NOW.isoformat()})
    assert sent.status_code == 200 and sent.json()["response_type"] == AssistantResponseType.information.value
    thread_id = sent.json()["thread_id"]
    fetched = client.get(f"/api/v1/assistant/threads/{thread_id}", headers=headers)
    assert fetched.status_code == 200 and len(fetched.json()["messages"]) == 2
    assert db_session.scalar(select(func.count(ConversationMessage.id)).where(ConversationMessage.thread_id == thread_id)) == 2


def test_self_core_static_authority_boundaries():
    from pathlib import Path

    source = Path("app/self_core/orchestrator.py").read_text(encoding="utf-8")
    morning = Path("app/self_core/morning.py").read_text(encoding="utf-8")
    assert "PlanBlock(" not in source + morning
    assert "google.genai" not in source + morning
    assert "db.add(" not in source + morning
    assert "ReviewQueue" not in source + morning


def test_self_core_plan_proposal_tools_use_confirmation_and_existing_service():
    registry = ToolRegistry()
    for name in ("accept_plan_proposal", "modify_plan_proposal", "reject_plan_proposal"):
        tool = registry.get(name)
        assert tool.kind == "MUTATION"
        assert registry.requires_confirmation(tool, model_requested=False) is True
        assert tool.allowed_roles == {"GENERAL_ASSISTANT"}
    assert registry.get("get_active_plan_proposals").kind == "READ_ONLY"

    source = __import__("pathlib").Path("app/assistant/tools.py").read_text(encoding="utf-8")
    assert "PlanProposalService" in source
    assert "PlanBlock(" not in source


def test_self_core_router_covers_representative_cross_domain_requests():
    routes = {
        "What's next?": "workspace_next",
        "Continue.": "workspace_continue",
        "How long until the gym?": "gym_commitment",
        "Show me the proposal.": "plan_proposal",
        "What can I cook tonight?": "chef",
        "Can I go to the concert Saturday?": "concert",
    }
    for request, expected in routes.items():
        assert SelfCoreOrchestrator._route(" ".join(request.lower().split())) == expected
