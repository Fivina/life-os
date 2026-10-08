from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PatternEvidence, UserProfile


def time_bucket(value: datetime) -> str:
    if 5 <= value.hour < 12:
        return "morning"
    if 12 <= value.hour < 17:
        return "afternoon"
    if 17 <= value.hour < 22:
        return "evening"
    return "night"


@dataclass(frozen=True)
class PlanningBehaviorProfile:
    patterns: list[dict[str, Any]]

    @classmethod
    def load(cls, db: Session, user: UserProfile) -> "PlanningBehaviorProfile":
        rows = list(
            db.scalars(
                select(PatternEvidence)
                .where(PatternEvidence.user_id == user.id)
                .order_by(PatternEvidence.last_updated.desc())
            ).all()
        )
        return cls(
            patterns=[
                {
                    "id": row.id,
                    "type": row.pattern_type,
                    "scope": row.scope or {},
                    "confidence": row.confidence,
                    "evidence_n": row.evidence_n,
                    "weighted_support": row.weighted_support,
                    "status": row.status,
                }
                for row in rows
            ]
        )

    def as_json(self) -> list[dict[str, Any]]:
        return self.patterns

