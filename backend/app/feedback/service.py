from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import (
    ActiveWorkspace,
    CognitiveTrace,
    ConversationThread,
    DecisionAudit,
    DecisionTrainingExample,
    FeedbackResponse,
    FeedbackSession,
    UserProfile,
)
from app.decision.traces import DecisionTraceService
from app.feedback.command import match_log_feedback
from app.feedback.questions import FeedbackQuestionSelector
from app.feedback.schemas import (
    FeedbackClarification,
    FeedbackResponseInput,
    FeedbackScope,
    FeedbackSessionState,
    FeedbackSessionStatus,
    FeedbackQuestion,
)
from app.feedback.targeting import FeedbackTarget, FeedbackTraceSelector
from app.feedback.training import DecisionTrainingExampleBuilder
from app.workspaces.schemas import WorkspaceStatus
from app.workspaces.service import ActiveWorkspaceService


logger = get_logger(__name__)
OPEN_WORKSPACE_STATUSES = {WorkspaceStatus.active.value, WorkspaceStatus.paused.value}


def utcnow() -> datetime:
    return datetime.now(UTC)


class FeedbackService:
    def __init__(
        self,
        settings: Settings,
        *,
        target_selector: FeedbackTraceSelector | None = None,
        question_selector: FeedbackQuestionSelector | None = None,
        training_builder: DecisionTrainingExampleBuilder | None = None,
        trace_service: DecisionTraceService | None = None,
    ):
        self.settings = settings
        self.target_selector = target_selector or FeedbackTraceSelector()
        self.question_selector = question_selector or FeedbackQuestionSelector(
            max_questions=settings.feedback_max_questions
        )
        self.training_builder = training_builder or DecisionTrainingExampleBuilder()
        self.trace_service = trace_service or DecisionTraceService()
        self.workspaces = ActiveWorkspaceService()

    def start_from_command(
        self,
        db: Session,
        user: UserProfile,
        *,
        command: str,
        parent_conversation_id: str | None,
        attention_item_id: str | None = None,
        now: datetime | None = None,
    ) -> FeedbackSessionState:
        parsed = match_log_feedback(command)
        if not parsed.matched:
            return FeedbackSessionState(result_code="NOT_FEEDBACK_COMMAND")
        if not self.settings.intelligence_feedback_enabled:
            return FeedbackSessionState(result_code="FEEDBACK_DISABLED")
        when = now or utcnow()
        conversation = self._conversation(db, user, parent_conversation_id)
        existing = self.get_active(db, user, conversation_id=parent_conversation_id)
        if existing is not None:
            return self.state(db, user, existing, result_code="ACTIVE_SESSION_EXISTS")

        foreground = self.workspaces.get_foreground_workspace(db, user)
        target = self.target_selector.select_target(
            db,
            user,
            conversation_id=parent_conversation_id,
            foreground_workspace=foreground,
            attention_item_id=attention_item_id,
        )
        if target is None:
            return FeedbackSessionState(result_code="NO_TARGET_TRACE")

        plan = self.question_selector.select(
            target.trace,
            inline_explanation=parsed.inline_explanation,
        )
        frozen = self._freeze(target)
        resume_state = {
            "parent_conversation": (
                {
                    "id": conversation.id,
                    "status": conversation.status,
                    "last_message_at": conversation.last_message_at.isoformat(),
                }
                if conversation else None
            ),
            "parent_workspace": (
                {
                    "id": foreground.id,
                    "workspace_type": foreground.workspace_type,
                    "status": foreground.status,
                    "is_foreground": foreground.is_foreground,
                    "state_revision": foreground.state_revision,
                }
                if foreground else None
            ),
        }
        questions_json = [question.model_dump(mode="json") for question in plan.questions]
        permanent_rule = self._is_permanent_rule(parsed.inline_explanation)
        session = FeedbackSession(
            user_id=user.id,
            status=FeedbackSessionStatus.active.value,
            started_at=when,
            parent_conversation_id=conversation.id if conversation else None,
            parent_workspace_id=foreground.id if foreground else None,
            parent_workspace_type=foreground.workspace_type if foreground else None,
            target_cognitive_trace_id=target.trace.id,
            target_decision_audit_id=target.decision_audit.id if target.decision_audit else None,
            target_assistant_message_id=target.assistant_message.id if target.assistant_message else None,
            frozen_world_revision=target.trace.world_revision if target.trace.world_revision is not None else user.world_revision,
            frozen_context_json=frozen,
            initial_user_explanation=parsed.inline_explanation,
            current_question_index=0,
            questions_planned_count=len(plan.questions),
            questions_answered_count=0,
            clarification_used=False,
            clarification_question_json=plan.clarification.model_dump(mode="json") if plan.clarification else {},
            planned_questions_json=questions_json,
            resume_state_json=resume_state,
            metadata_json={
                "selector_version": self.question_selector.version,
                "explicit_policy_handoff": (
                    {"scope": FeedbackScope.permanent_explicit_rule.value, "statement": parsed.inline_explanation}
                    if permanent_rule else None
                ),
            },
        )
        db.add(session)
        db.flush()
        logger.info(
            "feedback_session_started",
            extra={
                "user_id": user.id,
                "feedback_session_id": session.id,
                "target_trace_id": target.trace.id,
                "question_count": len(plan.questions),
            },
        )
        return self.state(db, user, session, result_code="STARTED")

    def get(self, db: Session, user: UserProfile, session_id: str, *, lock: bool = False) -> FeedbackSession:
        statement = select(FeedbackSession).where(
            FeedbackSession.id == session_id,
            FeedbackSession.user_id == user.id,
        )
        if lock:
            statement = statement.with_for_update()
        session = db.scalar(statement)
        if session is None:
            raise LookupError("Feedback session not found.")
        return session

    def get_active(
        self,
        db: Session,
        user: UserProfile,
        *,
        conversation_id: str | None = None,
    ) -> FeedbackSession | None:
        statement = select(FeedbackSession).where(
            FeedbackSession.user_id == user.id,
            FeedbackSession.status == FeedbackSessionStatus.active.value,
        )
        if conversation_id is not None:
            statement = statement.where(FeedbackSession.parent_conversation_id == conversation_id)
        return db.scalar(statement.order_by(FeedbackSession.created_at.desc()).limit(1))

    def submit_clarification(
        self,
        db: Session,
        user: UserProfile,
        session_id: str,
        *,
        answer: str,
    ) -> FeedbackSessionState:
        session = self.get(db, user, session_id, lock=True)
        self._require_active(session)
        if not session.clarification_question_json:
            raise ValueError("This feedback session does not require clarification.")
        if session.clarification_used:
            return self.state(db, user, session, result_code="CLARIFICATION_ALREADY_RECORDED")
        session.clarification_used = True
        session.clarification_answer = answer
        session.version += 1
        logger.info("feedback_clarification_recorded", extra={"user_id": user.id, "feedback_session_id": session.id})
        return self.state(db, user, session, result_code="CLARIFICATION_RECORDED")

    def submit_response(
        self,
        db: Session,
        user: UserProfile,
        session_id: str,
        payload: FeedbackResponseInput,
    ) -> FeedbackSessionState:
        session = self.get(db, user, session_id, lock=True)
        self._require_active(session)
        if session.clarification_question_json and not session.clarification_used:
            raise ValueError("Answer the single clarification before scored feedback.")
        question = self._planned_question(session, payload.question_id, payload.question_version)
        existing = db.scalar(
            select(FeedbackResponse).where(
                FeedbackResponse.feedback_session_id == session.id,
                FeedbackResponse.question_id == payload.question_id,
                FeedbackResponse.question_version == payload.question_version,
            )
        )
        if existing is not None:
            return self.state(db, user, session, result_code="RESPONSE_ALREADY_RECORDED")

        scope = self._validated_scope(
            payload.feedback_scope,
            session.initial_user_explanation,
            payload.explanation,
            payload.explicit_scope_statement,
        )
        response = FeedbackResponse(
            user_id=user.id,
            feedback_session_id=session.id,
            question_id=question.question_id,
            question_version=question.question_version,
            dimension=question.dimension.value,
            score=payload.score,
            is_skipped=payload.is_skipped,
            feedback_scope=scope.value,
            feedback_confidence=payload.feedback_confidence.value,
            explanation=payload.explanation,
        )
        db.add(response)
        db.flush()
        session.questions_answered_count += 1
        session.current_question_index = self._next_question_index(db, session)
        session.version += 1
        if scope == FeedbackScope.permanent_explicit_rule:
            metadata = dict(session.metadata_json)
            metadata["explicit_policy_handoff"] = {
                "scope": scope.value,
                "statement": payload.explicit_scope_statement or payload.explanation or session.initial_user_explanation,
                "response_id": response.id,
            }
            session.metadata_json = metadata
        logger.info(
            "feedback_response_recorded",
            extra={
                "user_id": user.id,
                "feedback_session_id": session.id,
                "dimension": response.dimension,
                "skipped": response.is_skipped,
            },
        )
        return self.state(db, user, session, result_code="RESPONSE_RECORDED")

    def complete(
        self,
        db: Session,
        user: UserProfile,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> FeedbackSessionState:
        session = self.get(db, user, session_id, lock=True)
        if session.status == FeedbackSessionStatus.completed.value:
            return self.state(db, user, session, result_code="ALREADY_COMPLETED")
        self._require_active(session)
        responses = list(db.scalars(
            select(FeedbackResponse)
            .where(FeedbackResponse.feedback_session_id == session.id, FeedbackResponse.user_id == user.id)
            .order_by(FeedbackResponse.created_at.asc())
        ))
        if not responses:
            raise ValueError("At least one feedback response is required before completion.")
        trace = db.scalar(select(CognitiveTrace).where(CognitiveTrace.id == session.target_cognitive_trace_id, CognitiveTrace.user_id == user.id))
        if trace is None:
            raise LookupError("The feedback target trace is unavailable.")

        evidence = [
            {
                "response_id": response.id,
                "dimension": response.dimension,
                "score": response.score,
                "skipped": response.is_skipped,
                "scope": response.feedback_scope,
                "confidence": response.feedback_confidence,
            }
            for response in responses
        ]
        audit = self.trace_service.add_audit(
            db,
            user,
            trace=trace,
            audit_type="explicit_log_feedback",
            outcome={"feedback_session_id": session.id, "dimensions": evidence},
            correction={
                "low_score_dimensions": [
                    response.dimension for response in responses
                    if response.score is not None and response.score <= 2
                ]
            },
            downstream_action_ref=None,
            feedback_ref=session.id,
            training_eligible=any(not response.is_skipped for response in responses),
            metadata={"selector_version": session.metadata_json.get("selector_version")},
        )
        examples: list[DecisionTrainingExample] = []
        for response in responses:
            example = self.training_builder.build(
                db,
                user,
                session=session,
                response=response,
                audit=audit,
            )
            if example is not None:
                examples.append(example)

        when = now or utcnow()
        session.status = FeedbackSessionStatus.completed.value
        session.completed_at = when
        session.current_question_index = session.questions_planned_count
        session.feedback_summary_json = {
            "responses": evidence,
            "decision_audit_id": audit.id,
            "training_example_ids": [example.id for example in examples],
            "multi_dimension_preserved": True,
        }
        session.resume_state_json = self._resume_state(db, user, session)
        session.version += 1
        logger.info(
            "feedback_session_completed",
            extra={
                "user_id": user.id,
                "feedback_session_id": session.id,
                "response_count": len(responses),
                "training_example_count": len(examples),
            },
        )
        return self.state(db, user, session, result_code="COMPLETED")

    def cancel(
        self,
        db: Session,
        user: UserProfile,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> FeedbackSessionState:
        session = self.get(db, user, session_id, lock=True)
        if session.status == FeedbackSessionStatus.cancelled.value:
            return self.state(db, user, session, result_code="ALREADY_CANCELLED")
        self._require_active(session)
        session.status = FeedbackSessionStatus.cancelled.value
        session.cancelled_at = now or utcnow()
        session.resume_state_json = self._resume_state(db, user, session)
        session.version += 1
        logger.info("feedback_session_cancelled", extra={"user_id": user.id, "feedback_session_id": session.id})
        return self.state(db, user, session, result_code="CANCELLED")

    def state(
        self,
        db: Session,
        user: UserProfile,
        session: FeedbackSession,
        *,
        result_code: str = "OK",
    ) -> FeedbackSessionState:
        clarification = None
        if session.clarification_question_json and not session.clarification_used and session.status == FeedbackSessionStatus.active.value:
            clarification = FeedbackClarification.model_validate(session.clarification_question_json)
        next_question = None if clarification else self.next_question(db, user, session)
        return FeedbackSessionState(
            result_code=result_code,
            session_id=session.id,
            status=FeedbackSessionStatus(session.status),
            parent_conversation_id=session.parent_conversation_id,
            parent_workspace_id=session.parent_workspace_id,
            target_cognitive_trace_id=session.target_cognitive_trace_id,
            current_question_index=session.current_question_index,
            questions_planned_count=session.questions_planned_count,
            questions_answered_count=session.questions_answered_count,
            clarification=clarification,
            next_question=next_question,
            resume_state=session.resume_state_json,
        )

    def next_question(
        self,
        db: Session,
        user: UserProfile,
        session: FeedbackSession,
    ) -> FeedbackQuestion | None:
        if session.user_id != user.id or session.status != FeedbackSessionStatus.active.value:
            return None
        answered = set(db.execute(
            select(FeedbackResponse.question_id, FeedbackResponse.question_version).where(
                FeedbackResponse.feedback_session_id == session.id,
                FeedbackResponse.user_id == user.id,
            )
        ).all())
        for raw in session.planned_questions_json:
            question = FeedbackQuestion.model_validate(raw)
            if (question.question_id, question.question_version) not in answered:
                return question
        return None

    @staticmethod
    def _conversation(
        db: Session,
        user: UserProfile,
        conversation_id: str | None,
    ) -> ConversationThread | None:
        if conversation_id is None:
            return None
        conversation = db.scalar(select(ConversationThread).where(
            ConversationThread.id == conversation_id,
            ConversationThread.user_id == user.id,
        ))
        if conversation is None:
            raise LookupError("Conversation not found.")
        return conversation

    @staticmethod
    def _freeze(target: FeedbackTarget) -> dict[str, Any]:
        trace = target.trace
        workspace = target.workspace
        attention = target.attention_item
        return {
            "freeze_version": 1,
            "trace": {
                "id": trace.id,
                "cognitive_event_id": trace.cognitive_event_id,
                "event_type": trace.event_type,
                "event_source": trace.event_source,
                "source_event_id": trace.source_event_id,
                "conversation_thread_id": trace.conversation_thread_id,
                "workspace_ref": trace.workspace_ref,
                "world_revision": trace.world_revision,
                "question_id": trace.question_id,
                "question_version": trace.question_version,
                "question_family": trace.question_family,
                "provider": trace.provider,
                "provider_version": trace.provider_version,
                "model_version": trace.model_version,
                "policy_version": trace.policy_version,
                "selected_answer": (trace.output_json or {}).get("selected_answer"),
                "confidence": trace.confidence,
                "probabilities": trace.probabilities_json,
                "context": trace.context_json,
                "context_refs": trace.context_refs_json,
                "memory_refs": trace.memory_refs_json,
                "pattern_refs": trace.pattern_refs_json,
                "state_change_refs": trace.state_change_refs_json,
                "metadata": trace.metadata_json,
            },
            "workspace": (
                {
                    "id": workspace.id,
                    "workspace_type": workspace.workspace_type,
                    "status": workspace.status,
                    "is_foreground": workspace.is_foreground,
                    "payload_version": workspace.payload_version,
                    "payload": workspace.payload_json,
                    "current_phase": workspace.current_phase,
                    "current_step": workspace.current_step,
                    "state_revision": workspace.state_revision,
                    "canonical_change_refs": workspace.canonical_change_refs_json,
                }
                if workspace else None
            ),
            "attention_item": (
                {
                    "id": attention.id,
                    "action": attention.action,
                    "reason_code": attention.reason_code,
                    "priority": attention.priority,
                    "workspace_id": attention.workspace_id,
                    "open_thread_id": attention.open_thread_id,
                    "prospective_thread_id": attention.prospective_thread_id,
                }
                if attention else None
            ),
            "candidate": {
                "action": (attention.action if attention else (trace.output_json or {}).get("selected_answer")),
                "urgency": None,
                "reversible": None,
            },
            "target_decision_audit_id": target.decision_audit.id if target.decision_audit else None,
            "target_assistant_message_id": target.assistant_message.id if target.assistant_message else None,
        }

    @staticmethod
    def _require_active(session: FeedbackSession) -> None:
        if session.status != FeedbackSessionStatus.active.value:
            raise ValueError("Feedback session is not active.")

    @staticmethod
    def _planned_question(session: FeedbackSession, question_id: str, version: int) -> FeedbackQuestion:
        for raw in session.planned_questions_json:
            question = FeedbackQuestion.model_validate(raw)
            if (question.question_id, question.question_version) == (question_id, version):
                return question
        raise ValueError("Question is not part of this feedback session.")

    @staticmethod
    def _next_question_index(db: Session, session: FeedbackSession) -> int:
        count = db.scalar(select(func.count(FeedbackResponse.id)).where(FeedbackResponse.feedback_session_id == session.id))
        return min(int(count or 0), session.questions_planned_count)

    @classmethod
    def _validated_scope(
        cls,
        requested: FeedbackScope,
        *evidence: str | None,
    ) -> FeedbackScope:
        combined = " ".join(item for item in evidence if item).lower()
        if requested == FeedbackScope.permanent_explicit_rule:
            return requested if cls._is_permanent_rule(combined) else FeedbackScope.exact_case
        if requested == FeedbackScope.general_preference:
            has_generalization = bool(re.search(r"\b(always|never|generally|usually|in general|i prefer)\b", combined))
            return requested if has_generalization else FeedbackScope.exact_case
        return requested

    @staticmethod
    def _is_permanent_rule(value: str | None) -> bool:
        if not value:
            return False
        lowered = value.lower()
        return bool(re.search(r"\b(never|always)\b", lowered)) and bool(
            re.search(r"\b(me|my|i)\b", lowered)
        )

    @staticmethod
    def _resume_state(db: Session, user: UserProfile, session: FeedbackSession) -> dict[str, Any]:
        original = session.resume_state_json
        conversation = db.scalar(select(ConversationThread).where(
            ConversationThread.id == session.parent_conversation_id,
            ConversationThread.user_id == user.id,
        )) if session.parent_conversation_id else None
        workspace = db.scalar(select(ActiveWorkspace).where(
            ActiveWorkspace.id == session.parent_workspace_id,
            ActiveWorkspace.user_id == user.id,
        )) if session.parent_workspace_id else None
        original_workspace = original.get("parent_workspace") or {}
        return {
            **original,
            "resume_result": {
                "conversation_id": conversation.id if conversation else None,
                "same_conversation": bool(conversation and conversation.id == session.parent_conversation_id),
                "workspace_id": workspace.id if workspace else None,
                "same_workspace": bool(workspace and workspace.id == session.parent_workspace_id),
                "workspace_still_open": bool(workspace and workspace.status in OPEN_WORKSPACE_STATUSES),
                "workspace_still_foreground": bool(workspace and workspace.is_foreground),
                "external_workspace_change": bool(
                    workspace and original_workspace and workspace.state_revision != original_workspace.get("state_revision")
                ),
            },
        }
