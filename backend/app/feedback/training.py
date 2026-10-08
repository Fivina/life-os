from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    DecisionAudit,
    DecisionDisagreement,
    DecisionTrainingExample,
    FeedbackResponse,
    FeedbackSession,
    UserProfile,
)
from app.feedback.schemas import FeedbackLabelSource, FeedbackLabelStrength


class DecisionTrainingExampleBuilder:
    version = "decision-training-example-v1"

    def build(
        self,
        db: Session,
        user: UserProfile,
        *,
        session: FeedbackSession,
        response: FeedbackResponse,
        audit: DecisionAudit,
    ) -> DecisionTrainingExample | None:
        if response.is_skipped or response.score is None:
            return None
        frozen = session.frozen_context_json
        trace = frozen["trace"]
        workspace = frozen.get("workspace") or {}
        candidate = frozen.get("candidate") or {}
        attention = frozen.get("attention_item") or {}
        strength = self._strength(response.feedback_confidence, response.feedback_scope)
        disagreement = db.scalar(
            select(DecisionDisagreement)
            .where(
                DecisionDisagreement.user_id == user.id,
                DecisionDisagreement.cognitive_trace_id == session.target_cognitive_trace_id,
            )
            .order_by(DecisionDisagreement.created_at.desc())
            .limit(1)
        )
        example = DecisionTrainingExample(
            user_id=user.id,
            cognitive_trace_id=session.target_cognitive_trace_id,
            decision_audit_id=audit.id,
            decision_disagreement_id=disagreement.id if disagreement else None,
            feedback_session_id=session.id,
            feedback_response_id=response.id,
            decision_family=trace["question_family"],
            question_id=trace["question_id"],
            question_version=trace["question_version"],
            cognitive_event_ref=trace["cognitive_event_id"],
            conversation_thread_id=session.parent_conversation_id,
            active_workspace_type=session.parent_workspace_type,
            workspace_phase=workspace.get("current_phase"),
            candidate_action=candidate.get("action") or trace.get("selected_answer"),
            urgency=candidate.get("urgency"),
            reversible=candidate.get("reversible"),
            context_json={
                "builder_version": self.version,
                "frozen_world_revision": session.frozen_world_revision,
                "trigger": {"event_type": trace["event_type"], "event_source": trace["event_source"]},
                "workspace": workspace,
                "context_refs": trace.get("context_refs", []),
                "memory_refs": trace.get("memory_refs", []),
                "pattern_refs": trace.get("pattern_refs", []),
                "attention_item_ref": attention.get("id"),
                "assistant_message_ref": session.target_assistant_message_id,
                "routing_policy": ((trace.get("metadata") or {}).get("provider_route") or {}).get("policy_version"),
            },
            model_answer_json={"value": trace.get("selected_answer")},
            model_confidence=trace.get("confidence"),
            probabilities_json=trace.get("probabilities") or {},
            executive_result=attention.get("action") or trace.get("selected_answer"),
            feedback_dimension=response.dimension,
            feedback_score=response.score,
            feedback_scope=response.feedback_scope,
            feedback_confidence=response.feedback_confidence,
            explicit_feedback_json={
                "response_id": response.id,
                "explanation": response.explanation,
                "initial_explanation": session.initial_user_explanation,
            },
            label_json={
                "dimension": response.dimension,
                "score": response.score,
                "scope": response.feedback_scope,
            },
            label_strength=strength.value,
            label_source=FeedbackLabelSource.explicit_log_feedback.value,
            provider=trace["provider"],
            model_version=trace.get("model_version"),
            policy_version=trace["policy_version"],
        )
        db.add(example)
        db.flush()
        return example

    @staticmethod
    def _strength(confidence: str, scope: str) -> FeedbackLabelStrength:
        if confidence == "HIGH":
            return FeedbackLabelStrength.strong
        if confidence == "LOW":
            return FeedbackLabelStrength.weak
        return FeedbackLabelStrength.medium
