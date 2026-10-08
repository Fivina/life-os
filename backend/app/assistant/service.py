from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIProviderError
from app.assistant.audit import record_ai_audit
from app.assistant.context_builder import ContextBuilderV2
from app.assistant.proposals import create_action_proposal, proposal_read as _proposal_read
from app.assistant.schemas import (
    AssistantIntentType,
    AssistantMessageRequest,
    AssistantMutationResult,
    AssistantResponse,
    AssistantResponseType,
    ModelTier,
)
from app.assistant.tools import AssistantToolError, ToolRegistry, semantic_error_response
from app.conversations.service import ConversationService
from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import AssistantActionProposal, ConversationThread, Movie, UserProfile
from app.feedback.command import match_log_feedback
from app.feedback.service import FeedbackService
from app.attention.schemas import AttentionAction
from app.communication.composer import ResponseComposer
from app.communication.schemas import CommunicativeIntent, ResponseModePreference, SpeechAct, StructuredFact
from app.memory.curator import MemoryCurator
from app.memory.jobs import enqueue as enqueue_memory_job
from app.memory.embeddings import EmbeddingService
from app.memory.retrieval import MemoryRetrievalService
from app.memory.service import MemoryService
from app.notebook.command import match_implementation_idea
from app.notebook.schemas import NotebookEntryCreate
from app.notebook.service import create_entry as create_notebook_entry
from app.movies.command import match_prospective_movie
from app.movies.prospective import create_movie_thread
from app.movies.schemas import MovieCreate, ProspectiveMovieCreate
from app.movies.service import save_movie
from app.skills.registry import SkillRegistry
from app.skills.runtime import SkillRuntime
from app.decision.traces import DecisionTraceService
from app.self_core.orchestrator import SelfCoreOrchestrator
from app.capture.schemas import QuickCaptureCreate
from app.capture.service import QuickCaptureService
from app.intelligence_settings.service import IntelligenceSettingsService

logger = get_logger(__name__)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _tier_for_message(message: str) -> ModelTier:
    lowered = message.lower()
    if any(term in lowered for term in ["complex", "synthesize", "across fitness and learning", "tradeoff", "trade-off"]):
        return ModelTier.strong
    return ModelTier.standard


