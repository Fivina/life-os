from __future__ import annotations

from datetime import UTC, datetime
import math

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AIProviderError
from app.core.config import get_settings
from app.database.models import NotebookEntry, NotebookPromotion, UserProfile
from app.events.service import append_event
from app.memory.embeddings import EmbeddingService
from app.memory.jobs import enqueue
from app.notebook.schemas import NotebookEntryCreate, NotebookEntryUpdate, NotebookPromotionRequest, NotebookSearchResult


def _now() -> datetime:
    return datetime.now(UTC)


def _get(db: Session, user: UserProfile, entry_id: str) -> NotebookEntry:
    row = db.scalar(select(NotebookEntry).where(NotebookEntry.id == entry_id, NotebookEntry.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook entry not found.")
    return row


def create_entry(db: Session, user: UserProfile, payload: NotebookEntryCreate, *, idempotency_key: str | None = None) -> NotebookEntry:
    if idempotency_key:
        existing = db.scalar(select(NotebookEntry).where(NotebookEntry.user_id == user.id, NotebookEntry.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    row = NotebookEntry(
        user_id=user.id, entry_type=payload.entry_type, title=payload.title, content=payload.content,
        status="ACTIVE", source=payload.source, source_ref=payload.source_ref,
        conversation_thread_id=payload.conversation_thread_id, workspace_ref=payload.workspace_ref,
        tags_json=payload.tags, metadata_json={**payload.metadata, "execution_authority": "NONE"},
        idempotency_key=idempotency_key,
    )
    db.add(row)
    db.flush()
    enqueue(db, user, job_type="notebook_embedding.refresh", source_type="notebook_entry", source_id=row.id)
    append_event(db, user, event_type="notebook.entry_created", aggregate_type="notebook_entry", aggregate_id=row.id,
                 payload={"entry_id": row.id, "entry_type": row.entry_type}, outbox=True)
    return row


def get_entry(db: Session, user: UserProfile, entry_id: str) -> NotebookEntry:
    return _get(db, user, entry_id)


def list_entries(db: Session, user: UserProfile, *, entry_type: str | None = None, status_filter: str | None = None, limit: int = 100) -> list[NotebookEntry]:
    query = select(NotebookEntry).where(NotebookEntry.user_id == user.id)
    if entry_type:
        query = query.where(NotebookEntry.entry_type == entry_type.upper())
    if status_filter:
        query = query.where(NotebookEntry.status == status_filter.upper())
    return list(db.scalars(query.order_by(NotebookEntry.updated_at.desc()).limit(min(limit, 200))).all())


def update_entry(db: Session, user: UserProfile, entry_id: str, payload: NotebookEntryUpdate) -> NotebookEntry:
    row = _get(db, user, entry_id)
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail=f"Notebook entry version conflict. Current version is {row.version}.")
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if "tags" in changes:
        changes["tags_json"] = changes.pop("tags")
    for key, value in changes.items():
        setattr(row, key, value)
    row.version += 1
    if {"title", "content"} & changes.keys():
        row.embedding_vector = None
        enqueue(db, user, job_type="notebook_embedding.refresh", source_type="notebook_entry", source_id=row.id)
    append_event(db, user, event_type="notebook.entry_updated", aggregate_type="notebook_entry", aggregate_id=row.id,
                 payload={"entry_id": row.id, "fields": sorted(changes)}, outbox=True)
    return row


def review_entry(db: Session, user: UserProfile, entry_id: str) -> NotebookEntry:
    row = _get(db, user, entry_id)
    if row.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Archived notebook entries cannot be reviewed.")
    if row.reviewed_at is not None:
        return row
    row.reviewed_at = _now(); row.status = "REVIEWED"; row.version += 1
    append_event(db, user, event_type="notebook.entry_reviewed", aggregate_type="notebook_entry", aggregate_id=row.id,
                 payload={"entry_id": row.id}, outbox=True)
    return row


def archive_entry(db: Session, user: UserProfile, entry_id: str) -> NotebookEntry:
    row = _get(db, user, entry_id)
    if row.archived_at is not None:
        return row
    row.archived_at = _now(); row.status = "ARCHIVED"; row.version += 1
    append_event(db, user, event_type="notebook.entry_archived", aggregate_type="notebook_entry", aggregate_id=row.id,
                 payload={"entry_id": row.id}, outbox=True)
    return row


def promote_entry(db: Session, user: UserProfile, entry_id: str, payload: NotebookPromotionRequest, *, idempotency_key: str) -> tuple[NotebookEntry, NotebookPromotion]:
    replay = db.scalar(select(NotebookPromotion).where(NotebookPromotion.user_id == user.id, NotebookPromotion.idempotency_key == idempotency_key))
    if replay is not None:
        return _get(db, user, replay.notebook_entry_id), replay
    row = _get(db, user, entry_id)
    existing = db.scalar(select(NotebookPromotion).where(NotebookPromotion.notebook_entry_id == row.id, NotebookPromotion.destination_type == payload.destination_type))
    if existing is not None:
        return row, existing
    promotion = NotebookPromotion(user_id=user.id, notebook_entry_id=row.id, destination_type=payload.destination_type,
                                  destination_ref=payload.destination_ref, idempotency_key=idempotency_key,
                                  metadata_json={"authority": "explicit_user_promotion", "created_entities": []})
    db.add(promotion)
    row.status = "PROMOTED"; row.promoted_at = _now(); row.version += 1
    db.flush()
    append_event(db, user, event_type="notebook.entry_promoted", aggregate_type="notebook_entry", aggregate_id=row.id,
                 payload={"entry_id": row.id, "promotion_id": promotion.id, "destination_type": promotion.destination_type}, outbox=True)
    return row, promotion


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right): return 0.0
    dot = sum(a * b for a, b in zip(left, right)); norm = math.sqrt(sum(a*a for a in left) * sum(b*b for b in right))
    return dot / norm if norm else 0.0


def search_entries(db: Session, user: UserProfile, query: str, *, limit: int = 20) -> list[NotebookSearchResult]:
    terms = {part.lower() for part in query.split() if part}
    candidates = list(db.scalars(select(NotebookEntry).where(NotebookEntry.user_id == user.id, NotebookEntry.status != "ARCHIVED").order_by(NotebookEntry.updated_at.desc()).limit(200)).all())
    query_embedding = None
    try:
        response = EmbeddingService(get_settings(), AIGateway(get_settings())).embed(db, user, [query], task_type="RETRIEVAL_QUERY", optional=True)
        query_embedding = response
    except Exception:
        query_vector = None
    results = []
    for row in candidates:
        haystack = f"{row.title} {row.content} {' '.join(row.tags_json)}".lower()
        lexical = sum(1 for term in terms if term in haystack) / max(len(terms), 1)
        semantic = _cosine(query_embedding.vectors[0], row.embedding_vector) if (
            query_embedding is not None and EmbeddingService.compatible(query_embedding, row)
        ) else None
        score = max(lexical, semantic or 0.0)
        if score > 0:
            results.append(NotebookSearchResult(entry=row, score=round(score, 6), lexical_score=round(lexical, 6), semantic_score=round(semantic, 6) if semantic is not None else None))
    return sorted(results, key=lambda item: (-item.score, item.entry.title.lower()))[:min(limit, 50)]
