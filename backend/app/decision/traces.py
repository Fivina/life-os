from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import CognitiveTrace, DecisionAudit, UserProfile
from app.decision.schemas import CognitiveEvent, DecisionContext, DecisionQuestion, DecisionResult


def utcnow() -> datetime:
    return datetime.now(UTC)


class DecisionTraceService:
    def record_quick_capture(
        self,
        db: Session,
        user: UserProfile,
        *,
        capture_id: str,
        conversation_thread_id: str | None,
        workspace_ref: str | None,
        interpretation: dict[str, Any],
        policy_outcome: str,
        review_item_id: str | None = None,
        canonical_ref: str | None = None,
    ) -> CognitiveTrace:
        """Persist the explicit capture path without private model reasoning."""
        when = utcnow()
        state_refs = [ref for ref in (review_item_id and f"review_item:{review_item_id}", canonical_ref) if ref]
        trace = CognitiveTrace(
            user_id=user.id, cognitive_event_id=capture_id, event_type="quick_capture.interpreted",
            event_source="quick_capture", conversation_thread_id=conversation_thread_id,
            workspace_ref=workspace_ref, world_revision=user.world_revision, correlation_id=capture_id,
            question_id="quick_capture.interpret", question_version=1, question_family="capture",
            output_type="JSON", status="completed", provider=interpretation.get("interpreter_provider", "deterministic"),
            provider_version="1", model_version=interpretation.get("interpreter_model"),
            policy_version="quick-capture-policy-v1", skill_name="quick-capture", skill_version="1.9.1",
            started_at=when, completed_at=when, latency_ms=0,
            context_json={"entity_candidates": interpretation.get("entity_candidates", [])},
            context_refs_json=[], memory_refs_json=[], pattern_refs_json=[],
            input_json={"capture_ref": capture_id},
            output_json={
                "domain": interpretation.get("interpreted_domain"),
                "intent_type": interpretation.get("intent_type"),
                "target_entity_type": interpretation.get("target_entity_type"),
                "target_entity_id": interpretation.get("target_entity_id"),
                "confidence": interpretation.get("confidence"),
                "ambiguity_flags": interpretation.get("ambiguity_flags", []),
                "policy_outcome": policy_outcome,
            },
            probabilities_json={}, confidence=interpretation.get("confidence", 0),
            tool_call_refs_json=[], state_change_refs_json=state_refs,
            metadata_json={"review_item_id": review_item_id, "hidden_reasoning_stored": False},
        )
        db.add(trace)
        db.flush()
        return trace

    def record_orchestration(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        conversation_thread_id: str,
        workspace_ref: str | None,
        route: str,
        context_sections: tuple[str, ...],
        tool_name: str | None,
        entity_refs: tuple[dict, ...],
        state_change_refs: tuple[str, ...],
        response_text: str,
    ) -> CognitiveTrace:
        """Record an explicit orchestration path without model reasoning or hidden chain-of-thought."""
        when = utcnow()
        trace = CognitiveTrace(
            user_id=user.id, cognitive_event_id=request_id, event_type="self_core.request",
            event_source="self_core", conversation_thread_id=conversation_thread_id,
            workspace_ref=workspace_ref, world_revision=user.world_revision, correlation_id=request_id,
            question_id="self_core.route", question_version=1, question_family="orchestration",
            output_type="JSON", status="completed", provider="host_policy", provider_version="1",
            model_version=None, policy_version="self-core-router-v1", skill_name="self-core",
            skill_version="1.9.0", started_at=when, completed_at=when, latency_ms=0,
            context_json={"included_sections": list(context_sections), "route": route},
            context_refs_json=list(entity_refs), memory_refs_json=[], pattern_refs_json=[],
            input_json={"request_ref": request_id}, output_json={"route": route, "response": response_text[:500]},
            probabilities_json={}, confidence=1.0, tool_call_refs_json=[tool_name] if tool_name else [],
            state_change_refs_json=list(state_change_refs), metadata_json={"hidden_reasoning_stored": False},
        )
        db.add(trace)
        db.flush()
        return trace

    def get(self, db: Session, user: UserProfile, trace_id: str) -> CognitiveTrace | None:
        return db.scalar(select(CognitiveTrace).where(CognitiveTrace.id == trace_id, CognitiveTrace.user_id == user.id))

    def list_recent(self, db: Session, user: UserProfile, *, limit: int = 50) -> list[CognitiveTrace]:
        bounded_limit = max(1, min(limit, 100))
        return list(db.scalars(
            select(CognitiveTrace)
            .where(CognitiveTrace.user_id == user.id)
            .order_by(CognitiveTrace.created_at.desc())
            .limit(bounded_limit)
        ))

    def record_completed(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        context: DecisionContext,
        result: DecisionResult,
        started_at: datetime,
        skill_name: str | None = None,
        skill_version: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> CognitiveTrace:
        trace = CognitiveTrace(
            user_id=user.id,
            cognitive_event_id=event.event_id,
            event_type=event.event_type,
            event_source=event.source,
            source_event_id=event.source_event_id,
            conversation_thread_id=event.conversation_thread_id,
            workspace_ref=event.workspace_ref,
            world_revision=event.world_revision,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            question_id=question.question_id,
            question_version=question.question_version,
            question_family=question.family,
            output_type=question.output_type.value,
            status="completed",
            provider=result.provider,
            provider_version=result.provider_version,
            model_version=result.model_version,
            policy_version=result.host_policy_version,
            skill_name=skill_name,
            skill_version=skill_version,
            started_at=started_at,
            completed_at=utcnow(),
            latency_ms=result.latency_ms,
            estimated_cost_eur=None,
            context_json=context.model_dump(mode="json"),
            context_refs_json=[reference.model_dump(mode="json") for reference in context.entity_refs],
            memory_refs_json=list(context.memory_refs),
            pattern_refs_json=list(context.pattern_refs),
            input_json={
                "question_description": question.description,
                "event_input_ref": event.user_input_ref,
                "candidate_count": len(context.entity_refs),
            },
            output_json={"selected_answer": result.selected_answer, "metadata": result.metadata},
            probabilities_json=result.probabilities or {},
            confidence=result.confidence,
            tool_call_refs_json=[],
            state_change_refs_json=[],
            metadata_json={"workspace_snapshot_ref": event.workspace_snapshot_ref, **(trace_metadata or {})},
        )
        db.add(trace)
        db.flush()
        return trace

    def record_failed(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        context: DecisionContext,
        provider: str,
        provider_version: str | None,
        model_version: str | None,
        policy_version: str,
        started_at: datetime,
        latency_ms: int,
        error_code: str,
        error_message: str,
    ) -> CognitiveTrace:
        trace = CognitiveTrace(
            user_id=user.id,
            cognitive_event_id=event.event_id,
            event_type=event.event_type,
            event_source=event.source,
            source_event_id=event.source_event_id,
            conversation_thread_id=event.conversation_thread_id,
            workspace_ref=event.workspace_ref,
            world_revision=event.world_revision,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            question_id=question.question_id,
            question_version=question.question_version,
            question_family=question.family,
            output_type=question.output_type.value,
            status="failed",
            provider=provider,
            provider_version=provider_version,
            model_version=model_version,
            policy_version=policy_version,
            started_at=started_at,
            completed_at=utcnow(),
            latency_ms=latency_ms,
            context_json=context.model_dump(mode="json"),
            context_refs_json=[reference.model_dump(mode="json") for reference in context.entity_refs],
            memory_refs_json=list(context.memory_refs),
            pattern_refs_json=list(context.pattern_refs),
            input_json={"question_description": question.description},
            output_json={},
            probabilities_json={},
            tool_call_refs_json=[],
            state_change_refs_json=[],
            error_code=error_code,
            error_message=error_message[:2000],
            metadata_json={},
        )
        db.add(trace)
        db.flush()
        return trace

    def add_audit(
        self,
        db: Session,
        user: UserProfile,
        *,
        trace: CognitiveTrace,
        audit_type: str,
        outcome: dict[str, Any] | None = None,
        correction: dict[str, Any] | None = None,
        override: dict[str, Any] | None = None,
        downstream_action_ref: str | None = None,
        feedback_ref: str | None = None,
        training_eligible: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionAudit:
        audit = DecisionAudit(
            user_id=user.id,
            trace_id=trace.id,
            audit_type=audit_type,
            downstream_action_ref=downstream_action_ref,
            outcome_json=outcome or {},
            correction_json=correction or {},
            override_json=override or {},
            feedback_ref=feedback_ref,
            training_eligible=training_eligible,
            metadata_json=metadata or {},
        )
        db.add(audit)
        db.flush()
        return audit
