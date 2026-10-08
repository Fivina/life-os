from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import ConversationMessage, ConversationSummary, ConversationThread, UserProfile
from app.events.service import append_event


def _token_estimate(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


class ConversationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_thread(
        self,
        db: Session,
        user: UserProfile,
        *,
        title: str | None = None,
        default_skill: str = "self-core",
    ) -> ConversationThread:
        thread = ConversationThread(
            user_id=user.id,
            title=(title or "New conversation").strip(),
            default_skill=default_skill,
            last_message_at=datetime.now(UTC),
        )
        db.add(thread)
        db.flush()
        append_event(
            db,
            user,
            event_type="conversation.thread.created",
            aggregate_type="conversation_thread",
            aggregate_id=thread.id,
            payload={"conversation_id": thread.id},
            outbox=True,
        )
        return thread

    def get_thread(self, db: Session, user: UserProfile, thread_id: str, *, include_archived: bool = True) -> ConversationThread:
        statement = select(ConversationThread).where(
            ConversationThread.id == thread_id,
            ConversationThread.user_id == user.id,
        )
        if not include_archived:
            statement = statement.where(ConversationThread.status == "active")
        thread = db.scalar(statement)
        if thread is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return thread

    def resolve_thread(
        self,
        db: Session,
        user: UserProfile,
        *,
        thread_id: str | None,
        default_skill: str,
    ) -> ConversationThread:
        if thread_id:
            return self.get_thread(db, user, thread_id, include_archived=False)
        return self.create_thread(db, user, default_skill=default_skill)

    def list_threads(self, db: Session, user: UserProfile, *, limit: int = 30) -> list[ConversationThread]:
        return list(
            db.scalars(
                select(ConversationThread)
                .where(ConversationThread.user_id == user.id, ConversationThread.status == "active")
                .order_by(ConversationThread.last_message_at.desc())
                .limit(limit)
            ).all()
        )

    def append_message(
        self,
        db: Session,
        user: UserProfile,
        thread: ConversationThread,
        *,
        role: str,
        content: str,
        skill_name: str | None = None,
        request_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConversationMessage:
        if thread.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        sequence_number = db.scalar(
            select(func.coalesce(func.max(ConversationMessage.sequence_number), 0)).where(
                ConversationMessage.thread_id == thread.id
            )
        ) or 0
        message = ConversationMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=role,
            content=content,
            skill_name=skill_name,
            request_id=request_id,
            sequence_number=sequence_number + 1,
            token_estimate=_token_estimate(content),
            metadata_json=metadata or {},
        )
        db.add(message)
        thread.last_message_at = datetime.now(UTC)
        if role == "user" and thread.title == "New conversation":
            clean = " ".join(content.split())
            thread.title = clean[:177] + "..." if len(clean) > 180 else clean
        thread.version += 1
        db.flush()
        append_event(
            db,
            user,
            event_type="conversation.message.created",
            aggregate_type="conversation_message",
            aggregate_id=message.id,
            payload={"conversation_id": thread.id, "message_id": message.id, "role": role},
            outbox=True,
        )
        return message

    def messages(self, db: Session, user: UserProfile, thread_id: str, *, limit: int = 100) -> list[ConversationMessage]:
        self.get_thread(db, user, thread_id)
        rows = list(
            db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.thread_id == thread_id, ConversationMessage.user_id == user.id)
                .order_by(ConversationMessage.sequence_number.desc())
                .limit(limit)
            ).all()
        )
        rows.reverse()
        return rows

    def recent_messages(self, db: Session, user: UserProfile, thread_id: str, *, limit: int | None = None) -> list[ConversationMessage]:
        return self.messages(db, user, thread_id, limit=limit or self.settings.conversation_recent_window)

    def get_summary(self, db: Session, user: UserProfile, thread_id: str) -> ConversationSummary | None:
        return db.scalar(
            select(ConversationSummary).where(
                ConversationSummary.thread_id == thread_id,
                ConversationSummary.user_id == user.id,
            )
        )

    def archive(self, db: Session, user: UserProfile, thread_id: str) -> ConversationThread:
        thread = self.get_thread(db, user, thread_id)
        thread.status = "archived"
        thread.version += 1
        append_event(
            db,
            user,
            event_type="conversation.thread.archived",
            aggregate_type="conversation_thread",
            aggregate_id=thread.id,
            payload={"conversation_id": thread.id},
            outbox=True,
        )
        return thread

    def recent_work(self, db: Session, user: UserProfile, *, skill_name: str, thread_id: str, now: datetime) -> list[dict]:
        """Bounded, same-skill historical results, never current canonical truth."""
        rows = db.scalars(select(ConversationMessage).join(
            ConversationThread, ConversationThread.id == ConversationMessage.thread_id,
        ).where(
            ConversationMessage.user_id == user.id, ConversationThread.user_id == user.id,
            ConversationThread.status == "active", ConversationMessage.thread_id != thread_id,
            ConversationMessage.skill_name == skill_name, ConversationMessage.role == "assistant",
            ConversationMessage.created_at >= now - timedelta(hours=48),
            ConversationMessage.created_at <= now,
        ).order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc()).limit(30))
        items, seen = [], set()
        for row in rows:
            metadata = row.metadata_json or {}
            if row.thread_id in seen or metadata.get("error_code") or metadata.get("response_type") not in {"INFORMATION", "MUTATION_RESULT"}:
                continue
            if any(marker in row.content for marker in ("sk-proj-", "sk-svcacct-", "AIza", "apikey_")):
                continue
            seen.add(row.thread_id)
            items.append({"message_id": row.id, "thread_id": row.thread_id,
                          "created_at": row.created_at.isoformat(), "skill_name": row.skill_name,
                          "excerpt": " ".join(row.content.split())[:320]})
            if len(items) == 3:
                break
        return items

    def compact_if_needed(self, db: Session, user: UserProfile, thread: ConversationThread) -> ConversationSummary | None:
        count = db.scalar(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.thread_id == thread.id,
                ConversationMessage.user_id == user.id,
            )
        ) or 0
        if count <= self.settings.conversation_compaction_threshold:
            return self.get_summary(db, user, thread.id)
        all_messages = self.messages(db, user, thread.id, limit=count)
        compacted = all_messages[: -self.settings.conversation_recent_window]
        if not compacted:
            return self.get_summary(db, user, thread.id)
        existing = self.get_summary(db, user, thread.id)
        already_covered = existing.covered_message_count if existing else 0
        new_messages = compacted[already_covered:]
        if not new_messages:
            return existing
        lines = [f"{item.role.upper()}: {' '.join(item.content.split())[:600]}" for item in new_messages]
        previous = existing.summary if existing else ""
        combined = "\n".join(part for part in [previous, *lines] if part).strip()
        combined = combined[-8000:]
        summary = existing or ConversationSummary(thread_id=thread.id, user_id=user.id, summary="")
        summary.summary = combined
        summary.covered_message_count = len(compacted)
        summary.covers_until_message_id = compacted[-1].id
        summary.token_estimate = _token_estimate(combined)
        if existing:
            summary.version += 1
        else:
            db.add(summary)
        db.flush()
        return summary
