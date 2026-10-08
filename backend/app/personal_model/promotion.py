from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PersonalModelVersion, UserProfile
from app.personal_model.confidence import MIN_EVIDENCE, PROMOTION_CONFIDENCE, influence_allowed


def next_model_version(db: Session, user: UserProfile, model_type: str) -> int:
    latest = db.scalar(
        select(PersonalModelVersion.version)
        .where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.model_type == model_type)
        .order_by(PersonalModelVersion.version.desc())
        .limit(1)
    )
    return int(latest or 0) + 1


def active_model(db: Session, user: UserProfile, model_type: str) -> PersonalModelVersion | None:
    return db.scalar(
        select(PersonalModelVersion)
        .where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.model_type == model_type, PersonalModelVersion.status == "ACTIVE")
        .order_by(PersonalModelVersion.promoted_at.desc().nulls_last(), PersonalModelVersion.created_at.desc())
        .limit(1)
    )


def promotion_decision(model_type: str, evidence_n: int, confidence: float, metrics: dict, baseline_metrics: dict) -> tuple[str, str]:
    if evidence_n < MIN_EVIDENCE[model_type]:
        return "REJECTED", f"INSUFFICIENT_EVIDENCE: requires {MIN_EVIDENCE[model_type]}, found {evidence_n}."
    if confidence < PROMOTION_CONFIDENCE[model_type]:
        return "REJECTED", f"LOW_CONFIDENCE: requires {PROMOTION_CONFIDENCE[model_type]:.2f}, found {confidence:.2f}."
    candidate_loss = metrics.get("loss")
    baseline_loss = baseline_metrics.get("loss")
    if candidate_loss is not None and baseline_loss is not None and candidate_loss > baseline_loss:
        return "REJECTED", "BASELINE_BETTER: candidate calibration is worse than baseline."
    if not influence_allowed(model_type, confidence, evidence_n):
        return "REJECTED", "GUARD_BLOCKED: influence guard did not pass."
    return "ACTIVE", "PROMOTED: sufficient evidence, confidence, and baseline comparison."


def apply_promotion(db: Session, user: UserProfile, candidate: PersonalModelVersion) -> PersonalModelVersion:
    status, reason = promotion_decision(candidate.model_type, candidate.evidence_n, candidate.confidence, candidate.metrics, candidate.baseline_metrics)
    candidate.status = status
    candidate.promotion_reason = reason
    if status == "ACTIVE":
        previous = active_model(db, user, candidate.model_type)
        if previous and previous.id != candidate.id:
            previous.status = "RETIRED"
            previous.version += 1
            candidate.supersedes_model_version_id = previous.id
        candidate.promoted_at = datetime.now(UTC)
    db.flush()
    return candidate