class AssistantService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tools = ToolRegistry()
        self.skills = SkillRegistry(settings, self.tools).load()
        self.conversations = ConversationService(settings)
        self.gateway = AIGateway(settings)
        self.embeddings = EmbeddingService(settings, self.gateway)
        self.memories = MemoryService(self.embeddings)
        self.memory_retrieval = MemoryRetrievalService(settings, self.embeddings)
        self.memory_curator = MemoryCurator(self.gateway, self.memories)
        self.context = ContextBuilderV2(settings, self.skills, self.tools, self.conversations, self.memory_retrieval)
        self.runtime = SkillRuntime(self.skills, self.tools, self.context, self.gateway)
        self.agent_runtime = None
        if settings.agent_runtime == "sdk":
            from app.agents.runtime import AgentsSDKRuntime

            self.agent_runtime = AgentsSDKRuntime(settings, self.skills, self.tools, self.context)
        self.orchestrator = SelfCoreOrchestrator(settings, self.context)
        self.feedback = FeedbackService(settings)
        self.quick_capture = QuickCaptureService(settings)
        self.intelligence_settings = IntelligenceSettingsService(settings)

    def _skill_for_user(self, db: Session, user: UserProfile, role):
        skill = self.skills.for_role(role)
        if not self.intelligence_settings.skill_enabled(db, user, skill.manifest.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The {skill.manifest.name} skill is disabled in Intelligence settings.",
            )
        return skill

    def handle_message(self, db: Session, user: UserProfile, request: AssistantMessageRequest) -> AssistantResponse:
        request_id = str(uuid4())
        prospective_movie = match_prospective_movie(request.message)
        if prospective_movie is not None:
            skill = self._skill_for_user(db, user, request.role)
            thread = self.conversations.resolve_thread(db, user, thread_id=request.thread_id, default_skill=skill.manifest.name)
            user_message = self.conversations.append_message(
                db, user, thread, role="user", content=request.message, skill_name=skill.manifest.name, request_id=request_id
            )
            matches = list(db.scalars(select(Movie).where(Movie.title.ilike(prospective_movie)).limit(2)))
            if len(matches) == 1:
                movie = matches[0]
            else:
                movie_read = save_movie(db, user, MovieCreate(title=prospective_movie))
                movie = db.get(Movie, movie_read.id)
            assert movie is not None
            prospective = create_movie_thread(db, user, movie, ProspectiveMovieCreate(movie_id=movie.id))
            response = AssistantResponse(
                message=f"Saved {movie.title} for its release window. Nothing was booked or added to your calendar.",
                role_used=request.role,
                response_type=AssistantResponseType.mutation_result,
                mutation_result=AssistantMutationResult(
                    tool_name="movies.watch_when_available", entity_type="prospective_thread", entity_id=prospective.id,
                    world_revision=user.world_revision,
                    result={"status": "dormant", "movie_id": movie.id, "calendar_changed": False, "booking_created": False},
                ),
                entity_references=[{"type": "movie", "id": movie.id}, {"type": "prospective_thread", "id": prospective.id}],
                request_id=request_id, model_tier=ModelTier.no_ai, skill_name=skill.manifest.name, skill_version=skill.manifest.version,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        implementation_idea = match_implementation_idea(request.message)
        if implementation_idea is not None:
            skill = self._skill_for_user(db, user, request.role)
            thread = self.conversations.resolve_thread(db, user, thread_id=request.thread_id, default_skill=skill.manifest.name)
            user_message = self.conversations.append_message(
                db, user, thread, role="user", content=request.message, skill_name=skill.manifest.name, request_id=request_id
            )
            title = " ".join(implementation_idea.split())[:120]
            entry = create_notebook_entry(
                db, user,
                NotebookEntryCreate(entry_type="IMPLEMENTATION_IDEA", title=title, content=implementation_idea,
                                    source="assistant_command", source_ref=user_message.id,
                                    conversation_thread_id=thread.id),
                idempotency_key=f"assistant-message:{user_message.id}",
            )
            intent = CommunicativeIntent(
                purpose=SpeechAct.confirm, attention_action=AttentionAction.show_passively,
                reason_code="NOTEBOOK_IDEA_SAVED",
                facts=(StructuredFact(key="notebook_entry_id", value=entry.id, source_ref=f"notebook:{entry.id}"),),
                conversation_ref=thread.id, response_mode_preference=ResponseModePreference.deterministic,
                fallback_template_key="notebook_idea_saved",
                must_not_claim=("roadmap changed", "task created", "goal created", "plan changed"),
            )
            response = AssistantResponse(
                message=ResponseComposer().deterministic_text(intent), role_used=request.role,
                response_type=AssistantResponseType.mutation_result,
                mutation_result=AssistantMutationResult(tool_name="notebook.park_implementation_idea", entity_type="notebook_entry",
                                                        entity_id=entry.id, world_revision=user.world_revision,
                                                        result={"status": "stored", "execution_authority": "NONE"}),
                entity_references=[{"type": "notebook_entry", "id": entry.id}], request_id=request_id,
                model_tier=ModelTier.no_ai, skill_name=skill.manifest.name, skill_version=skill.manifest.version,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        reserved_feedback = match_log_feedback(request.message)
        if reserved_feedback.matched:
            thread = None
            if request.thread_id:
                thread = self.conversations.get_thread(db, user, request.thread_id)
            else:
                recent_threads = self.conversations.list_threads(db, user, limit=1)
                thread = recent_threads[0] if recent_threads else None
            feedback_state = self.feedback.start_from_command(
                db,
                user,
                command=request.message,
                parent_conversation_id=thread.id if thread else None,
            )
            messages = {
                "STARTED": "Feedback opened. A few focused ratings will help evaluate that decision.",
                "ACTIVE_SESSION_EXISTS": "The current feedback session is still open.",
                "NO_TARGET_TRACE": "I could not find a recent decision in this context to evaluate.",
                "FEEDBACK_DISABLED": "Intelligence feedback is currently disabled.",
            }
            return AssistantResponse(
                message=messages.get(feedback_state.result_code, "Feedback is unavailable for this interaction."),
                role_used=request.role,
                response_type=(
                    AssistantResponseType.feedback
                    if feedback_state.session_id
                    else AssistantResponseType.no_action
                ),
                request_id=request_id,
                model_tier=ModelTier.no_ai,
                thread_id=thread.id if thread else None,
                feedback_session_id=feedback_state.session_id,
                feedback_status=feedback_state.status.value if feedback_state.status else feedback_state.result_code,
                feedback_question=(
                    feedback_state.clarification.model_dump(mode="json")
                    if feedback_state.clarification
                    else feedback_state.next_question.model_dump(mode="json") if feedback_state.next_question else None
                ),
                error_code=(feedback_state.result_code if feedback_state.session_id is None else None),
            )
        if self.quick_capture.is_likely_capture(request.message):
            skill = self._skill_for_user(db, user, request.role)
            thread = self.conversations.resolve_thread(db, user, thread_id=request.thread_id, default_skill=skill.manifest.name)
            user_message = self.conversations.append_message(
                db, user, thread, role="user", content=request.message,
                skill_name=skill.manifest.name, request_id=request_id,
            )
            captured = self.quick_capture.capture(
                db, user,
                QuickCaptureCreate(
                    text=request.message, conversation_thread_id=thread.id, source_message_id=user_message.id,
                    now=request.now, timezone=request.timezone,
                ),
                idempotency_key=f"assistant-message:{user_message.id}",
            )
            if captured.review_required:
                message = f"I captured this, but it needs one check before anything changes: {captured.reason_codes[-1].replace('_', ' ') if captured.reason_codes else 'details are uncertain'}."
            else:
                message = f"I understood this as {captured.intent_type.value.replace('_', ' ').lower()}. Review the preview and confirm it before I change your records."
            response = AssistantResponse(
                message=message, role_used=request.role, response_type=AssistantResponseType.proposal,
                mutation_result=AssistantMutationResult(
                    tool_name="quick_capture.propose", entity_type="quick_capture", entity_id=captured.id,
                    world_revision=user.world_revision,
                    result={
                        "status": captured.status.value, "policy_outcome": captured.policy_outcome.value,
                        "structured_preview": captured.structured_payload, "review_item_id": captured.review_item_id,
                        "capture_version": captured.version,
                        "canonical_state_changed": False,
                    },
                ),
                entity_references=[{"type": "quick_capture", "id": captured.id}] + ([{"type": "review_item", "id": captured.review_item_id}] if captured.review_item_id else []),
                request_id=request_id, model_tier=ModelTier.no_ai, skill_name=skill.manifest.name,
                skill_version=skill.manifest.version, cognitive_trace_ref=None, orchestration_route="quick_capture",
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        tier = _tier_for_message(request.message)
        started = perf_counter()
        provider = None
        model = None
        skill = self._skill_for_user(db, user, request.role)
        thread = self.conversations.resolve_thread(
            db,
            user,
            thread_id=request.thread_id,
            default_skill=skill.manifest.name,
        )
        user_message = self.conversations.append_message(
            db,
            user,
            thread,
            role="user",
            content=request.message,
            skill_name=skill.manifest.name,
            request_id=request_id,
        )
        orchestrated = self.orchestrator.try_handle(
            db, user, request=request, thread=thread, skill=skill, request_id=request_id
        )
        if orchestrated is not None:
            workspace_ref = next((item["id"] for item in orchestrated.entity_references if item.get("type") == "active_workspace"), None)
            trace = DecisionTraceService().record_orchestration(
                db, user, request_id=request_id, conversation_thread_id=thread.id,
                workspace_ref=workspace_ref, route=orchestrated.route,
                context_sections=orchestrated.context_sections, tool_name=orchestrated.tool_name,
                entity_refs=orchestrated.entity_references,
                state_change_refs=orchestrated.state_change_refs, response_text=orchestrated.message,
            )
            response = AssistantResponse(
                message=orchestrated.message, role_used=request.role,
                response_type=(AssistantResponseType.mutation_result if orchestrated.state_change_refs else AssistantResponseType.information),
                mutation_result=(AssistantMutationResult(
                    tool_name=orchestrated.tool_name or orchestrated.route,
                    entity_type="active_workspace" if workspace_ref else None,
                    entity_id=workspace_ref, world_revision=user.world_revision,
                    result={"state_change_refs": list(orchestrated.state_change_refs)},
                ) if orchestrated.state_change_refs else None),
                entity_references=list(orchestrated.entity_references), request_id=request_id,
                model_tier=ModelTier.no_ai, skill_name=skill.manifest.name,
                skill_version=skill.manifest.version, cognitive_trace_ref=trace.id,
                orchestration_route=orchestrated.route,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        if not self.settings.memory_candidate_gate_enabled or self.memory_curator.should_inspect(request.message):
            try:
                if request.message.strip().lower().startswith("remember"):
                    with db.begin_nested():
                        self.memory_curator.capture(
                            db,
                            user,
                            thread,
                            message_id=user_message.id,
                            message=request.message,
                            request_id=request_id,
                        )
                else:
                    enqueue_memory_job(
                        db,
                        user,
                        job_type="memory_candidate.process",
                        source_type="conversation_message",
                        source_id=user_message.id,
                        payload={"thread_id": thread.id},
                    )
            except Exception as exc:
                # Memory is helpful context, never a reason to fail the assistant request.
                logger.warning(
                    "Optional assistant memory capture failed",
                    extra={"user_id": user.id, "request_id": request_id, "error_type": type(exc).__name__},
                )
        per_user_agents_enabled = self.intelligence_settings.live_agents_enabled(db, user)
        if self.settings.agent_runtime == "sdk" or per_user_agents_enabled:
            if self.agent_runtime is None:
                from app.agents.runtime import AgentsSDKRuntime

                self.agent_runtime = AgentsSDKRuntime(self.settings, self.skills, self.tools, self.context)
            response = self.agent_runtime.run(
                db, user, request_id=request_id, request=request, thread=thread, preferred_tier=tier,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        try:
            runtime_result = self.runtime.interpret(
                db,
                user,
                request_id=request_id,
                request=request,
                thread=thread,
                preferred_tier=tier,
            )
            provider = runtime_result.provider
            model = runtime_result.model
            intent = runtime_result.intent
            capability = runtime_result.capability
            tier = intent.model_tier if intent.model_tier != ModelTier.no_ai else tier
        except AIProviderError as exc:
            record_ai_audit(
                db,
                user,
                assistant_role=request.role,
                request_id=request_id,
                provider=provider,
                model=model,
                model_tier=tier,
                status="error",
                error_code=exc.code,
                duration_ms=round((perf_counter() - started) * 1000),
            )
            response = AssistantResponse(
                message=exc.message,
                role_used=request.role,
                response_type=AssistantResponseType.error,
                request_id=request_id,
                provider=provider,
                model=model,
                model_tier=tier,
                skill_name=skill.manifest.name,
                skill_version=skill.manifest.version,
                error_code=exc.code,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)

        if intent.type == AssistantIntentType.clarification_required:
            record_ai_audit(db, user, assistant_role=request.role, request_id=request_id, provider=provider, model=model, model_tier=tier, status="clarification", duration_ms=round((perf_counter() - started) * 1000))
            response = AssistantResponse(
                message=intent.user_facing_summary or "Can you clarify that?",
                role_used=request.role,
                response_type=AssistantResponseType.clarification,
                request_id=request_id,
                provider=provider,
                model=model,
                model_tier=tier,
                capability=capability.value,
                skill_name=skill.manifest.name,
                skill_version=skill.manifest.version,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)
        if intent.type == AssistantIntentType.discussion:
            record_ai_audit(db, user, assistant_role=request.role, request_id=request_id, provider=provider, model=model, model_tier=ModelTier.no_ai, status="no_action", duration_ms=round((perf_counter() - started) * 1000))
            response = AssistantResponse(
                message=intent.user_facing_summary or "No Life OS data was changed.",
                role_used=request.role,
                response_type=AssistantResponseType.no_action,
                request_id=request_id,
                provider=provider,
                model=model,
                model_tier=ModelTier.no_ai,
                capability=capability.value,
                skill_name=skill.manifest.name,
                skill_version=skill.manifest.version,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)

        try:
            tool = self.tools.get(intent.tool_name)
            self.tools.authorize(tool, request.role)
            args = tool.validate_args(intent.arguments)
        except (AssistantToolError, ValidationError) as exc:
            code = exc.code if isinstance(exc, AssistantToolError) else "invalid_tool_arguments"
            message = exc.message if isinstance(exc, AssistantToolError) else "The tool arguments were invalid."
            record_ai_audit(db, user, assistant_role=request.role, request_id=request_id, provider=provider, model=model, model_tier=tier, status="rejected", tool_name=intent.tool_name, error_code=code, duration_ms=round((perf_counter() - started) * 1000))
            response = AssistantResponse(message=message, role_used=request.role, response_type=AssistantResponseType.error, request_id=request_id, provider=provider, model=model, model_tier=tier, capability=capability.value, skill_name=skill.manifest.name, skill_version=skill.manifest.version, error_code=code)
            return self._finalize(db, user, thread, response, skill.manifest.name)

        if tool.kind == "MUTATION" and self.tools.requires_confirmation(tool, intent.requires_confirmation):
            proposal = create_action_proposal(
                db, user, role=request.role, tool=tool, args=args, summary=intent.user_facing_summary,
            )
            record_ai_audit(db, user, assistant_role=request.role, request_id=request_id, provider=provider, model=model, model_tier=tier, status="proposed", tool_name=tool.name, proposal_id=proposal.id, duration_ms=round((perf_counter() - started) * 1000))
            response = AssistantResponse(
                message="Review this proposed action before I change Life OS.",
                role_used=request.role,
                response_type=AssistantResponseType.proposal,
                proposed_action=_proposal_read(proposal),
                request_id=request_id,
                provider=provider,
                model=model,
                model_tier=tier,
                capability=capability.value,
                skill_name=skill.manifest.name,
                skill_version=skill.manifest.version,
            )
            return self._finalize(db, user, thread, response, skill.manifest.name)

        try:
            result = self.tools.execute(db, user, tool, args)
        except HTTPException as exc:
            tool_exc = semantic_error_response(exc)
            response = self._error(db, user, request.role, request_id, provider, model, tier, tool.name, tool_exc, started)
            return self._finalize(db, user, thread, response, skill.manifest.name)
        except AssistantToolError as exc:
            response = self._error(db, user, request.role, request_id, provider, model, tier, tool.name, exc, started)
            return self._finalize(db, user, thread, response, skill.manifest.name)
        mutation = AssistantMutationResult(tool_name=tool.name, entity_type=result.entity_type, entity_id=result.entity_id, world_revision=user.world_revision, result=result.result)
        record_ai_audit(db, user, assistant_role=request.role, request_id=request_id, provider=provider, model=model, model_tier=tier, status="executed" if tool.kind == "MUTATION" else "read", tool_name=tool.name, mutation_id=result.entity_id, duration_ms=round((perf_counter() - started) * 1000))
        response_type = AssistantResponseType.mutation_result if tool.kind == "MUTATION" else (AssistantResponseType.information if intent.type != AssistantIntentType.explain else AssistantResponseType.information)
        response_message = result.message
        if tool.kind == "READ_ONLY":
            try:
                response_message = self.runtime.finalize_tool_result(
                    db,
                    user,
                    request_id=request_id,
                    request=request,
                    runtime_result=runtime_result,
                    tool_name=tool.name,
                    tool_result=result.result,
                    tool_message=result.message,
                )
            except AIProviderError:
                response_message = result.message
        response = AssistantResponse(
            message=response_message,
            role_used=request.role,
            response_type=response_type,
            mutation_result=mutation if tool.kind == "MUTATION" else None,
            explanation=result.explanation,
            entity_references=[{"type": result.entity_type, "id": result.entity_id}] if result.entity_type and result.entity_id else [],
            request_id=request_id,
            provider=provider,
            model=model,
            model_tier=tier,
            capability=capability.value,
            skill_name=skill.manifest.name,
            skill_version=skill.manifest.version,
        )
        return self._finalize(db, user, thread, response, skill.manifest.name)

    def _finalize(
        self,
        db: Session,
        user: UserProfile,
        thread: ConversationThread,
        response: AssistantResponse,
        skill_name: str,
    ) -> AssistantResponse:
        message = self.conversations.append_message(
            db,
            user,
            thread,
            role="assistant",
            content=response.message,
            skill_name=skill_name,
            request_id=response.request_id,
            metadata={
                "response_type": response.response_type.value,
                "error_code": response.error_code,
                "cognitive_trace_ref": response.cognitive_trace_ref,
                "orchestration_route": response.orchestration_route,
                "provider": response.provider,
                "model": response.model,
                "work_log": [item.model_dump(mode="json") for item in response.work_log],
                "proposal_id": response.proposed_action.id if response.proposed_action is not None else None,
            },
        )
        self.conversations.compact_if_needed(db, user, thread)
        if response.proposed_action is not None:
            proposal = db.get(AssistantActionProposal, response.proposed_action.id)
            if proposal is not None and proposal.status == "pending":
                proposal.expected_world_revision = user.world_revision
                response.proposed_action.expected_world_revision = user.world_revision
        response.thread_id = thread.id
        response.assistant_message_id = message.id
        return response

    def confirm_proposal(self, db: Session, user: UserProfile, proposal_id: str) -> AssistantResponse:
        request_id = str(uuid4())
        proposal = self._read_proposal(db, user, proposal_id)
        if proposal.status == "confirmed" and proposal.result_json:
            result = proposal.result_json
            return AssistantResponse(
                message="This proposal was already confirmed.",
                role_used=proposal.assistant_role,
                response_type=AssistantResponseType.mutation_result,
                mutation_result=AssistantMutationResult.model_validate(result["mutation_result"]),
                request_id=request_id,
                model_tier=ModelTier.no_ai,
            )
        if proposal.status != "pending":
            return AssistantResponse(message=f"This proposal is already {proposal.status}.", role_used=proposal.assistant_role, response_type=AssistantResponseType.no_action, request_id=request_id, model_tier=ModelTier.no_ai)
        if _aware_utc(proposal.expires_at) < datetime.now(UTC):
            proposal.status = "expired"
            return AssistantResponse(message="This proposal expired. Please ask again.", role_used=proposal.assistant_role, response_type=AssistantResponseType.error, request_id=request_id, model_tier=ModelTier.no_ai, error_code="proposal_expired")
        if proposal.expected_world_revision is not None and proposal.expected_world_revision != user.world_revision:
            return AssistantResponse(
                message="Life OS changed after this proposal was made. Please review a fresh proposal before confirming.",
                role_used=proposal.assistant_role,
                response_type=AssistantResponseType.error,
                request_id=request_id,
                model_tier=ModelTier.no_ai,
                error_code="stale_proposal",
            )
        try:
            tool = self.tools.get(proposal.tool_name)
            self.tools.authorize(tool, proposal.assistant_role)
            args = tool.validate_args(proposal.arguments_json)
            result = self.tools.execute(db, user, tool, args, idempotency_key=proposal.idempotency_key or f"assistant-proposal:{proposal.id}")
        except HTTPException as exc:
            return self._error(db, user, proposal.assistant_role, request_id, "none", None, ModelTier.no_ai, proposal.tool_name, semantic_error_response(exc), perf_counter())
        except (AssistantToolError, ValidationError) as exc:
            code = exc.code if isinstance(exc, AssistantToolError) else "invalid_tool_arguments"
            message = exc.message if isinstance(exc, AssistantToolError) else "The proposal arguments are invalid."
            return AssistantResponse(message=message, role_used=proposal.assistant_role, response_type=AssistantResponseType.error, request_id=request_id, model_tier=ModelTier.no_ai, error_code=code)
        mutation = AssistantMutationResult(tool_name=tool.name, entity_type=result.entity_type, entity_id=result.entity_id, world_revision=user.world_revision, result=result.result)
        proposal.status = "confirmed"
        proposal.result_json = {"mutation_result": mutation.model_dump(mode="json"), "message": result.message}
        proposal.version += 1
        record_ai_audit(db, user, assistant_role=proposal.assistant_role, request_id=request_id, provider="none", model=None, model_tier=ModelTier.no_ai, status="confirmed", tool_name=tool.name, proposal_id=proposal.id, mutation_id=result.entity_id)
        return AssistantResponse(
            message=result.message,
            role_used=proposal.assistant_role,
            response_type=AssistantResponseType.mutation_result,
            mutation_result=mutation,
            entity_references=[{"type": result.entity_type, "id": result.entity_id}] if result.entity_type and result.entity_id else [],
            request_id=request_id,
            model_tier=ModelTier.no_ai,
        )

    def cancel_proposal(self, db: Session, user: UserProfile, proposal_id: str) -> AssistantResponse:
        proposal = self._read_proposal(db, user, proposal_id)
        request_id = str(uuid4())
        if proposal.status != "pending":
            return AssistantResponse(
                message=f"This proposal was already {proposal.status}. No additional data was changed.",
                role_used=proposal.assistant_role, response_type=AssistantResponseType.no_action,
                request_id=request_id, model_tier=ModelTier.no_ai,
            )
        proposal.status = "cancelled"
        proposal.version += 1
        record_ai_audit(db, user, assistant_role=proposal.assistant_role, request_id=request_id, provider="none", model=None, model_tier=ModelTier.no_ai, status="cancelled", tool_name=proposal.tool_name, proposal_id=proposal.id)
        return AssistantResponse(message="Cancelled. No Life OS data was changed.", role_used=proposal.assistant_role, response_type=AssistantResponseType.no_action, request_id=request_id, model_tier=ModelTier.no_ai)

    def _read_proposal(self, db: Session, user: UserProfile, proposal_id: str) -> AssistantActionProposal:
        proposal = db.scalar(select(AssistantActionProposal).where(AssistantActionProposal.id == proposal_id, AssistantActionProposal.user_id == user.id))
        if proposal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.")
        return proposal

    def _error(
        self,
        db: Session,
        user: UserProfile,
        role,
        request_id: str,
        provider: str | None,
        model: str | None,
        tier: ModelTier,
        tool_name: str | None,
        exc: AssistantToolError,
        started: float,
    ) -> AssistantResponse:
        record_ai_audit(db, user, assistant_role=role, request_id=request_id, provider=provider, model=model, model_tier=tier, status="error", tool_name=tool_name, error_code=exc.code, duration_ms=round((perf_counter() - started) * 1000))
        return AssistantResponse(message=exc.message, role_used=role, response_type=AssistantResponseType.error, request_id=request_id, provider=provider, model=model, model_tier=tier, error_code=exc.code)
