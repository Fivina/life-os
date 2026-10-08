from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attention.curiosity import CuriosityPolicy
from app.attention.manager import AttentionManager
from app.attention.schemas import (
    AttentionAction,
    AttentionCandidate,
    AttentionDecision,
    CuriosityAction,
    CuriosityInputs,
)
from app.attention.service import AttentionItemService
from app.cognition.contributors import DEFAULT_COGNITIVE_CONTRIBUTORS
from app.cognition.schemas import CognitiveCycleResult, CognitiveCycleStatus
from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import CognitiveTrace, UserIntelligenceSettings, UserProfile
from app.decision.context import DecisionContextBuilder
from app.decision.contributors import DecisionContributorRegistry
from app.decision.errors import DecisionError
from app.decision.gateway import DecisionGateway
from app.decision.schemas import CognitiveEvent, DecisionQuestionRequest, ProvenanceReference
from app.decision.traces import DecisionTraceService
from app.workspaces.situation import BroadContext, GlobalWorkspace, GlobalWorkspaceBuilder


logger = get_logger(__name__)
MAX_ACTIVATED_CONTRIBUTORS = 4
MAX_QUESTIONS_PER_CONTRIBUTOR = 4
MAX_TOTAL_QUESTIONS = 12
ACTION_RANK = {
    AttentionAction.silent: 0,
    AttentionAction.act_silently: 1,
    AttentionAction.show_passively: 2,
    AttentionAction.mention_when_natural: 3,
    AttentionAction.ask: 4,
    AttentionAction.propose: 5,
    AttentionAction.interrupt: 6,
    AttentionAction.escalate_to_gemini: 7,
}
SURFACEABLE_ACTIONS = {
    AttentionAction.show_passively,
    AttentionAction.mention_when_natural,
    AttentionAction.ask,
    AttentionAction.propose,
    AttentionAction.interrupt,
    AttentionAction.escalate_to_gemini,
}


