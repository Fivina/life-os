from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIProviderError
from app.communication.composer import ResponseComposer
from app.communication.schemas import (
    CommunicativeIntent,
    ComposeRequest,
    ComposedResponse,
    ResponseMode,
    ResponseStreamEvent,
    ResponseStreamEventType,
    StructuredFact,
    SpeechAct,
)
from app.conversations.service import ConversationService
from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import AIActionAudit, CognitiveTrace, PlanProposal, UserProfile
from app.decision.traces import DecisionTraceService


logger = get_logger(__name__)


class ResponseCompositionService:
    """Orchestrates rendering, AI usage accounting, message persistence, and audit linkage."""

    def __init__(
        self,
        settings: Settings,
        *,
        gateway: AIGateway | None = None,
        composer: ResponseComposer | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway or AIGateway(settings)
        self.composer = composer or ResponseComposer()
        self.conversations = ConversationService(settings)

    def compose(
        self,
        db: Session,
        user: UserProfile,
        request: ComposeRequest,
    ) -> ComposedResponse | None:
        intent = request.intent
        if not self.settings.response_composer_enabled or not self.composer.should_speak(intent):
            return None
        response_id = str(uuid4())
        mode = self.composer.select_mode(
            intent,
            generative_enabled=self.settings.response_composer_generative_enabled,
        )
        provider = model = None
        fallback_used = False
        started = perf_counter()
        if mode == ResponseMode.deterministic:
            text = self.composer.deterministic_text(intent)
        else:
            try:
                ai_response = self.gateway.complete(
                    db,
                    user,
                    request_id=response_id,
                    assistant_role="RESPONSE_COMPOSER",
                    skill_name="response-composer",
                    skill_version="1",
                    capability=AICapability.economy,
                    request=self.composer.build_request(intent, request.recent_context),
                    conversation_thread_id=intent.conversation_ref,
                    optional=True,
                )
                text = self.composer.validate_generated(
                    intent,
                    ai_response.text,
                    tool_call_count=len(ai_response.tool_calls),
                )
                provider, model = ai_response.provider, ai_response.model
            except (AIProviderError, ValueError) as exc:
                text = self.composer.deterministic_text(intent)
                mode = ResponseMode.deterministic_fallback
                fallback_used = True
                logger.warning(
                    "response_fallback_used",
                    extra={"intent_id": intent.intent_id, "error_type": type(exc).__name__},
                )
        result = self._finalize(
            db,
            user,
            intent=intent,
            response_id=response_id,
            text=text,
            mode=mode,
            provider=provider,
            model=model,
            fallback_used=fallback_used,
            streamed=False,
            persist=request.persist_message,
            latency_ms=round((perf_counter() - started) * 1000),
            estimated_cost_eur=self._estimated_cost(db, response_id),
        )
        logger.info(
            "response_composition_completed",
            extra={"intent_id": intent.intent_id, "mode": mode.value, "latency_ms": round((perf_counter() - started) * 1000)},
        )
        return result

    def stream(
        self,
        db: Session,
        user: UserProfile,
        request: ComposeRequest,
    ) -> Iterator[ResponseStreamEvent]:
        intent = request.intent
        if not self.settings.response_composer_enabled or not self.composer.should_speak(intent):
            return
        response_id = str(uuid4())
        started = perf_counter()
        sequence = 0
        yield ResponseStreamEvent(
            event_type=ResponseStreamEventType.start,
            response_id=response_id,
            conversation_id=intent.conversation_ref,
            sequence=sequence,
        )
        mode = self.composer.select_mode(intent, generative_enabled=self.settings.response_composer_generative_enabled)
        provider = model = None
        fallback_used = False
        emitted = False
        text_parts: list[str] = []
        try:
            if mode == ResponseMode.deterministic:
                text_parts = [self.composer.deterministic_text(intent)]
                sequence += 1
                emitted = True
                yield ResponseStreamEvent(
                    event_type=ResponseStreamEventType.text_delta,
                    response_id=response_id,
                    conversation_id=intent.conversation_ref,
                    sequence=sequence,
                    text_delta=text_parts[0],
                )
            else:
                for chunk in self.gateway.stream(
                    db,
                    user,
                    request_id=response_id,
                    assistant_role="RESPONSE_COMPOSER",
                    skill_name="response-composer",
                    skill_version="1",
                    capability=AICapability.economy,
                    request=self.composer.build_request(intent, request.recent_context),
                    conversation_thread_id=intent.conversation_ref,
                    optional=True,
                ):
                    provider, model = chunk.provider, chunk.model
                    if chunk.text_delta:
                        self.composer.validate_generated(intent, chunk.text_delta)
                        text_parts.append(chunk.text_delta)
                        sequence += 1
                        emitted = True
                        yield ResponseStreamEvent(
                            event_type=ResponseStreamEventType.text_delta,
                            response_id=response_id,
                            conversation_id=intent.conversation_ref,
                            sequence=sequence,
                            text_delta=chunk.text_delta,
                        )
                self.composer.validate_generated(intent, "".join(text_parts))
        except (AIProviderError, ValueError) as exc:
            if emitted:
                sequence += 1
                yield ResponseStreamEvent(
                    event_type=ResponseStreamEventType.error,
                    response_id=response_id,
                    conversation_id=intent.conversation_ref,
                    sequence=sequence,
                    error_code=getattr(exc, "code", "invalid_stream_output"),
                )
                db.rollback()
                return
            text_parts = [self.composer.deterministic_text(intent)]
            mode = ResponseMode.deterministic_fallback
            fallback_used = True
            sequence += 1
            yield ResponseStreamEvent(
                event_type=ResponseStreamEventType.text_delta,
                response_id=response_id,
                conversation_id=intent.conversation_ref,
                sequence=sequence,
                text_delta=text_parts[0],
            )
        result = self._finalize(
            db,
            user,
            intent=intent,
            response_id=response_id,
            text="".join(text_parts),
            mode=mode,
            provider=provider,
            model=model,
            fallback_used=fallback_used,
            streamed=True,
            persist=request.persist_message,
            latency_ms=round((perf_counter() - started) * 1000),
            estimated_cost_eur=self._estimated_cost(db, response_id),
        )
        db.commit()
        sequence += 1
        yield ResponseStreamEvent(
            event_type=ResponseStreamEventType.complete,
            response_id=response_id,
            conversation_id=result.conversation_id,
            message_id=result.message_id,
            sequence=sequence,
            final_response=result.model_copy(update={"world_revision": user.world_revision}),
            world_revision=user.world_revision,
        )

    def intent_for_plan_proposal(
        self,
        proposal: PlanProposal,
        *,
        conversation_ref: str | None = None,
    ) -> CommunicativeIntent:
        snapshot = proposal.trajectory_snapshot_json
        effects = proposal.expected_effects_json
        current_shortfall = (effects.get("projected_shortfall_minutes") or {}).get("current")
        proposed_shortfall = (effects.get("projected_shortfall_minutes") or {}).get("proposed")
        facts = [
            StructuredFact(key="exam_title", value=str(snapshot.get("exam_title") or "The exam"), source_ref=f"exam:{proposal.exam_id}"),
            StructuredFact(key="trajectory_state", value="is below the current target pace", source_ref=f"plan_proposal:{proposal.id}"),
        ]
        if current_shortfall is not None:
            facts.append(StructuredFact(key="current_shortfall_minutes", value=int(current_shortfall), unit="minutes", source_ref=f"plan_proposal:{proposal.id}"))
        if proposed_shortfall is not None:
            facts.append(StructuredFact(key="proposed_shortfall_minutes", value=int(proposed_shortfall), unit="minutes", source_ref=f"plan_proposal:{proposal.id}"))
        return CommunicativeIntent(
            purpose=SpeechAct.propose,
            attention_action=proposal.attention_action,
            reason_code=proposal.reason_code,
            importance=min(100, 50 + proposal.authority_level * 10),
            urgency=float(proposal.trajectory_snapshot_json.get("days_remaining") is not None and proposal.authority_level >= 3),
            facts=tuple(facts),
            current_state_refs=(f"plan:{proposal.current_plan_id}:v{proposal.current_plan_version}",),
            conversation_ref=conversation_ref,
            cognitive_trace_ref=proposal.source_trace_id,
            plan_proposal_ref=proposal.id,
            recommended_next_action="Review the structured proposal before applying it.",
            must_include=("Review the proposal before applying any changes.",),
            must_not_claim=("the proposal is already applied", "exam failure is certain", "the user lacks motivation"),
            fallback_template_key="plan_proposal",
            metadata={"proposal_status": proposal.status},
        )

    def _finalize(
        self,
        db: Session,
        user: UserProfile,
        *,
        intent: CommunicativeIntent,
        response_id: str,
        text: str,
        mode: ResponseMode,
        provider: str | None,
        model: str | None,
        fallback_used: bool,
        streamed: bool,
        persist: bool,
        latency_ms: int,
        estimated_cost_eur: float | None,
    ) -> ComposedResponse:
        thread = None
        message = None
        if persist:
            thread = self.conversations.resolve_thread(
                db,
                user,
                thread_id=intent.conversation_ref,
                default_skill="response-composer",
            )
            message = self.conversations.append_message(
                db,
                user,
                thread,
                role="assistant",
                content=text,
                skill_name="response-composer",
                request_id=response_id,
                metadata={
                    "communicative_intent": intent.model_dump(mode="json"),
                    "response_policy_version": self.composer.policy_version,
                    "response_mode": mode.value,
                    "provider": provider,
                    "model": model,
                    "capability": AICapability.economy.value if provider else None,
                    "fallback_used": fallback_used,
                    "streamed": streamed,
                    "latency_ms": latency_ms,
                    "estimated_cost_eur": estimated_cost_eur,
                    "cognitive_trace_ref": intent.cognitive_trace_ref,
                    "plan_proposal_ref": intent.plan_proposal_ref,
                },
            )
        result = ComposedResponse(
            intent_id=intent.intent_id,
            intent_version=intent.version,
            response_id=response_id,
            text=text,
            mode=mode,
            conversation_id=thread.id if thread else intent.conversation_ref,
            message_id=message.id if message else None,
            cognitive_trace_ref=intent.cognitive_trace_ref,
            plan_proposal_ref=intent.plan_proposal_ref,
            provider=provider,
            model=model,
            capability=AICapability.economy.value if provider else None,
            fallback_used=fallback_used,
            streamed=streamed,
            latency_ms=latency_ms,
            estimated_cost_eur=estimated_cost_eur,
            world_revision=user.world_revision,
            created_at=datetime.now(UTC),
        )
        self._audit(db, user, intent, result)
        return result

    @staticmethod
    def _audit(db: Session, user: UserProfile, intent: CommunicativeIntent, result: ComposedResponse) -> None:
        if not intent.cognitive_trace_ref:
            return
        trace = db.scalar(select(CognitiveTrace).where(CognitiveTrace.id == intent.cognitive_trace_ref, CognitiveTrace.user_id == user.id))
        if trace is None:
            return
        DecisionTraceService().add_audit(
            db,
            user,
            trace=trace,
            audit_type="response_composed",
            downstream_action_ref=result.message_id,
            outcome={"response_mode": result.mode.value, "message_id": result.message_id},
            training_eligible=False,
            metadata={
                "communicative_intent_id": intent.intent_id,
                "communicative_intent_version": intent.version,
                "response_policy_version": result.policy_version,
                "provider": result.provider,
                "model": result.model,
                "capability": result.capability,
                "fallback_used": result.fallback_used,
                "streamed": result.streamed,
                "latency_ms": result.latency_ms,
                "estimated_cost_eur": result.estimated_cost_eur,
            },
        )

    @staticmethod
    def _estimated_cost(db: Session, request_id: str) -> float | None:
        value = db.scalar(select(AIActionAudit.estimated_cost).where(AIActionAudit.request_id == request_id))
        return float(value) if value is not None else None
