from __future__ import annotations

import math
import re
import hashlib
from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.types import AIProviderError
from app.core.config import Settings
from app.database.models import Episode, MemoryItem, MemoryRetrievalAudit, UserProfile
from app.memory.confidence import clamp, effective_confidence
from app.memory.embeddings import EmbeddingService
from app.memory.schemas import EpisodeRead, EpisodeSearchResult, MemorySearchResult
from app.memory.service import _read


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1}


def _lexical_similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cosine(left, right) -> float:
    if left is None or right is None:
        return 0.0
    a, b = list(left), list(right)
    if not a or len(a) != len(b):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in a)) * math.sqrt(sum(value * value for value in b))
    if denominator == 0:
        return 0.0
    return clamp((sum(x * y for x, y in zip(a, b)) / denominator + 1.0) / 2.0)


def _recency(value: datetime, now: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    days = max(0.0, (now - value).total_seconds() / 86400)
    return math.pow(0.5, days / 180)


class MemoryRetrievalService:
    def __init__(self, settings: Settings, embeddings: EmbeddingService):
        self.settings = settings
        self.embeddings = embeddings

    def search_memories(
        self,
        db: Session,
        user: UserProfile,
        query: str,
        *,
        domain: str | None = None,
        domains: list[str] | None = None,
        memory_types: list[str] | None = None,
        current_context: str | None = None,
        include_pinned: bool = True,
        minimum_relevance: float | None = None,
        limit: int | None = None,
        request_id: str | None = None,
    ) -> list[MemorySearchResult]:
        started = perf_counter()
        bounded_limit = min(max(limit or self.settings.memory_retrieval_limit, 1), self.settings.memory_retrieval_limit)
        requested_domains = set(domains or ([] if domain is None else [domain]))
        search_text = f"{query} {current_context or ''}".strip()
        now = datetime.now(UTC)
        conditions = [
            MemoryItem.user_id == user.id,
            MemoryItem.deleted_at.is_(None),
            MemoryItem.status.in_(["active", "uncertain", "candidate"]),
        ]
        if memory_types:
            conditions.append(MemoryItem.memory_type.in_(memory_types))
        if requested_domains:
            conditions.append(MemoryItem.domain.in_(sorted(requested_domains | {"general", "global"})))
        if not include_pinned:
            conditions.append(MemoryItem.pinned.is_(False))
        rows = list(
            db.scalars(
                select(MemoryItem)
                .where(*conditions)
                .order_by(MemoryItem.pinned.desc(), MemoryItem.importance.desc(), MemoryItem.last_observed_at.desc())
                .limit(300)
            ).all()
        )
        if not rows:
            self._audit(db, user, "semantic_memory", search_text, sorted(requested_domains), 0, started, degraded=False)
            return []
        query_embedding, degraded = self._query_vector(db, user, search_text, request_id=request_id)
        scored: list[MemorySearchResult] = []
        for row in rows:
            if row.valid_until is not None:
                valid_until = row.valid_until if row.valid_until.tzinfo else row.valid_until.replace(tzinfo=UTC)
                if valid_until <= now:
                    continue
            lexical = _lexical_similarity(search_text, f"{row.domain} {row.content}")
            vector = _cosine(query_embedding.vectors[0], row.embedding_vector) if (
                query_embedding is not None and EmbeddingService.compatible(query_embedding, row)
            ) else 0.0
            semantic = max(lexical, vector)
            domain_match = 1.0 if requested_domains and (row.domain in requested_domains or row.domain == "general") else (0.5 if not requested_domains else 0.0)
            confidence = effective_confidence(row, now=now)
            recency = _recency(row.last_observed_at, now)
            status_factor = {"active": 1.0, "uncertain": 0.55, "candidate": 0.42}.get(row.status, 0.0)
            confirmation = 1.0 if row.pinned else (0.75 if row.user_confirmed else 0.0)
            score = (
                0.46 * semantic
                + 0.12 * domain_match
                + 0.12 * row.importance
                + 0.12 * confidence
                + 0.07 * recency
                + 0.07 * confirmation
                + 0.04 * status_factor
            )
            if score < (minimum_relevance if minimum_relevance is not None else self.settings.memory_min_relevance):
                continue
            components = {
                "semantic": round(semantic, 4),
                "domain": round(domain_match, 4),
                "importance": round(row.importance, 4),
                "confidence": round(confidence, 4),
                "recency": round(recency, 4),
                "confirmation": round(confirmation, 4),
            }
            scored.append(MemorySearchResult(memory=_read(row), score=round(score, 4), components=components))
        scored.sort(key=lambda item: (item.score, item.memory.pinned, item.memory.updated_at), reverse=True)
        result = scored[:bounded_limit]
        self._audit(db, user, "semantic_memory", search_text, sorted(requested_domains), len(result), started, degraded=degraded)
        return result

    def search_episodes(
        self,
        db: Session,
        user: UserProfile,
        query: str,
        *,
        domain: str | None = None,
        limit: int | None = None,
        request_id: str | None = None,
    ) -> list[EpisodeSearchResult]:
        started = perf_counter()
        bounded_limit = min(max(limit or self.settings.episode_retrieval_limit, 1), self.settings.episode_retrieval_limit)
        now = datetime.now(UTC)
        conditions = [Episode.user_id == user.id, Episode.status == "active"]
        if domain:
            conditions.append(or_(Episode.domain.in_([domain, "general"]), Episode.domain.is_(None)))
        rows = list(
            db.scalars(
                select(Episode)
                .where(*conditions)
                .order_by(Episode.end_at.desc())
                .limit(200)
            ).all()
        )
        if not rows:
            self._audit(db, user, "episode", query, [domain] if domain else [], 0, started, degraded=False)
            return []
        query_embedding, degraded = self._query_vector(db, user, query, request_id=request_id)
        scored: list[EpisodeSearchResult] = []
        for row in rows:
            lexical = _lexical_similarity(query, f"{row.domain or ''} {row.title} {row.summary}")
            vector = _cosine(query_embedding.vectors[0], row.embedding_vector) if (
                query_embedding is not None and EmbeddingService.compatible(query_embedding, row)
            ) else 0.0
            semantic = max(lexical, vector)
            domain_match = 1.0 if domain and row.domain in {domain, None, "general"} else (0.5 if not domain else 0.0)
            score = 0.58 * semantic + 0.14 * domain_match + 0.12 * row.importance + 0.08 * row.confidence + 0.08 * _recency(row.end_at, now)
            if score >= self.settings.memory_min_relevance:
                scored.append(EpisodeSearchResult(episode=EpisodeRead.model_validate(row), score=round(score, 4)))
        scored.sort(key=lambda item: item.score, reverse=True)
        result = scored[:bounded_limit]
        self._audit(db, user, "episode", query, [domain] if domain else [], len(result), started, degraded=degraded)
        return result

    def _query_vector(self, db: Session, user: UserProfile, query: str, *, request_id: str | None):
        try:
            response = self.embeddings.embed(
                db,
                user,
                [query],
                task_type="RETRIEVAL_QUERY",
                request_id=request_id,
                optional=True,
            )
        except AIProviderError:
            return None, True
        return response, False

    @staticmethod
    def _audit(
        db: Session,
        user: UserProfile,
        retrieval_type: str,
        query: str,
        domains: list[str | None],
        returned_count: int,
        started: float,
        *,
        degraded: bool,
    ) -> None:
        db.add(
            MemoryRetrievalAudit(
                user_id=user.id,
                retrieval_type=retrieval_type,
                query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                domains_json=[item for item in domains if item],
                returned_count=returned_count,
                duration_ms=max(0, round((perf_counter() - started) * 1000)),
                degraded=degraded,
            )
        )
        db.flush()
