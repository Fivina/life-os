from __future__ import annotations

import re
import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import MemoryEvidence, MemoryItem, MemorySuppression, RecommendationOutcome, UserProfile
from app.ai.types import AIProviderError
from app.events.service import append_event
from app.memory.confidence import effective_confidence, evidence_confidence, status_for
from app.memory.embeddings import EmbeddingService
from app.memory.merge import MemoryMergeService
from app.memory.policy import semantic_identity, validate_semantic_memory
from app.memory.schemas import (
    MemoryCandidate,
    MemoryCreate,
    MemoryDetail,
    MemoryEvidenceRead,
    MemoryRead,
    MemoryUpdate,
    RecommendationOutcomeCreate,
    RecommendationOutcomeRead,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_key(value: str) -> str:
    value = re.sub(r"[^a-z0-9\s-]", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()[:255]


def _read(memory: MemoryItem, evidence_count: int = 0) -> MemoryRead:
    return MemoryRead(
        id=memory.id,
        memory_type=memory.memory_type,
        domain=memory.domain,
        content=memory.content,
        normalized_key=memory.normalized_key,
        polarity=memory.polarity,
        confidence=memory.confidence,
        effective_confidence=effective_confidence(memory),
        importance=memory.importance,
        status=memory.status,
        pinned=memory.pinned,
        user_confirmed=memory.user_confirmed,
        source_kind=memory.source_kind,
        first_observed_at=memory.first_observed_at,
        last_observed_at=memory.last_observed_at,
        last_confirmed_at=memory.last_confirmed_at,
        valid_from=memory.valid_from,
        valid_until=memory.valid_until,
        supersedes_memory_id=memory.supersedes_memory_id,
        embedding_provider=memory.embedding_provider,
        embedding_model=memory.embedding_model,
        embedding_dimension=memory.embedding_dimension,
        embedding_version=memory.embedding_version,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        version=memory.version,
        evidence_count=evidence_count,
    )


class MemoryService:
    def __init__(self, embeddings: EmbeddingService, merge: MemoryMergeService | None = None):
        self.embeddings = embeddings
        self.merge = merge or MemoryMergeService()

    def list(
        self,
        db: Session,
        user: UserProfile,
        *,
        include_inactive: bool = False,
        domain: str | None = None,
        memory_type: str | None = None,
        status_filter: str | None = None,
    ) -> list[MemoryRead]:
        query = select(MemoryItem).where(MemoryItem.user_id == user.id, MemoryItem.deleted_at.is_(None))
        if status_filter:
            query = query.where(MemoryItem.status == status_filter)
        elif not include_inactive:
            query = query.where(MemoryItem.status.in_(["candidate", "active", "uncertain"]))
        if domain:
            query = query.where(MemoryItem.domain == domain)
        if memory_type:
            query = query.where(MemoryItem.memory_type == memory_type)
        rows = list(db.scalars(query.order_by(MemoryItem.pinned.desc(), MemoryItem.importance.desc(), MemoryItem.updated_at.desc())).all())
        counts = dict(
            db.execute(
                select(MemoryEvidence.memory_id, func.count(MemoryEvidence.id))
                .where(MemoryEvidence.user_id == user.id)
                .group_by(MemoryEvidence.memory_id)
            ).all()
        )
        return [_read(row, counts.get(row.id, 0)) for row in rows]

    def get_model(self, db: Session, user: UserProfile, memory_id: str) -> MemoryItem:
        row = db.scalar(select(MemoryItem).where(MemoryItem.id == memory_id, MemoryItem.user_id == user.id))
        if row is None or row.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
        return row

    def detail(self, db: Session, user: UserProfile, memory_id: str) -> MemoryDetail:
        memory = self.get_model(db, user, memory_id)
        evidence = list(
            db.scalars(
                select(MemoryEvidence)
                .where(MemoryEvidence.memory_id == memory.id, MemoryEvidence.user_id == user.id)
                .order_by(MemoryEvidence.observed_at.desc())
            ).all()
        )
        return MemoryDetail(**_read(memory, len(evidence)).model_dump(), evidence=[MemoryEvidenceRead.model_validate(item) for item in evidence])

    def create_explicit(self, db: Session, user: UserProfile, payload: MemoryCreate, *, request_id: str | None = None) -> MemoryRead:
        policy = validate_semantic_memory(payload.content, explicit=True)
        if not policy.allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "not_semantic_memory", "reason": policy.reason},
            )
        candidate = MemoryCandidate(
            memory_type=payload.memory_type,
            domain=payload.domain,
            content=payload.content,
            normalized_key=semantic_identity(payload.content),
            polarity=payload.polarity,
            importance=payload.importance,
            explicit=True,
        )
        memory = self.remember(
            db,
            user,
            candidate,
            source_type="api",
            source_id=request_id,
            source_kind="explicit_user",
            evidence_kind="user_confirmation",
            user_confirmed=True,
            pinned=payload.pinned,
            request_id=request_id,
        )
        return _read(memory, self._evidence_count(db, memory.id))

    def remember(
        self,
        db: Session,
        user: UserProfile,
        candidate: MemoryCandidate,
        *,
        source_type: str,
        source_id: str | None,
        source_kind: str,
        evidence_kind: str,
        user_confirmed: bool = False,
        pinned: bool = False,
        request_id: str | None = None,
    ) -> MemoryItem:
        now = utcnow()
        policy = validate_semantic_memory(candidate.content, explicit=candidate.explicit or user_confirmed)
        if not policy.allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "not_semantic_memory", "reason": policy.reason},
            )
        key = normalize_key(candidate.normalized_key or semantic_identity(candidate.content))
        if self._is_suppressed(db, user, key, source_type=source_type, source_id=source_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "memory_source_suppressed", "message": "This forgotten source has already been suppressed."},
            )
        content_changed = False
        decision = self.merge.exact(db, user, candidate, key)
        same_key = decision.existing if decision.action == "reinforce" else None
        contradiction = decision.existing if decision.action == "conflict" else None
        embedding_response = None
        if decision.action == "create":
            try:
                embedding_response = self.embeddings.embed(
                    db,
                    user,
                    [candidate.content],
                    task_type="RETRIEVAL_DOCUMENT",
                    request_id=request_id,
                )
            except AIProviderError:
                embedding_response = None
            if embedding_response is not None:
                decision = self.merge.semantic(
                    db,
                    user,
                    candidate,
                    embedding_response.vectors[0],
                    threshold=self.embeddings.settings.memory_semantic_merge_threshold,
                    embedding_provider=embedding_response.provider,
                    embedding_model=embedding_response.model,
                    embedding_dimension=embedding_response.dimensions,
                )
                same_key = decision.existing if decision.action == "reinforce" else None
                contradiction = decision.existing if decision.action == "conflict" else None
        if contradiction is not None:
            return self._handle_contradiction(
                db,
                user,
                contradiction,
                candidate,
                source_type=source_type,
                source_id=source_id,
                source_kind=source_kind,
                evidence_kind=evidence_kind,
                user_confirmed=user_confirmed,
                request_id=request_id,
            )
        if same_key is not None and self._evidence_exists(
            db,
            same_key.id,
            source_type=source_type,
            source_id=source_id,
            evidence_kind=evidence_kind,
            direction="supports",
        ):
            return same_key
        if same_key is None:
            same_key = MemoryItem(
                user_id=user.id,
                memory_type=candidate.memory_type,
                domain=candidate.domain,
                content=candidate.content.strip(),
                normalized_key=key,
                polarity=candidate.polarity,
                confidence=0.5,
                importance=candidate.importance,
                status="candidate",
                pinned=pinned,
                user_confirmed=user_confirmed,
                source_kind=source_kind,
                first_observed_at=now,
                last_observed_at=now,
                last_confirmed_at=now if user_confirmed else None,
                valid_from=now,
            )
            db.add(same_key)
            db.flush()
            event_type = "memory.created"
        else:
            same_key.last_observed_at = now
            same_key.importance = max(same_key.importance, candidate.importance)
            same_key.user_confirmed = same_key.user_confirmed or user_confirmed
            same_key.pinned = same_key.pinned or pinned
            if user_confirmed:
                same_key.last_confirmed_at = now
                if not same_key.pinned:
                    next_content = candidate.content.strip()
                    content_changed = same_key.content != next_content
                    same_key.content = next_content
            same_key.version += 1
            event_type = "memory.updated"
        self._add_evidence(
            db,
            same_key,
            source_type=source_type,
            source_id=source_id,
            evidence_kind=evidence_kind,
            direction="supports",
            weight=1.0 if user_confirmed else 0.72,
            excerpt=candidate.content,
        )
        self._recompute(db, same_key)
        if embedding_response is not None:
            self.embeddings.attach(same_key, embedding_response, content=same_key.content)
        elif same_key.embedding_vector is None or content_changed:
            self.embeddings.try_attach(db, user, same_key, same_key.content, request_id=request_id)
        append_event(
            db,
            user,
            event_type=event_type,
            aggregate_type="memory",
            aggregate_id=same_key.id,
            payload={"memory_id": same_key.id, "domain": same_key.domain, "memory_type": same_key.memory_type, "source_kind": same_key.source_kind},
            outbox=False,
            increment_world_revision=False,
        )
        db.flush()
        return same_key

    def update(self, db: Session, user: UserProfile, memory_id: str, payload: MemoryUpdate, *, request_id: str | None = None) -> MemoryRead:
        memory = self.get_model(db, user, memory_id)
        if payload.expected_version is not None and payload.expected_version != memory.version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Memory changed after it was loaded.")
        changed_content = payload.content is not None and payload.content.strip() != memory.content
        if changed_content:
            return self._correct(db, user, memory, payload, request_id=request_id)
        if payload.memory_type is not None:
            memory.memory_type = payload.memory_type
        if payload.domain is not None:
            memory.domain = payload.domain
        if payload.polarity is not None:
            memory.polarity = payload.polarity
        if payload.importance is not None:
            memory.importance = payload.importance
        memory.user_confirmed = True
        memory.last_confirmed_at = utcnow()
        memory.last_observed_at = memory.last_confirmed_at
        memory.version += 1
        self._add_evidence(db, memory, source_type="api", source_id=request_id, evidence_kind="user_correction", direction="supports", weight=1.0, excerpt=memory.content)
        self._recompute(db, memory)
        append_event(
            db,
            user,
            event_type="memory.updated",
            aggregate_type="memory",
            aggregate_id=memory.id,
            payload={"memory_id": memory.id, "fields": sorted(payload.model_fields_set)},
            outbox=False,
            increment_world_revision=False,
        )
        db.flush()
        return _read(memory, self._evidence_count(db, memory.id))

    def pin(self, db: Session, user: UserProfile, memory_id: str, pinned: bool) -> MemoryRead:
        memory = self.get_model(db, user, memory_id)
        memory.pinned = pinned
        if pinned:
            memory.user_confirmed = True
            memory.last_confirmed_at = utcnow()
            memory.status = "active"
            memory.confidence = 1.0
        else:
            self._recompute(db, memory)
        memory.version += 1
        append_event(
            db,
            user,
            event_type="memory.pinned" if pinned else "memory.unpinned",
            aggregate_type="memory",
            aggregate_id=memory.id,
            payload={"memory_id": memory.id, "pinned": pinned},
            outbox=False,
            increment_world_revision=False,
        )
        db.flush()
        return _read(memory, self._evidence_count(db, memory.id))

    def confirm(self, db: Session, user: UserProfile, memory_id: str) -> MemoryRead:
        memory = self.get_model(db, user, memory_id)
        memory.user_confirmed = True
        memory.last_confirmed_at = utcnow()
        self._add_evidence(db, memory, source_type="api", source_id=f"confirm:{memory.version}", evidence_kind="user_confirmation", direction="supports", weight=1.0, excerpt=memory.content)
        self._recompute(db, memory)
        memory.version += 1
        append_event(db, user, event_type="memory.confirmed", aggregate_type="memory", aggregate_id=memory.id, payload={"memory_id": memory.id}, outbox=False, increment_world_revision=False)
        db.flush()
        return _read(memory, self._evidence_count(db, memory.id))

    def forget(self, db: Session, user: UserProfile, memory_id: str) -> MemoryRead:
        memory = self.get_model(db, user, memory_id)
        evidence = list(db.scalars(select(MemoryEvidence).where(MemoryEvidence.memory_id == memory.id)).all())
        for item in evidence:
            self._suppress(db, user, memory.normalized_key, source_type=item.source_type, source_id=item.source_id)
        memory.status = "forgotten"
        memory.deleted_at = utcnow()
        memory.embedding_vector = None
        memory.version += 1
        append_event(db, user, event_type="memory.forgotten", aggregate_type="memory", aggregate_id=memory.id, payload={"memory_id": memory.id}, outbox=False, increment_world_revision=False)
        db.flush()
        return _read(memory, self._evidence_count(db, memory.id))

    def _correct(
        self,
        db: Session,
        user: UserProfile,
        memory: MemoryItem,
        payload: MemoryUpdate,
        *,
        request_id: str | None,
    ) -> MemoryRead:
        content = (payload.content or memory.content).strip()
        policy = validate_semantic_memory(content, explicit=True)
        if not policy.allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "not_semantic_memory", "reason": policy.reason},
            )
        now = utcnow()
        replacement = MemoryItem(
            user_id=user.id,
            memory_type=payload.memory_type or memory.memory_type,
            domain=payload.domain or memory.domain,
            content=content,
            normalized_key=semantic_identity(content),
            polarity=payload.polarity if payload.polarity is not None else memory.polarity,
            confidence=0.92,
            importance=payload.importance if payload.importance is not None else memory.importance,
            status="active",
            pinned=memory.pinned,
            user_confirmed=True,
            source_kind="user_correction",
            first_observed_at=now,
            last_observed_at=now,
            last_confirmed_at=now,
            valid_from=now,
            supersedes_memory_id=memory.id,
            metadata_json={"corrected_from_memory_id": memory.id},
        )
        memory.status = "contradicted" if replacement.polarity not in {0, memory.polarity} else "archived"
        memory.valid_until = now
        memory.pinned = False
        memory.version += 1
        db.add(replacement)
        db.flush()
        self._add_evidence(
            db,
            replacement,
            source_type="user_correction",
            source_id=request_id or f"correction:{replacement.id}",
            evidence_kind="user_correction",
            direction="supports",
            weight=1.0,
            excerpt=content,
        )
        self._add_evidence(
            db,
            memory,
            source_type="user_correction",
            source_id=request_id or f"correction:{replacement.id}",
            evidence_kind="user_correction",
            direction="contradicts",
            weight=1.0,
            excerpt=content,
        )
        self.embeddings.try_attach(db, user, replacement, replacement.content, request_id=request_id)
        append_event(
            db,
            user,
            event_type="memory.corrected",
            aggregate_type="memory",
            aggregate_id=replacement.id,
            payload={"memory_id": replacement.id, "supersedes_memory_id": memory.id},
            outbox=False,
            increment_world_revision=False,
        )
        db.flush()
        return _read(replacement, self._evidence_count(db, replacement.id))

    @staticmethod
    def _suppression_key(normalized_key: str, source_type: str | None, source_id: str | None) -> str:
        raw = f"{normalized_key}|{source_type or '*'}|{source_id or '*'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _suppress(
        self,
        db: Session,
        user: UserProfile,
        normalized_key: str,
        *,
        source_type: str | None,
        source_id: str | None,
    ) -> None:
        key = self._suppression_key(normalized_key, source_type, source_id)
        existing = db.scalar(
            select(MemorySuppression).where(MemorySuppression.user_id == user.id, MemorySuppression.suppression_key == key)
        )
        if existing is None:
            db.add(
                MemorySuppression(
                    user_id=user.id,
                    suppression_key=key,
                    normalized_key=normalized_key,
                    source_type=source_type,
                    source_id=source_id,
                    reason="user_forgot",
                    active=True,
                    suppressed_at=utcnow(),
                )
            )
            db.flush()
        else:
            existing.active = True
            existing.expires_at = None

    def _is_suppressed(
        self,
        db: Session,
        user: UserProfile,
        normalized_key: str,
        *,
        source_type: str | None,
        source_id: str | None,
    ) -> bool:
        if not source_id:
            return False
        key = self._suppression_key(normalized_key, source_type, source_id)
        row = db.scalar(
            select(MemorySuppression).where(
                MemorySuppression.user_id == user.id,
                MemorySuppression.suppression_key == key,
                MemorySuppression.active.is_(True),
            )
        )
        if row is None:
            return False
        if row.expires_at is not None:
            expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
            return expires > utcnow()
        return True

    @staticmethod
    def _evidence_exists(
        db: Session,
        memory_id: str,
        *,
        source_type: str,
        source_id: str | None,
        evidence_kind: str,
        direction: str,
    ) -> bool:
        if not source_id:
            return False
        return db.scalar(
            select(MemoryEvidence.id).where(
                MemoryEvidence.memory_id == memory_id,
                MemoryEvidence.source_type == source_type,
                MemoryEvidence.source_id == source_id,
                MemoryEvidence.evidence_kind == evidence_kind,
                MemoryEvidence.direction == direction,
            )
        ) is not None

    def record_outcome(self, db: Session, user: UserProfile, payload: RecommendationOutcomeCreate) -> RecommendationOutcomeRead:
        from app.recommendations.service import record_outcome

        return record_outcome(db, user, payload)

    def list_outcomes(self, db: Session, user: UserProfile, limit: int = 50) -> list[RecommendationOutcomeRead]:
        from app.recommendations.service import list_outcomes

        return list_outcomes(db, user, limit=limit)

    def _handle_contradiction(self, db: Session, user: UserProfile, existing: MemoryItem, candidate: MemoryCandidate, **kwargs) -> MemoryItem:
        if kwargs.get("source_id"):
            prior = db.scalar(
                select(MemoryItem)
                .join(MemoryEvidence, MemoryEvidence.memory_id == MemoryItem.id)
                .where(
                    MemoryItem.user_id == user.id,
                    MemoryItem.supersedes_memory_id == existing.id,
                    MemoryEvidence.source_type == kwargs["source_type"],
                    MemoryEvidence.source_id == kwargs["source_id"],
                    MemoryEvidence.direction == "supports",
                )
            )
            if prior is not None:
                return prior
        now = utcnow()
        if existing.pinned:
            memory = MemoryItem(
                user_id=user.id,
                memory_type=candidate.memory_type,
                domain=candidate.domain,
                content=candidate.content.strip(),
                normalized_key=normalize_key(candidate.normalized_key),
                polarity=candidate.polarity,
                confidence=0.35,
                importance=candidate.importance,
                status="uncertain",
                pinned=False,
                user_confirmed=False,
                source_kind=kwargs["source_kind"],
                first_observed_at=now,
                last_observed_at=now,
                valid_from=now,
                supersedes_memory_id=existing.id,
                metadata_json={"contradicts_pinned_memory": existing.id},
            )
        else:
            existing.status = "contradicted"
            existing.valid_until = now
            existing.version += 1
            memory = MemoryItem(
                user_id=user.id,
                memory_type=candidate.memory_type,
                domain=candidate.domain,
                content=candidate.content.strip(),
                normalized_key=normalize_key(candidate.normalized_key),
                polarity=candidate.polarity,
                confidence=0.5,
                importance=candidate.importance,
                status="candidate",
                pinned=False,
                user_confirmed=kwargs["user_confirmed"],
                source_kind=kwargs["source_kind"],
                first_observed_at=now,
                last_observed_at=now,
                last_confirmed_at=now if kwargs["user_confirmed"] else None,
                valid_from=now,
                supersedes_memory_id=existing.id,
            )
        db.add(memory)
        db.flush()
        self._add_evidence(
            db,
            memory,
            source_type=kwargs["source_type"],
            source_id=kwargs["source_id"],
            evidence_kind=kwargs["evidence_kind"],
            direction="supports",
            weight=1.0 if kwargs["user_confirmed"] else 0.72,
            excerpt=candidate.content,
        )
        self._add_evidence(
            db,
            existing,
            source_type=kwargs["source_type"],
            source_id=kwargs["source_id"],
            evidence_kind=kwargs["evidence_kind"],
            direction="contradicts",
            weight=0.8,
            excerpt=candidate.content,
        )
        self._recompute(db, memory, contradictory=existing.pinned)
        if not existing.pinned:
            self._recompute(db, existing)
            existing.status = "contradicted"
        self.embeddings.try_attach(db, user, memory, memory.content, request_id=kwargs["request_id"])
        append_event(
            db,
            user,
            event_type="memory.contradiction_detected",
            aggregate_type="memory",
            aggregate_id=memory.id,
            payload={"memory_id": memory.id, "contradicts_memory_id": existing.id, "pinned_memory_protected": existing.pinned},
            outbox=False,
            increment_world_revision=False,
        )
        if memory.status == "uncertain":
            from app.review.service import ReviewQueueService
            ReviewQueueService().enqueue_memory_candidate(db, user, memory.id)
        return memory

    def _add_evidence(self, db: Session, memory: MemoryItem, **values) -> None:
        existing = None
        source_id = values.get("source_id")
        if source_id:
            existing = db.scalar(
                select(MemoryEvidence).where(
                    MemoryEvidence.memory_id == memory.id,
                    MemoryEvidence.source_type == values["source_type"],
                    MemoryEvidence.source_id == source_id,
                    MemoryEvidence.evidence_kind == values["evidence_kind"],
                    MemoryEvidence.direction == values["direction"],
                )
            )
        if existing is None:
            db.add(MemoryEvidence(memory_id=memory.id, user_id=memory.user_id, observed_at=utcnow(), metadata_json={}, **values))
            db.flush()

    def _recompute(self, db: Session, memory: MemoryItem, *, contradictory: bool = False) -> None:
        evidence = list(db.scalars(select(MemoryEvidence).where(MemoryEvidence.memory_id == memory.id)).all())
        memory.confidence = evidence_confidence(evidence, pinned=memory.pinned, user_confirmed=memory.user_confirmed)
        memory.status = status_for(memory.confidence, user_confirmed=memory.user_confirmed, contradictory=contradictory)

    @staticmethod
    def _evidence_count(db: Session, memory_id: str) -> int:
        return int(db.scalar(select(func.count(MemoryEvidence.id)).where(MemoryEvidence.memory_id == memory_id)) or 0)
