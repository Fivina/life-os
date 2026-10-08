from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    ActiveWorkspace,
    AttentionItem,
    CognitiveTrace,
    ConversationMessage,
    DecisionAudit,
    UserProfile,
)


NON_TARGET_EVENT_SOURCES = {"benchmark", "housekeeping", "system_background", "worker"}
NON_TARGET_EVENT_TYPES = {"internal.noop", "benchmark.case", "housekeeping.completed"}


@dataclass(frozen=True)
class FeedbackTarget:
    trace: CognitiveTrace
    workspace: ActiveWorkspace | None
    attention_item: AttentionItem | None
    decision_audit: DecisionAudit | None
    assistant_message: ConversationMessage | None


class FeedbackTraceSelector:
    """Selects a meaningful trace inside explicit conversation/workspace scope."""

    def select_target(
        self,
        db: Session,
        user: UserProfile,
        *,
        conversation_id: str | None,
        foreground_workspace: ActiveWorkspace | None,
        attention_item_id: str | None = None,
    ) -> FeedbackTarget | None:
        explicit_attention = None
        if attention_item_id:
            explicit_attention = db.scalar(
                select(AttentionItem).where(
                    AttentionItem.id == attention_item_id,
                    AttentionItem.user_id == user.id,
                )
            )
            if explicit_attention is None:
                return None

        traces = list(db.scalars(
            select(CognitiveTrace)
            .where(CognitiveTrace.user_id == user.id, CognitiveTrace.status == "completed")
            .order_by(CognitiveTrace.completed_at.desc(), CognitiveTrace.created_at.desc())
            .limit(100)
        ))
        attention_by_trace = {
            item.source_trace_id: item
            for item in db.scalars(
                select(AttentionItem).where(
                    AttentionItem.user_id == user.id,
                    AttentionItem.source_trace_id.is_not(None),
                )
            )
        }

        scored: list[tuple[int, CognitiveTrace, AttentionItem | None]] = []
        for trace in traces:
            attention = attention_by_trace.get(trace.id)
            if not self._meaningful(trace, attention):
                continue
            exact_attention = explicit_attention is not None and explicit_attention.source_trace_id == trace.id
            conversation_match = bool(conversation_id and trace.conversation_thread_id == conversation_id)
            workspace_match = bool(foreground_workspace and (
                trace.workspace_ref == foreground_workspace.id
                or (attention and attention.workspace_id == foreground_workspace.id)
            ))
            if explicit_attention is not None and not exact_attention:
                continue
            if conversation_id or foreground_workspace:
                if not (exact_attention or conversation_match or workspace_match):
                    continue

            score = 0
            score += 120 if exact_attention else 0
            score += 90 if conversation_match else 0
            score += 70 if workspace_match else 0
            score += 25 if attention is not None else 0
            score += 20 if trace.question_family in {"attention", "memory", "planning"} else 0
            score += 15 if (trace.metadata_json or {}).get("cycle_id") else 0
            scored.append((score, trace, attention))

        if not scored:
            return None
        scored.sort(
            key=lambda item: (
                item[0],
                item[1].completed_at or item[1].created_at,
                item[1].created_at,
            ),
            reverse=True,
        )
        _, trace, attention = scored[0]
        audit = db.scalar(
            select(DecisionAudit)
            .where(DecisionAudit.user_id == user.id, DecisionAudit.trace_id == trace.id)
            .order_by(DecisionAudit.created_at.desc())
            .limit(1)
        )
        assistant_message = None
        if conversation_id:
            assistant_message = db.scalar(
                select(ConversationMessage)
                .where(
                    ConversationMessage.user_id == user.id,
                    ConversationMessage.thread_id == conversation_id,
                    ConversationMessage.role == "assistant",
                )
                .order_by(ConversationMessage.sequence_number.desc())
                .limit(1)
            )
        return FeedbackTarget(
            trace=trace,
            workspace=foreground_workspace,
            attention_item=attention,
            decision_audit=audit,
            assistant_message=assistant_message,
        )

    @staticmethod
    def _meaningful(trace: CognitiveTrace, attention: AttentionItem | None) -> bool:
        if trace.event_source in NON_TARGET_EVENT_SOURCES or trace.event_type in NON_TARGET_EVENT_TYPES:
            return False
        if trace.question_family == "system" or trace.skill_name == "decision-fixture":
            return False
        selected = (trace.output_json or {}).get("selected_answer")
        if selected == "SILENT" and attention is None:
            return False
        return True
