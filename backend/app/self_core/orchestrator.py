from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from math import ceil

from sqlalchemy.orm import Session

from app.assistant.context_builder import ContextBuilderV2
from app.assistant.schemas import AssistantMessageRequest
from app.attention.schemas import AttentionAction
from app.communication.composer import ResponseComposer
from app.communication.schemas import CommunicativeIntent, ResponseModePreference, SpeechAct, StructuredFact
from app.commitments.service import list_commitments
from app.core.config import Settings
from app.database.models import ConversationThread, UserProfile
from app.domains.finance.contracts import discretionary_social_budget_remaining
from app.domains.kitchen.chef import recommend_from_text
from app.domains.kitchen.schemas import ChefIntentRequest
from app.self_core.schemas import SelfCoreReference
from app.skills.models import LoadedSkill
from app.social.schemas import OpportunityType
from app.social.service import list_opportunities
from app.strategy.service import PlanProposalService
from app.workspaces.service import ActiveWorkspaceService
from app.workspaces.situation import GlobalWorkspaceBuilder


@dataclass(frozen=True)
class OrchestrationResult:
    message: str
    route: str
    facts: tuple[StructuredFact, ...]
    entity_references: tuple[dict, ...] = ()
    tool_name: str | None = None
    state_change_refs: tuple[str, ...] = ()
    context_sections: tuple[str, ...] = ()


