from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MemoryItem, UserProfile
from app.memory.schemas import MemoryCandidate


MergeAction = Literal["create", "reinforce", "conflict"]


@dataclass(frozen=True)
class MemoryMergeDecision:
    action: MergeAction
    existing: MemoryItem | None = None
    similarity: float | None = None
    matched_by: Literal["normalized_key", "embedding"] | None = None


def cosine_similarity(left, right) -> float:
    if left is None or right is None:
        return 0.0
    a, b = list(left), list(right)
    if not a or len(a) != len(b):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in a)) * math.sqrt(sum(value * value for value in b))
    return sum(x * y for x, y in zip(a, b)) / denominator if denominator else 0.0


class MemoryMergeService:
    """Finds merge targets; callers execute the validated persistence decision."""

    def exact(self, db: Session, user: UserProfile, candidate: MemoryCandidate, normalized_key: str) -> MemoryMergeDecision:
        existing = db.scalar(
            select(MemoryItem).where(
                MemoryItem.user_id == user.id,
                MemoryItem.memory_type == candidate.memory_type,
                MemoryItem.domain == candidate.domain,
                MemoryItem.normalized_key == normalized_key,
                MemoryItem.deleted_at.is_(None),
                MemoryItem.status.in_(["candidate", "active", "uncertain"]),
            )
        )
        if existing is None:
            return MemoryMergeDecision(action="create")
        return MemoryMergeDecision(
            action=self._relation(candidate, existing),
            existing=existing,
            similarity=1.0,
            matched_by="normalized_key",
        )

    def semantic(
        self,
        db: Session,
        user: UserProfile,
        candidate: MemoryCandidate,
        vector: list[float],
        *,
        threshold: float,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> MemoryMergeDecision:
        candidates = list(
            db.scalars(
                select(MemoryItem).where(
                    MemoryItem.user_id == user.id,
                    MemoryItem.memory_type == candidate.memory_type,
                    MemoryItem.domain == candidate.domain,
                    MemoryItem.embedding_vector.is_not(None),
                    MemoryItem.embedding_provider == embedding_provider,
                    MemoryItem.embedding_model == embedding_model,
                    MemoryItem.embedding_dimension == embedding_dimension,
                    MemoryItem.deleted_at.is_(None),
                    MemoryItem.status.in_(["candidate", "active", "uncertain"]),
                ).limit(200)
            ).all()
        )
        existing = max(candidates, key=lambda item: cosine_similarity(vector, item.embedding_vector), default=None)
        similarity = cosine_similarity(vector, existing.embedding_vector) if existing is not None else 0.0
        if existing is None or similarity < threshold:
            return MemoryMergeDecision(action="create", similarity=similarity)
        return MemoryMergeDecision(
            action=self._relation(candidate, existing),
            existing=existing,
            similarity=similarity,
            matched_by="embedding",
        )

    @staticmethod
    def _relation(candidate: MemoryCandidate, existing: MemoryItem) -> MergeAction:
        if candidate.polarity != 0 and existing.polarity not in {0, candidate.polarity}:
            return "conflict"
        return "reinforce"