class CognitiveCycleRunner:
    """Coordinates one bounded cognition pass without prose, tools, or domain mutation."""

    def __init__(
        self,
        settings: Settings,
        *,
        workspace_builder: GlobalWorkspaceBuilder | None = None,
        contributor_registry: DecisionContributorRegistry | None = None,
        context_builder: DecisionContextBuilder | None = None,
        decision_gateway: DecisionGateway | None = None,
        attention_manager: AttentionManager | None = None,
        curiosity_policy: CuriosityPolicy | None = None,
        attention_items: AttentionItemService | None = None,
        trace_service: DecisionTraceService | None = None,
    ):
        self.settings = settings
        self.workspace_builder = workspace_builder or GlobalWorkspaceBuilder()
        self.contributor_registry = contributor_registry or DecisionContributorRegistry(DEFAULT_COGNITIVE_CONTRIBUTORS)
        self.context_builder = context_builder or DecisionContextBuilder()
        self.decision_gateway = decision_gateway or DecisionGateway(settings)
        self.attention_manager = attention_manager or AttentionManager()
        self.curiosity_policy = curiosity_policy or CuriosityPolicy()
        self.attention_items = attention_items or AttentionItemService()
        self.trace_service = trace_service or DecisionTraceService()

    def run(
        self,
        db: Session,
        user: UserProfile,
        event: CognitiveEvent,
        *,
        now: datetime | None = None,
        broad_context: BroadContext = BroadContext.unknown,
        goal_states: dict[str, str] | None = None,
        trigger_observations: dict[str, str | bool | int | float | None] | None = None,
    ) -> CognitiveCycleResult:
        cycle_id = str(uuid4())
        when = now or datetime.now(UTC)
        if not self.settings.cognitive_workspace_enabled or not self.settings.attention_policy_enabled:
            return self._silent_result(cycle_id, CognitiveCycleStatus.disabled, "cognition_disabled")

        errors: list[str] = []
        try:
            situation = self.workspace_builder.build(
                db,
                user,
                now=when,
                broad_context=broad_context,
                conversation_thread_ref=event.conversation_thread_id,
                goal_states=goal_states,
                trigger_observations=trigger_observations,
            )
        except Exception as exc:
            logger.exception("cognitive_cycle_situation_failed", extra={"cycle_id": cycle_id, "error_type": type(exc).__name__})
            return self._silent_result(cycle_id, CognitiveCycleStatus.degraded, "situation_build_failed", errors=(type(exc).__name__,))

        activation = self.contributor_registry.activate(event, max_contributors=MAX_ACTIVATED_CONTRIBUTORS)
        requests: list[tuple[str, str, DecisionQuestionRequest]] = []
        for contributor in activation.contributors:
            contributed = contributor.contribute(event=event, state={"situation": situation})
            if len(contributed) > MAX_QUESTIONS_PER_CONTRIBUTOR:
                errors.append(f"contributor_question_bound:{contributor.descriptor.contributor_id}")
                contributed = contributed[:MAX_QUESTIONS_PER_CONTRIBUTOR]
            for request in contributed:
                if len(requests) >= MAX_TOTAL_QUESTIONS:
                    errors.append("cycle_question_bound")
                    break
                requests.append((contributor.descriptor.contributor_id, contributor.descriptor.version, request))

        if not requests:
            return CognitiveCycleResult(
                cycle_id=cycle_id,
                status=CognitiveCycleStatus.completed,
                situation_snapshot_ref=situation.snapshot_ref,
                activated_contributors=tuple(item.descriptor.contributor_id for item in activation.contributors),
                truncated_contributors=activation.truncated_contributor_ids,
                attention_action=AttentionAction.silent,
                attention_reason_code="no_relevant_contributors",
                eligible_prospective_thread_refs=tuple(ref.ref_id for ref in situation.eligible_prospective_threads),
            )

        decisions: list[AttentionDecision] = []
        trace_refs: list[str] = []
        question_refs: list[str] = []
        for contributor_id, contributor_version, request in requests:
            question_ref = f"{request.question.question_id}:v{request.question.question_version}"
            question_refs.append(question_ref)
            try:
                context = self._build_context(event, request, situation)
                execution = self.decision_gateway.evaluate(
                    db,
                    user,
                    event=event,
                    question=request.question,
                    context=context,
                    skill_name=contributor_id,
                    skill_version=contributor_version,
                    trace_metadata={
                        "cycle_id": cycle_id,
                        "situation_snapshot_ref": situation.snapshot_ref,
                        "situation_world_revision": situation.world_revision,
                        "activated_contributors": [item.descriptor.contributor_id for item in activation.contributors],
                        "activated_contributor_versions": {
                            item.descriptor.contributor_id: item.descriptor.version for item in activation.contributors
                        },
                        "attention_policy_version": self.attention_manager.policy_version,
                        "curiosity_policy_version": self.curiosity_policy.policy_version,
                        "eligible_prospective_thread_refs": [ref.ref_id for ref in situation.eligible_prospective_threads],
                    },
                )
                if execution.trace_id:
                    trace_refs.append(execution.trace_id)
                user_policy = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
                decisions.append(
                    self._attention_decision(
                        event,
                        request,
                        execution.result.selected_answer,
                        execution.result.confidence or 0,
                        execution.trace_id,
                        situation,
                        when,
                        user_policy,
                    )
                )
            except (DecisionError, ValidationError, ValueError, TypeError) as exc:
                errors.append(f"{question_ref}:{type(exc).__name__}")
                logger.warning(
                    "cognitive_cycle_decision_degraded",
                    extra={"cycle_id": cycle_id, "question_ref": question_ref, "error_type": type(exc).__name__},
                )

        best = max(decisions, key=lambda item: (ACTION_RANK[item.action], item.priority), default=None)
        if best is None:
            return CognitiveCycleResult(
                cycle_id=cycle_id,
                status=CognitiveCycleStatus.degraded,
                situation_snapshot_ref=situation.snapshot_ref,
                activated_contributors=tuple(item.descriptor.contributor_id for item in activation.contributors),
                truncated_contributors=activation.truncated_contributor_ids,
                question_refs=tuple(question_refs),
                trace_refs=tuple(trace_refs),
                attention_action=AttentionAction.silent,
                attention_reason_code="decision_unavailable",
                eligible_prospective_thread_refs=tuple(ref.ref_id for ref in situation.eligible_prospective_threads),
                errors=tuple(errors),
            )

        item_ref: str | None = None
        state_refs: list[str] = []
        if best.action in SURFACEABLE_ACTIONS:
            deduplication_key = self._deduplication_key(event, best, requests)
            item, created = self.attention_items.enqueue(
                db,
                user,
                best,
                deduplication_key=deduplication_key,
                payload={"question_ref": best.question_ref, "cycle_id": cycle_id},
                metadata={
                    "attention_policy_version": self.attention_manager.policy_version,
                    "curiosity_policy_version": self.curiosity_policy.policy_version,
                },
            )
            item_ref = item.id
            if created:
                state_refs.append(f"attention_item:{item.id}")

        if best.source_trace_id:
            trace = db.get(CognitiveTrace, best.source_trace_id)
            if trace is not None:
                self.trace_service.add_audit(
                    db,
                    user,
                    trace=trace,
                    audit_type="attention_decision",
                    downstream_action_ref=item_ref,
                    outcome={"attention_action": best.action.value, "reason_code": best.reason_code},
                    metadata={
                        "cycle_id": cycle_id,
                        "attention_policy_version": self.attention_manager.policy_version,
                        "curiosity_policy_version": self.curiosity_policy.policy_version,
                    },
                )

        return CognitiveCycleResult(
            cycle_id=cycle_id,
            status=CognitiveCycleStatus.degraded if errors else CognitiveCycleStatus.completed,
            situation_snapshot_ref=situation.snapshot_ref,
            activated_contributors=tuple(item.descriptor.contributor_id for item in activation.contributors),
            truncated_contributors=activation.truncated_contributor_ids,
            question_refs=tuple(question_refs),
            trace_refs=tuple(trace_refs),
            attention_action=best.action,
            attention_reason_code=best.reason_code,
            attention_item_ref=item_ref,
            eligible_prospective_thread_refs=tuple(ref.ref_id for ref in situation.eligible_prospective_threads),
            state_mutation_refs=tuple(state_refs),
            errors=tuple(errors),
        )

    def _build_context(
        self,
        event: CognitiveEvent,
        request: DecisionQuestionRequest,
        situation: GlobalWorkspace,
    ):
        facts: dict[str, Any] = {
            "world_revision": situation.world_revision,
            "foreground_workspace_type": situation.foreground_workspace.label if situation.foreground_workspace else None,
            "pending_attention_count": len(situation.pending_attention),
            "eligible_prospective_thread_count": len(situation.eligible_prospective_threads),
            "broad_context": situation.broad_context.value,
        }
        provenance = {
            key: (ProvenanceReference(source_type="global_workspace", source_id=situation.snapshot_ref),)
            for key in facts
        }
        metadata: dict[str, Any] = {}
        if event.source == "test":
            for key in ("fake_scenario", "fake_selected_answer"):
                if key in event.metadata:
                    metadata[key] = event.metadata[key]
        return self.context_builder.build(
            event=event,
            question=request.question,
            facts=facts,
            provenance=provenance,
            metadata=metadata,
        )

    def _attention_decision(
        self,
        event: CognitiveEvent,
        request: DecisionQuestionRequest,
        selected_answer: object,
        confidence: float,
        trace_id: str | None,
        situation: GlobalWorkspace,
        now: datetime,
        user_policy: UserIntelligenceSettings | None,
    ) -> AttentionDecision:
        metadata = request.metadata
        action = AttentionAction(str(selected_answer))
        foreground_id = situation.foreground_workspace.ref_id if situation.foreground_workspace else None
        candidate = AttentionCandidate(
            requested_action=action,
            reason_code=str(metadata.get("reason_code") or "candidate_evaluated"),
            subject=str(metadata.get("subject") or event.event_type),
            priority=metadata.get("priority", 50),
            urgency=metadata.get("urgency", 0.3),
            evidence_quality=metadata.get("evidence_quality", 0.7),
            confidence=confidence,
            reversible=metadata.get("reversible", True),
            requires_canonical_mutation=metadata.get("requires_canonical_mutation", False),
            supported_in_version=metadata.get("supported_in_version", True),
            active_task_interruption_cost=metadata.get("active_task_interruption_cost", 0.2),
            host_authorized_actions=tuple(metadata.get("host_authorized_actions") or ()),
            not_before=metadata.get("not_before"),
            expires_at=metadata.get("expires_at"),
            source_event_id=event.event_id,
            source_trace_id=trace_id,
            workspace_id=foreground_id,
            open_thread_id=metadata.get("open_thread_id"),
            prospective_thread_id=metadata.get("prospective_thread_id"),
            question_ref=f"{request.question.question_id}:v{request.question.question_version}",
        )
        decision = self.attention_manager.decide(
            candidate,
            proactivity_mode=user_policy.proactivity_mode if user_policy else "BALANCED",
            passive_suggestions_enabled=user_policy.passive_suggestions_enabled if user_policy else True,
            questions_enabled=user_policy.questions_enabled if user_policy else True,
            interruptions_enabled=user_policy.interruptions_enabled if user_policy else True,
        )
        if decision.action != AttentionAction.ask:
            return decision

        curiosity_payload = metadata.get("curiosity") or {
            "importance": 0.8,
            "uncertainty": 0.8,
            "decision_impact": 0.8,
            "naturalness": 0.8,
            "interruption_cost": 0.1,
            "annoyance": 0.1,
            "inferability_elsewhere": 0.1,
        }
        curiosity = self.curiosity_policy.evaluate(CuriosityInputs.model_validate(curiosity_payload))
        if curiosity.action == CuriosityAction.skip:
            return decision.model_copy(update={"action": AttentionAction.silent, "reason_code": curiosity.reason_code})
        if curiosity.action == CuriosityAction.defer:
            return decision.model_copy(
                update={"not_before": decision.not_before or now + timedelta(minutes=30), "reason_code": curiosity.reason_code}
            )
        return decision

    @staticmethod
    def _deduplication_key(
        event: CognitiveEvent,
        decision: AttentionDecision,
        requests: list[tuple[str, str, DecisionQuestionRequest]],
    ) -> str:
        explicit = next((request.metadata.get("deduplication_key") for _, _, request in requests if request.metadata.get("deduplication_key")), None)
        if explicit:
            return str(explicit)[:180]
        if decision.prospective_thread_id:
            return f"prospective:{decision.prospective_thread_id}:{decision.action.value}"[:180]
        identity = event.source_event_id or event.event_id
        return f"cognitive:{identity}:{decision.reason_code}:{decision.action.value}"[:180]

    @staticmethod
    def _silent_result(
        cycle_id: str,
        status: CognitiveCycleStatus,
        reason: str,
        *,
        errors: tuple[str, ...] = (),
    ) -> CognitiveCycleResult:
        return CognitiveCycleResult(
            cycle_id=cycle_id,
            status=status,
            attention_action=AttentionAction.silent,
            attention_reason_code=reason,
            errors=errors,
        )