class SelfCoreOrchestrator:
    """Coordinates existing bounded services; it owns no canonical state."""

    def __init__(self, settings: Settings, context: ContextBuilderV2):
        self.settings = settings
        self.context = context
        self.workspaces = ActiveWorkspaceService()
        self.proposals = PlanProposalService(settings)

    def try_handle(
        self,
        db: Session,
        user: UserProfile,
        *,
        request: AssistantMessageRequest,
        thread: ConversationThread,
        skill: LoadedSkill,
        request_id: str,
    ) -> OrchestrationResult | None:
        if request.role != "GENERAL_ASSISTANT":
            return None
        text = " ".join(request.message.lower().split())
        route = self._route(text)
        if route is None:
            return None
        bundle = self.context.build(
            db, user, role=request.role, skill=skill, thread=thread, user_request=request.message,
            now=request.now, timezone=request.timezone, client_recent_messages=request.recent_messages,
            request_id=request_id, include_optional=False,
        )
        situation = GlobalWorkspaceBuilder().build(db, user, now=request.now, conversation_thread_ref=thread.id)
        if route in {"workspace_next", "workspace_continue"}:
            result = self._workspace(db, user, route, situation.foreground_workspace)
        elif route == "gym_commitment":
            result = self._gym(db, user, situation, request.now)
        elif route == "plan_proposal":
            result = self._proposal(db, user)
        elif route == "chef":
            result = self._chef(db, user, request)
        else:
            result = self._concert(db, user, request)
        return replace(result, context_sections=tuple(bundle.included_sections))

    @staticmethod
    def _route(text: str) -> str | None:
        if text in {"what's next?", "whats next?", "what's next", "whats next", "next"}:
            return "workspace_next"
        if text in {"continue", "continue.", "resume", "resume."}:
            return "workspace_continue"
        if "how long" in text and "gym" in text:
            return "gym_commitment"
        if any(term in text for term in ("show me the proposal", "why do you want to move", "what changes", "why is algorithms heavier")):
            return "plan_proposal"
        if any(term in text for term in ("what can i cook", "what should i cook", "cook tonight", "meal tonight")):
            return "chef"
        if "concert" in text and any(term in text for term in ("can i go", "room for", "fit", "saturday")):
            return "concert"
        return None

    def _workspace(self, db: Session, user: UserProfile, route: str, ref) -> OrchestrationResult:
        row = self.workspaces.get_foreground_workspace(db, user)
        if row is None:
            answer = "There is no foreground activity to continue."
            return self._render("self_core_workspace", "WORKSPACE_NONE", answer, route)
        changed: tuple[str, ...] = ()
        if route == "workspace_continue" and row.status == "PAUSED":
            row = self.workspaces.resume_workspace(db, user, row.id, foreground=True)
            changed = (f"workspace:{row.id}:r{row.state_revision}",)
        detail = row.current_step or row.current_phase or "the current session"
        verb = "Continue" if route == "workspace_next" else "Resumed"
        answer = f"{verb} {row.workspace_type.lower()}: {detail}."
        return self._render("self_core_workspace", "WORKSPACE_CONTINUITY", answer, route,
                            refs=({"type": "active_workspace", "id": row.id},), state_changes=changed)

    def _gym(self, db: Session, user: UserProfile, situation, now: datetime | None) -> OrchestrationResult:
        when = _aware(now or situation.current_time)
        commitment = next((row for row in list_commitments(db, user, status_filter="active", starts_from=when)
                           if row.starts_at and "gym" in f"{row.title} {row.location or ''}".lower()), None)
        if commitment is None:
            return self._render("self_core_gym", "GYM_COMMITMENT_NOT_FOUND", "I couldn't find an upcoming gym commitment.", "gym_commitment")
        minutes = max(0, ceil((_aware(commitment.starts_at) - when).total_seconds() / 60))
        answer = f"You have {minutes} minutes until {commitment.title}."
        return self._render("self_core_gym", "GYM_COMMITMENT", answer, "gym_commitment",
                            refs=({"type": "commitment", "id": commitment.id},))

    def _proposal(self, db: Session, user: UserProfile) -> OrchestrationResult:
        rows = self.proposals.list_active(db, user, limit=1)
        if not rows:
            return self._render("self_core_proposal", "PROPOSAL_NONE", "There is no active plan proposal.", "plan_proposal")
        row = rows[0]
        effects = ", ".join(f"{key}: {value}" for key, value in list((row.expected_effects_json or {}).items())[:3])
        tradeoffs = "; ".join(str(item) for item in (row.tradeoffs_json or [])[:2])
        answer = f"The proposal is based on {row.reason_code.replace('_', ' ').lower()} and contains {len(row.changes_json or [])} plan changes."
        if effects:
            answer += f" Expected effects: {effects}."
        if tradeoffs:
            answer += f" Trade-offs: {tradeoffs}."
        answer += " It will not change your plan unless you apply it."
        return self._render("self_core_proposal", "PROPOSAL_EXPLAINED", answer, "plan_proposal",
                            refs=({"type": "plan_proposal", "id": row.id},))

    def _chef(self, db: Session, user: UserProfile, request: AssistantMessageRequest) -> OrchestrationResult:
        recommendation = recommend_from_text(db, user, ChefIntentRequest(request=request.message, limit=3, conversation_thread_id=request.thread_id), self.settings)
        if recommendation.options:
            names = ", ".join(item.recipe.name for item in recommendation.options)
            answer = f"Chef found {len(recommendation.options)} grounded options: {names}."
            refs = tuple({"type": "recipe", "id": item.recipe.id} for item in recommendation.options)
        else:
            answer = recommendation.response_text
            refs = ()
        return self._render("self_core_cross_domain", "CHEF_ROUTED", answer, "chef", refs=refs, tool="chef.recommend_from_text")

    def _concert(self, db: Session, user: UserProfile, request: AssistantMessageRequest) -> OrchestrationResult:
        opportunities = list_opportunities(db, user, category=OpportunityType.concert, starts_after=request.now, relevant=True, limit=1, now=request.now)
        budget = discretionary_social_budget_remaining(db, user)
        if not opportunities:
            answer = "I couldn't find a relevant upcoming concert to evaluate. Nothing was added to your plan."
            refs = ()
        else:
            item = opportunities[0]
            feasibility = item.feasibility or {}
            answer = f"{item.title} is the current concert candidate. Schedule feasibility is {str(feasibility.get('schedule_state', 'unknown')).lower()}, and discretionary budget is {budget.status.lower()}. Nothing was booked or scheduled."
            refs = ({"type": "opportunity", "id": item.id},)
        return self._render("self_core_cross_domain", "OPPORTUNITY_COORDINATED", answer, "concert", refs=refs, tool="social.list_opportunities")

    @staticmethod
    def _render(template: str, reason: str, answer: str, route: str, *, refs=(), state_changes=(), tool=None) -> OrchestrationResult:
        fact = StructuredFact(key="answer", value=answer, source_ref=refs[0]["id"] if refs else None)
        intent = CommunicativeIntent(
            purpose=SpeechAct.inform, attention_action=AttentionAction.show_passively, reason_code=reason,
            facts=(fact,), current_state_refs=tuple(f"{item['type']}:{item['id']}" for item in refs),
            response_mode_preference=ResponseModePreference.deterministic, fallback_template_key=template,
        )
        return OrchestrationResult(ResponseComposer().deterministic_text(intent), route, (fact,), tuple(refs), tool, tuple(state_changes))


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
