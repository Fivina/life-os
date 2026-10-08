from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MemoryItem, MemoryLearningBridgeRun, PatternEvidence, RecommendationOutcome, UserProfile
from app.memory.schemas import LearningBridgeRead


class LearningBridgeService:
    """Creates a bounded cross-system snapshot without collapsing source authority."""

    def refresh(
        self,
        db: Session,
        user: UserProfile,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> LearningBridgeRead:
        end = period_end or datetime.now(UTC)
        start = period_start or (end - timedelta(days=7))
        existing = db.scalar(
            select(MemoryLearningBridgeRun).where(
                MemoryLearningBridgeRun.user_id == user.id,
                MemoryLearningBridgeRun.period_start == start,
                MemoryLearningBridgeRun.period_end == end,
            )
        )
        if existing is not None:
            return LearningBridgeRead.model_validate(existing)
        memories = list(
            db.scalars(
                select(MemoryItem)
                .where(MemoryItem.user_id == user.id, MemoryItem.updated_at >= start, MemoryItem.updated_at < end)
                .order_by(MemoryItem.updated_at.desc())
                .limit(50)
            ).all()
        )
        patterns = list(
            db.scalars(
                select(PatternEvidence)
                .where(PatternEvidence.user_id == user.id, PatternEvidence.last_updated >= start, PatternEvidence.last_updated < end)
                .order_by(PatternEvidence.last_updated.desc())
                .limit(50)
            ).all()
        )
        outcomes = list(
            db.scalars(
                select(RecommendationOutcome)
                .where(RecommendationOutcome.user_id == user.id, RecommendationOutcome.observed_at >= start, RecommendationOutcome.observed_at < end)
                .order_by(RecommendationOutcome.observed_at.desc())
                .limit(50)
            ).all()
        )
        row = MemoryLearningBridgeRun(
            user_id=user.id,
            period_start=start,
            period_end=end,
            status="completed",
            memory_change_count=len(memories),
            pattern_change_count=len(patterns),
            recommendation_outcome_count=len(outcomes),
            snapshot_json={
                "semantic_memory_changes": [
                    {"id": item.id, "domain": item.domain, "type": item.memory_type, "status": item.status, "pinned": item.pinned}
                    for item in memories[:20]
                ],
                "behavioral_pattern_changes": [
                    {"id": item.id, "type": item.pattern_type, "status": item.status, "confidence": item.confidence, "evidence_n": item.evidence_n}
                    for item in patterns[:20]
                ],
                "recommendation_outcomes": [
                    {"id": item.id, "domain": item.domain, "type": item.recommendation_type, "outcome": item.outcome, "accepted": item.accepted}
                    for item in outcomes[:20]
                ],
                "authority_boundary": "Semantic memory, behavioral patterns, and recommendation outcomes remain separate evidence systems.",
            },
        )
        db.add(row)
        db.flush()
        return LearningBridgeRead.model_validate(row)

    def refresh_due(self, db: Session) -> int:
        end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        count = 0
        for user in db.scalars(select(UserProfile)).all():
            existing = db.scalar(
                select(MemoryLearningBridgeRun.id).where(
                    MemoryLearningBridgeRun.user_id == user.id,
                    MemoryLearningBridgeRun.period_start == start,
                    MemoryLearningBridgeRun.period_end == end,
                )
            )
            if existing is not None:
                continue
            self.refresh(db, user, period_start=start, period_end=end)
            count += 1
        return count
