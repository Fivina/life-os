from __future__ import annotations

from app.attention.schemas import AttentionAction, AttentionCandidate, AttentionDecision
from app.core.logging import get_logger


logger = get_logger(__name__)
SENSITIVE_ACTIONS = {
    AttentionAction.act_silently,
    AttentionAction.propose,
    AttentionAction.interrupt,
}


class AttentionManager:
    """Deterministic host policy. It chooses an intent and performs no side effect."""

    policy_version = "attention-policy-v1"
    minimum_evidence = 0.35
    minimum_confidence = 0.30

    def decide(
        self,
        candidate: AttentionCandidate,
        *,
        proactivity_mode: str = "BALANCED",
        passive_suggestions_enabled: bool = True,
        questions_enabled: bool = True,
        interruptions_enabled: bool = True,
    ) -> AttentionDecision:
        action = candidate.requested_action
        reason = candidate.reason_code
        if not candidate.supported_in_version:
            action, reason = AttentionAction.silent, "unsupported_action"
        elif candidate.requires_canonical_mutation:
            action, reason = AttentionAction.silent, "canonical_authority_required"
        elif candidate.evidence_quality < self.minimum_evidence or candidate.confidence < self.minimum_confidence:
            action, reason = AttentionAction.silent, "insufficient_evidence"
        elif action in SENSITIVE_ACTIONS and action not in candidate.host_authorized_actions:
            action, reason = self._safe_downgrade(action), "host_authorization_missing"
        elif action == AttentionAction.interrupt and (
            candidate.priority < 90
            or candidate.urgency < 0.85
            or candidate.evidence_quality < 0.80
            or candidate.active_task_interruption_cost > 0.50
        ):
            action, reason = AttentionAction.mention_when_natural, "interrupt_threshold_not_met"
        if action == AttentionAction.interrupt and not interruptions_enabled:
            action, reason = AttentionAction.mention_when_natural, "interruptions_disabled"
        if action == AttentionAction.ask and not questions_enabled:
            action, reason = AttentionAction.silent, "questions_disabled"
        if action == AttentionAction.show_passively and not passive_suggestions_enabled:
            action, reason = AttentionAction.silent, "passive_suggestions_disabled"
        if proactivity_mode == "QUIET" and action in {
            AttentionAction.mention_when_natural,
            AttentionAction.propose,
            AttentionAction.ask,
        } and candidate.urgency < 0.85:
            action, reason = AttentionAction.silent, "quiet_mode_nonurgent"

        decision = AttentionDecision(
            action=action,
            reason_code=reason,
            subject=candidate.subject,
            priority=candidate.priority,
            urgency=candidate.urgency,
            confidence=candidate.confidence,
            evidence_quality=candidate.evidence_quality,
            not_before=candidate.not_before,
            expires_at=candidate.expires_at,
            source_event_id=candidate.source_event_id,
            source_trace_id=candidate.source_trace_id,
            workspace_id=candidate.workspace_id,
            open_thread_id=candidate.open_thread_id,
            prospective_thread_id=candidate.prospective_thread_id,
            question_ref=candidate.question_ref,
            policy_version=self.policy_version,
            metadata={"requested_action": candidate.requested_action.value, "proactivity_mode": proactivity_mode},
        )
        logger.info(
            "attention_decided",
            extra={"action": action.value, "reason_code": reason, "priority": candidate.priority},
        )
        return decision

    @staticmethod
    def _safe_downgrade(action: AttentionAction) -> AttentionAction:
        if action == AttentionAction.interrupt:
            return AttentionAction.mention_when_natural
        if action == AttentionAction.propose:
            return AttentionAction.show_passively
        return AttentionAction.silent
