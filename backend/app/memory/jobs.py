from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.core.config import Settings
from app.database.models import (
    ConversationMessage,
    ConversationThread,
    MemoryProcessingJob,
    NotebookEntry,
    RecommendationOutcome,
    UserProfile,
)
from app.memory.curator import MemoryCurator
from app.memory.embeddings import EmbeddingService
from app.memory.service import MemoryService
from app.memory.schemas import MemoryCandidate


def utcnow() -> datetime:
    return datetime.now(UTC)


class PermanentMemoryJobError(Exception):
    pass


def enqueue(
    db: Session,
    user: UserProfile,
    *,
    job_type: str,
    source_type: str,
    source_id: str,
    payload: dict | None = None,
) -> MemoryProcessingJob:
    existing = db.scalar(
        select(MemoryProcessingJob).where(
            MemoryProcessingJob.user_id == user.id,
            MemoryProcessingJob.job_type == job_type,
            MemoryProcessingJob.source_type == source_type,
            MemoryProcessingJob.source_id == source_id,
        )
    )
    if existing is not None:
        return existing
    row = MemoryProcessingJob(
        user_id=user.id,
        job_type=job_type,
        source_type=source_type,
        source_id=source_id,
        status="pending",
        attempts=0,
        available_at=utcnow(),
        payload_json=payload or {},
    )
    db.add(row)
    db.flush()
    return row


class MemoryJobProcessor:
    def __init__(self, settings: Settings):
        self.settings = settings
        gateway = AIGateway(settings)
        memories = MemoryService(EmbeddingService(settings, gateway))
        self.memories = memories
        self.curator = MemoryCurator(gateway, memories)

    def process_pending(self, db: Session, *, limit: int = 25) -> int:
        now = utcnow()
        stale_before = now - timedelta(minutes=15)
        rows = list(
            db.scalars(
                select(MemoryProcessingJob)
                .where(
                    or_(
                        (MemoryProcessingJob.status == "pending") & (MemoryProcessingJob.available_at <= now),
                        (MemoryProcessingJob.status == "running") & (MemoryProcessingJob.locked_at < stale_before),
                    )
                )
                .order_by(MemoryProcessingJob.available_at.asc(), MemoryProcessingJob.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        processed = 0
        for row in rows:
            row.status = "running"
            row.locked_at = now
            row.attempts += 1
            db.flush()
            try:
                self._process(db, row)
                row.status = "completed"
                row.processed_at = utcnow()
                row.last_error = None
                processed += 1
            except PermanentMemoryJobError as exc:
                row.status = "skipped"
                row.processed_at = utcnow()
                row.last_error = str(exc)[:2000]
                processed += 1
            except Exception as exc:
                row.last_error = str(exc)[:2000]
                row.locked_at = None
                if row.attempts >= self.settings.outbox_max_attempts:
                    row.status = "failed"
                else:
                    row.status = "pending"
                    backoff = min(
                        self.settings.outbox_base_backoff_seconds * (2 ** max(row.attempts - 1, 0)),
                        self.settings.outbox_max_backoff_seconds,
                    )
                    row.available_at = utcnow() + timedelta(seconds=backoff)
            row.version += 1
            db.flush()
        return processed

    def _process(self, db: Session, job: MemoryProcessingJob) -> None:
        user = db.scalar(select(UserProfile).where(UserProfile.id == job.user_id))
        if user is None:
            raise PermanentMemoryJobError("Memory job user no longer exists.")
        if job.job_type == "memory_candidate.process" and job.source_type == "conversation_message":
            message = db.scalar(
                select(ConversationMessage).where(
                    ConversationMessage.id == job.source_id,
                    ConversationMessage.user_id == user.id,
                )
            )
            if message is None:
                raise PermanentMemoryJobError("Conversation message source no longer exists.")
            thread = db.scalar(
                select(ConversationThread).where(
                    ConversationThread.id == message.thread_id,
                    ConversationThread.user_id == user.id,
                )
            )
            if thread is None:
                raise PermanentMemoryJobError("Conversation thread source no longer exists.")
            self.curator.capture(
                db,
                user,
                thread,
                message_id=message.id,
                message=message.content,
                request_id=f"memory-job:{job.id}",
            )
            return
        if job.job_type == "recommendation_outcome.process" and job.source_type == "recommendation_outcome":
            outcome = db.scalar(
                select(RecommendationOutcome).where(
                    RecommendationOutcome.id == job.source_id,
                    RecommendationOutcome.user_id == user.id,
                )
            )
            if outcome is None:
                raise PermanentMemoryJobError("Recommendation outcome source no longer exists.")
            candidate_payload = (outcome.metadata_json or {}).get("memory_candidate")
            if outcome.accepted is True and isinstance(candidate_payload, dict):
                candidate = MemoryCandidate.model_validate(candidate_payload)
                matching = list(
                    db.scalars(
                        select(RecommendationOutcome).where(
                            RecommendationOutcome.user_id == user.id,
                            RecommendationOutcome.domain == outcome.domain,
                            RecommendationOutcome.recommendation_type == outcome.recommendation_type,
                            RecommendationOutcome.accepted.is_(True),
                        )
                    ).all()
                )
                matching = [
                    item
                    for item in matching
                    if isinstance((item.metadata_json or {}).get("memory_candidate"), dict)
                    and (item.metadata_json or {})["memory_candidate"].get("normalized_key") == candidate.normalized_key
                ]
                if len(matching) >= 3:
                    for item in matching:
                        self.memories.remember(
                            db,
                            user,
                            candidate,
                            source_type="recommendation_outcome",
                            source_id=item.id,
                            source_kind="observed_recommendation_outcome",
                            evidence_kind="recommendation_outcome",
                            user_confirmed=False,
                            request_id=f"memory-job:{job.id}",
                        )
            if outcome.feedback_text and self.curator.should_inspect(outcome.feedback_text):
                self.curator.capture(
                    db,
                    user,
                    None,
                    message_id=outcome.id,
                    message=outcome.feedback_text,
                    request_id=f"memory-job:{job.id}",
                    source_type="recommendation_outcome",
                    source_kind="recommendation_feedback",
                )
            return
        if job.job_type == "notebook_embedding.refresh" and job.source_type == "notebook_entry":
            entry = db.scalar(
                select(NotebookEntry).where(NotebookEntry.id == job.source_id, NotebookEntry.user_id == user.id)
            )
            if entry is None:
                raise PermanentMemoryJobError("Notebook entry source no longer exists.")
            embedding = EmbeddingService(self.settings, AIGateway(self.settings))
            if not embedding.try_attach(
                db, user, entry, f"{entry.title}\n{entry.content}", request_id=f"notebook-job:{job.id}"
            ):
                raise RuntimeError("Notebook embedding provider was unavailable.")
            return
        raise PermanentMemoryJobError(f"Unsupported memory job type: {job.job_type}/{job.source_type}.")
