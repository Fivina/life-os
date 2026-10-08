from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PatternEvidence, UserProfile
from app.personal_model.schemas import PatternEvidenceRead


def _matches_domain(pattern: PatternEvidence, domain: str | None) -> bool:
    if domain is None:
        return True
    scope = pattern.scope or {}
    scoped_domain = scope.get("domain")
    if scoped_domain is not None:
        return scoped_domain in {domain, "general", "global"}
    key = str(scope.get("key") or "")
    if not key:
        return True
    return key.startswith(f"{domain}|") or key.startswith(f"domain:{domain}") or key.startswith("global")


class PatternRetrievalService:
    """Bounded read interface over active, uncorrected Personal Learning evidence."""

    def relevant(
        self,
        db: Session,
        user: UserProfile,
        *,
        domain: str | None = None,
        limit: int = 6,
    ) -> list[PatternEvidenceRead]:
        bounded = min(max(limit, 1), 20)
        rows = list(
            db.scalars(
                select(PatternEvidence)
                .where(PatternEvidence.user_id == user.id, PatternEvidence.status == "ACTIVE")
                .order_by(PatternEvidence.confidence.desc(), PatternEvidence.evidence_n.desc(), PatternEvidence.last_updated.desc())
                .limit(100)
            ).all()
        )
        return [PatternEvidenceRead.model_validate(row) for row in rows if _matches_domain(row, domain)][:bounded]
