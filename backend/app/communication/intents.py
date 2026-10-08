from __future__ import annotations

from app.attention.schemas import AttentionAction, AttentionDecision
from app.cognition.schemas import CognitiveCycleResult
from app.communication.schemas import (
    CommunicativeIntent,
    ResponseTone,
    SpeechAct,
    StructuredClaim,
    StructuredFact,
)


SPEECH_ACT_BY_ATTENTION: dict[AttentionAction, SpeechAct] = {
    AttentionAction.silent: SpeechAct.status,
    AttentionAction.act_silently: SpeechAct.confirm,
    AttentionAction.show_passively: SpeechAct.status,
    AttentionAction.mention_when_natural: SpeechAct.mention,
    AttentionAction.ask: SpeechAct.ask,
    AttentionAction.propose: SpeechAct.propose,
    AttentionAction.interrupt: SpeechAct.warn,
    AttentionAction.escalate_to_gemini: SpeechAct.degraded,
}


class CommunicativeIntentFactory:
    """Converts host-owned structured decisions into presentation-only intent."""

    def from_attention(
        self,
        decision: AttentionDecision,
        *,
        facts: tuple[StructuredFact, ...] = (),
        claims: tuple[StructuredClaim, ...] = (),
        current_state_refs: tuple[str, ...] = (),
        conversation_ref: str | None = None,
        plan_proposal_ref: str | None = None,
        question: str | None = None,
        recommended_next_action: str | None = None,
        fallback_template_key: str = "generic",
    ) -> CommunicativeIntent:
        return CommunicativeIntent(
            purpose=SPEECH_ACT_BY_ATTENTION[decision.action],
            attention_action=decision.action,
            reason_code=decision.reason_code,
            importance=decision.priority,
            urgency=decision.urgency,
            facts=facts,
            claims=claims,
            current_state_refs=current_state_refs,
            workspace_ref=decision.workspace_id,
            conversation_ref=conversation_ref,
            cognitive_trace_ref=decision.source_trace_id,
            plan_proposal_ref=plan_proposal_ref,
            user_response_required=decision.action == AttentionAction.ask,
            question=question,
            recommended_next_action=recommended_next_action,
            tone=ResponseTone.serious if decision.priority >= 85 else ResponseTone.warm,
            fallback_template_key=fallback_template_key,
            metadata={
                "attention_policy_version": decision.policy_version,
                "source_event_id": decision.source_event_id,
                "open_thread_id": decision.open_thread_id,
                "prospective_thread_id": decision.prospective_thread_id,
            },
        )

    def from_cycle(
        self,
        cycle: CognitiveCycleResult,
        *,
        subject: str,
        facts: tuple[StructuredFact, ...] = (),
        claims: tuple[StructuredClaim, ...] = (),
        workspace_ref: str | None = None,
        conversation_ref: str | None = None,
        question: str | None = None,
        fallback_template_key: str = "generic",
    ) -> CommunicativeIntent:
        trace_ref = cycle.trace_refs[-1] if cycle.trace_refs else None
        return CommunicativeIntent(
            purpose=SPEECH_ACT_BY_ATTENTION[cycle.attention_action],
            attention_action=cycle.attention_action,
            reason_code=cycle.attention_reason_code,
            facts=facts,
            claims=claims,
            current_state_refs=cycle.state_mutation_refs,
            workspace_ref=workspace_ref,
            conversation_ref=conversation_ref,
            cognitive_trace_ref=trace_ref,
            user_response_required=cycle.attention_action == AttentionAction.ask,
            question=question,
            fallback_template_key=fallback_template_key,
            metadata={
                "cycle_id": cycle.cycle_id,
                "cycle_status": cycle.status.value,
                "subject": subject,
                "situation_snapshot_ref": cycle.situation_snapshot_ref,
                "attention_item_ref": cycle.attention_item_ref,
            },
        )
