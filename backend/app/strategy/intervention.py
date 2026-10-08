from __future__ import annotations

from app.attention.manager import AttentionManager
from app.attention.schemas import AttentionAction, AttentionCandidate
from app.strategy.schemas import (
    AuthorityLevel,
    DataCompleteness,
    DeviationSeverity,
    InterventionDecision,
    Recoverability,
    StrategicDeviation,
    ExamTrajectorySnapshot,
)


class InterventionEngine:
    """Host-owned strategic authority policy. It never writes canonical plans."""

    def __init__(self, attention_manager: AttentionManager | None = None) -> None:
        self.attention_manager = attention_manager or AttentionManager()

    def decide(
        self,
        snapshot: ExamTrajectorySnapshot,
        deviation: StrategicDeviation | None,
        *,
        provider_judgment: str | None = None,
        source_trace_id: str | None = None,
    ) -> InterventionDecision:
        if deviation is None:
            return self._result(AuthorityLevel.observe, AttentionAction.silent, "trajectory_healthy", snapshot, None, provider_judgment, source_trace_id)
        if snapshot.completeness == DataCompleteness.insufficient or deviation.evidence_quality < 0.35:
            return self._result(AuthorityLevel.observe, AttentionAction.silent, "strategic_evidence_insufficient", snapshot, deviation, provider_judgment, source_trace_id)

        if deviation.severity == DeviationSeverity.low:
            level, requested, reason = AuthorityLevel.observe, AttentionAction.silent, "minor_recoverable_deviation"
        elif deviation.severity == DeviationSeverity.moderate:
            level = AuthorityLevel.prepare_proposal
            requested = AttentionAction.mention_when_natural
            reason = "recoverable_drift_requires_proposal"
        elif deviation.severity == DeviationSeverity.high:
            level = AuthorityLevel.prepare_proposal
            requested = AttentionAction.propose
            reason = "material_trajectory_shortfall"
        elif deviation.recoverability == Recoverability.unrecoverable and (deviation.days_remaining or 999) <= 2:
            level = AuthorityLevel.urgent_attention
            requested = AttentionAction.interrupt
            reason = "imminent_unrecoverable_shortfall"
        else:
            level = AuthorityLevel.ask_or_discuss_tradeoff
            requested = AttentionAction.ask
            reason = "critical_tradeoff_requires_user"

        return self._result(level, requested, reason, snapshot, deviation, provider_judgment, source_trace_id)

    def _result(
        self,
        level: AuthorityLevel,
        requested: AttentionAction,
        reason: str,
        snapshot: ExamTrajectorySnapshot,
        deviation: StrategicDeviation | None,
        provider_judgment: str | None,
        source_trace_id: str | None,
    ) -> InterventionDecision:
        severity = deviation.severity if deviation else DeviationSeverity.none
        priority = {DeviationSeverity.none: 10, DeviationSeverity.low: 30, DeviationSeverity.moderate: 62, DeviationSeverity.high: 84, DeviationSeverity.critical: 96}[severity]
        urgency = {DeviationSeverity.none: 0.0, DeviationSeverity.low: 0.15, DeviationSeverity.moderate: 0.45, DeviationSeverity.high: 0.75, DeviationSeverity.critical: 0.95}[severity]
        evidence = deviation.evidence_quality if deviation else snapshot.completeness_score
        authorized = (AttentionAction.propose, AttentionAction.interrupt) if level >= AuthorityLevel.prepare_proposal else ()
        attention = self.attention_manager.decide(AttentionCandidate(
            requested_action=requested,
            reason_code=reason,
            subject=f"Exam trajectory: {snapshot.exam_title}",
            priority=priority,
            urgency=urgency,
            evidence_quality=evidence,
            confidence=evidence,
            host_authorized_actions=authorized,
            source_trace_id=source_trace_id,
            payload={"exam_id": snapshot.exam_id, "authority_level": int(level)},
        ))
        return InterventionDecision(
            authority_level=level,
            attention_action=attention.action,
            reason_code=attention.reason_code,
            priority=priority,
            urgency=urgency,
            confidence=evidence,
            provider_judgment=provider_judgment,
            source_trace_id=source_trace_id,
        )
