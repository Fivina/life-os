from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import (
    ConversationSummary,
    ConversationMessage,
    Episode,
    Event,
    MemoryConsolidationRun,
    MemoryItem,
    RecommendationOutcome,
    UserProfile,
)
from app.events.service import append_event
from app.memory.curator import MEMORY_SIGNAL
from app.memory.embeddings import EmbeddingService
from app.memory.jobs import enqueue
from app.memory.schemas import ConsolidationRead


IGNORED_PREFIXES = ("notification.", "personal_model.", "memory.", "episode.")


def _domain(event: Event) -> str:
    prefix = event.event_type.split(".", 1)[0]
    if prefix in {"fitness", "learning", "kitchen"}:
        return prefix
    return str(event.payload.get("domain") or "life")


class MemoryConsolidator:
    def __init__(self, settings: Settings, embeddings: EmbeddingService):
        self.settings = settings
        self.embeddings = embeddings

    def consolidate_user(
        self,
        db: Session,
        user: UserProfile,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        force: bool = False,
    ) -> ConsolidationRead:
        now = datetime.now(UTC)
        end = period_end or now
        start = period_start or (end - timedelta(hours=self.settings.memory_consolidation_lookback_hours))
        existing = db.scalar(
            select(MemoryConsolidationRun).where(
                MemoryConsolidationRun.user_id == user.id,
                MemoryConsolidationRun.period_start == start,
                MemoryConsolidationRun.period_end == end,
            )
        )
        if existing is not None and not force and existing.status in {"completed", "running"}:
            return ConsolidationRead.model_validate(existing)
        run = existing or MemoryConsolidationRun(user_id=user.id, period_start=start, period_end=end, status="running")
        if existing is None:
            db.add(run)
            db.flush()
        else:
            run.status = "running"
            run.error = None
            run.finished_at = None
        try:
            events = list(
                db.scalars(
                    select(Event)
                    .where(Event.user_id == user.id, Event.occurred_at >= start, Event.occurred_at < end)
                    .order_by(Event.occurred_at.asc())
                ).all()
            )
            meaningful = [event for event in events if not event.event_type.startswith(IGNORED_PREFIXES)]
            run.source_event_count = len(meaningful)
            created = 0
            candidate_jobs = 0
            messages = list(
                db.scalars(
                    select(ConversationMessage).where(
                        ConversationMessage.user_id == user.id,
                        ConversationMessage.role == "user",
                        ConversationMessage.created_at >= start,
                        ConversationMessage.created_at < end,
                    )
                ).all()
            )
            for message in messages:
                if not MEMORY_SIGNAL.search(message.content):
                    continue
                job = enqueue(
                    db,
                    user,
                    job_type="memory_candidate.process",
                    source_type="conversation_message",
                    source_id=message.id,
                    payload={"thread_id": message.thread_id, "nightly_recovery": True},
                )
                if job.status == "pending" and job.attempts == 0:
                    candidate_jobs += 1

            summaries = list(
                db.scalars(
                    select(ConversationSummary)
                    .where(ConversationSummary.user_id == user.id, ConversationSummary.updated_at >= start, ConversationSummary.updated_at < end)
                    .order_by(ConversationSummary.updated_at.desc())
                ).all()
            )
            outcomes_all = list(
                db.scalars(
                    select(RecommendationOutcome)
                    .where(RecommendationOutcome.user_id == user.id, RecommendationOutcome.observed_at >= start, RecommendationOutcome.observed_at < end)
                    .order_by(RecommendationOutcome.observed_at.asc())
                ).all()
            )
            groups: dict[str, list[Event]] = defaultdict(list)
            for event in meaningful:
                groups[_domain(event)].append(event)
            domains = set(groups) | {item.domain for item in outcomes_all}
            for domain in sorted(domains):
                    group = groups.get(domain, [])
                    outcomes = [item for item in outcomes_all if item.domain == domain]
                    summary = summaries[0] if summaries else None
                    signal_count = len(group) + len(outcomes) + (1 if summary is not None else 0)
                    if signal_count < self.settings.memory_consolidation_event_threshold:
                        continue
                    source_ids = [item.id for item in group] + [item.id for item in outcomes]
                    if summary is not None:
                        source_ids.append(summary.id)
                    key_source = f"{user.id}:{domain}:{':'.join(source_ids)}"
                    key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:64]
                    if db.scalar(select(Episode.id).where(Episode.user_id == user.id, Episode.normalized_key == key)):
                        continue
                    kinds: list[str] = []
                    entities: list[dict] = []
                    for event in group:
                        label = event.event_type.replace(".", " ")
                        if label not in kinds:
                            kinds.append(label)
                        entities.append({"type": event.aggregate_type, "id": event.aggregate_id, "event": event.event_type})
                    for outcome in outcomes[:10]:
                        entities.append({"type": "recommendation_outcome", "id": outcome.id, "outcome": outcome.outcome})
                    episode_summary = f"{len(group)} meaningful {domain} events"
                    if kinds:
                        episode_summary += f": {', '.join(kinds[:6])}"
                    episode_summary += "."
                    if summary:
                        episode_summary += f" Conversation context: {summary.summary[:400]}"
                    if outcomes:
                        accepted = len([item for item in outcomes if item.accepted is True])
                        episode_summary += f" Recommendation outcomes: {accepted} accepted of {len(outcomes)} recorded."
                    timestamps = [item.occurred_at for item in group] + [item.observed_at for item in outcomes]
                    if summary is not None:
                        timestamps.append(summary.updated_at)
                    episode = Episode(
                        user_id=user.id,
                        domain=domain,
                        title=f"{domain.title()} activity",
                        summary=episode_summary,
                        normalized_key=key,
                        start_at=min(timestamps),
                        end_at=max(timestamps),
                        importance=min(1.0, 0.45 + signal_count * 0.04),
                        confidence=0.78,
                        status="active",
                        source_event_start_id=group[0].id if group else None,
                        source_event_end_id=group[-1].id if group else None,
                        source_summary_id=summary.id if summary else None,
                        related_entities_json=entities[:50],
                        metadata_json={"event_types": kinds, "consolidation_version": "episode-v1"},
                    )
                    db.add(episode)
                    db.flush()
                    self.embeddings.try_attach(db, user, episode, f"{episode.title}. {episode.summary}")
                    append_event(
                        db,
                        user,
                        event_type="episode.created",
                        aggregate_type="episode",
                        aggregate_id=episode.id,
                        payload={"episode_id": episode.id, "domain": domain, "signal_count": signal_count},
                        outbox=False,
                        increment_world_revision=False,
                    )
                    created += 1
            run.episode_count = created
            run.memory_count = candidate_jobs
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.error = None
            db.flush()
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(UTC)
            db.flush()
            raise
        return ConsolidationRead.model_validate(run)

    def consolidate_due(self, db: Session) -> int:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=1)
        completed = 0
        for user in db.scalars(select(UserProfile)).all():
            existing = db.scalar(
                select(MemoryConsolidationRun.id).where(
                    MemoryConsolidationRun.user_id == user.id,
                    MemoryConsolidationRun.period_start == start,
                    MemoryConsolidationRun.period_end == today,
                    MemoryConsolidationRun.status == "completed",
                )
            )
            if existing:
                continue
            self.consolidate_user(db, user, period_start=start, period_end=today)
            completed += 1
        return completed
