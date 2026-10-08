from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import CognitiveTrace, DecisionAudit, DecisionDisagreement, DecisionProviderUsage, UserProfile
from app.decision.provider_schemas import DisagreementType, ProviderCallRecord, ProviderRole
from app.decision.schemas import CognitiveEvent, DecisionContext, DecisionResult


def _answer_json(value: Any) -> dict[str, Any]:
    return {"value": value}


class DecisionProviderEvidenceService:
    """Persists operational metadata without exposing provider authority to canonical domains."""

    def record_usage(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question_id: str,
        question_version: int,
        question_family: str,
        routing_policy_version: str,
        calls: list[ProviderCallRecord],
        trace: CognitiveTrace | None,
    ) -> list[DecisionProviderUsage]:
        rows: list[DecisionProviderUsage] = []
        for call in calls:
            row = DecisionProviderUsage(
                user_id=user.id,
                cognitive_trace_id=trace.id if trace else None,
                cognitive_event_id=event.event_id,
                question_id=question_id,
                question_version=question_version,
                question_family=question_family,
                question_count=int(call.metadata.get("question_count") or 1),
                provider=call.provider,
                model_version=call.model_version,
                provider_role=call.role.value,
                routing_policy_version=routing_policy_version,
                routing_reason=call.routing_reason,
                status=call.status.value,
                latency_ms=call.latency_ms,
                input_units=call.input_units,
                output_units=call.output_units,
                estimated_cost_eur=call.estimated_cost_eur,
                request_id=call.request_id,
                error_code=call.error_code,
                metadata_json=call.metadata,
            )
            db.add(row)
            rows.append(row)
        db.flush()
        return rows

    def record_disagreement(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question_id: str,
        question_version: int,
        question_family: str,
        context: DecisionContext,
        routing_policy_version: str,
        primary_provider: str,
        comparison_provider: str,
        comparison_role: ProviderRole,
        primary_result: DecisionResult | None,
        comparison_result: DecisionResult | None,
        operational_result: DecisionResult,
        trace: CognitiveTrace | None,
        primary_error_code: str | None = None,
        comparison_error_code: str | None = None,
    ) -> DecisionDisagreement:
        kind = self.classify(
            primary_result=primary_result,
            comparison_result=comparison_result,
            primary_error_code=primary_error_code,
            comparison_error_code=comparison_error_code,
        )
        row = DecisionDisagreement(
            user_id=user.id,
            cognitive_trace_id=trace.id if trace else None,
            cognitive_event_id=event.event_id,
            question_id=question_id,
            question_version=question_version,
            question_family=question_family,
            context_hash=hashlib.sha256(
                context.model_dump_json(exclude={"built_at"}).encode("utf-8")
            ).hexdigest(),
            decision_audit_id=None,
            comparison_role=comparison_role.value,
            disagreement_type=kind.value,
            primary_provider=primary_provider,
            primary_model_version=primary_result.model_version if primary_result else None,
            primary_answer_json=_answer_json(primary_result.selected_answer) if primary_result else {},
            primary_probabilities_json=primary_result.probabilities or {} if primary_result else {},
            primary_confidence=primary_result.confidence if primary_result else None,
            comparison_provider=comparison_provider,
            comparison_model_version=comparison_result.model_version if comparison_result else None,
            comparison_answer_json=_answer_json(comparison_result.selected_answer) if comparison_result else {},
            comparison_probabilities_json=comparison_result.probabilities or {} if comparison_result else {},
            comparison_confidence=comparison_result.confidence if comparison_result else None,
            operational_provider=operational_result.provider,
            operational_answer_json=_answer_json(operational_result.selected_answer),
            routing_policy_version=routing_policy_version,
            training_eligible=False,
            review_status="UNREVIEWED",
            metadata_json={
                "primary_error_code": primary_error_code,
                "comparison_error_code": comparison_error_code,
                "shadow_had_no_operational_authority": comparison_role == ProviderRole.shadow,
            },
        )
        db.add(row)
        db.flush()
        return row

    def shadow_cost_today_eur(self, db: Session, user: UserProfile) -> float:
        return self.provider_cost_today_eur(db, user, role=ProviderRole.shadow)

    def provider_cost_today_eur(
        self,
        db: Session,
        user: UserProfile,
        *,
        provider: str | None = None,
        role: ProviderRole | None = None,
    ) -> float:
        today = datetime.now(UTC).date()
        query = select(func.coalesce(func.sum(DecisionProviderUsage.estimated_cost_eur), 0.0)).where(
            DecisionProviderUsage.user_id == user.id,
            func.date(DecisionProviderUsage.created_at) == today,
        )
        if provider:
            query = query.where(DecisionProviderUsage.provider == provider)
        if role:
            query = query.where(DecisionProviderUsage.provider_role == role.value)
        value = db.scalar(query)
        return float(value or 0.0)

    def link_audit(
        self,
        db: Session,
        user: UserProfile,
        *,
        disagreement_id: str,
        audit: DecisionAudit,
    ) -> DecisionDisagreement:
        row = db.scalar(select(DecisionDisagreement).where(
            DecisionDisagreement.id == disagreement_id,
            DecisionDisagreement.user_id == user.id,
        ))
        if row is None:
            raise LookupError("Decision disagreement not found.")
        if audit.user_id != user.id or audit.trace_id != row.cognitive_trace_id:
            raise ValueError("Decision audit does not belong to the disagreement trace.")
        row.decision_audit_id = audit.id
        row.review_status = "EVIDENCE_LINKED"
        db.flush()
        return row

    @staticmethod
    def classify(
        *,
        primary_result: DecisionResult | None,
        comparison_result: DecisionResult | None,
        primary_error_code: str | None = None,
        comparison_error_code: str | None = None,
    ) -> DisagreementType:
        if primary_error_code or comparison_error_code or primary_result is None or comparison_result is None:
            return DisagreementType.provider_error
        primary_confidence = primary_result.confidence or 0.0
        comparison_confidence = comparison_result.confidence or 0.0
        if primary_result.selected_answer == comparison_result.selected_answer:
            if abs(primary_confidence - comparison_confidence) >= 0.25:
                return DisagreementType.confidence_gap
            return DisagreementType.same_answer
        if primary_confidence < 0.6 <= comparison_confidence:
            return DisagreementType.primary_uncertain_secondary_confident
        if primary_confidence >= 0.75 > comparison_confidence:
            return DisagreementType.primary_confident_secondary_uncertain
        return DisagreementType.different_answer
