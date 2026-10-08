from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Action, UserProfile
from app.domains.base import DomainRefreshResult, PlanningRequirement
from app.events.service import append_event


GENERATION_VERSION = "domain-intelligence-v1.4"


@dataclass
class _Counts:
    created: int = 0
    updated: int = 0
    archived: int = 0


def _same(left, right) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        left = left.replace(tzinfo=UTC) if left.tzinfo is None else left.astimezone(UTC)
        right = right.replace(tzinfo=UTC) if right.tzinfo is None else right.astimezone(UTC)
    return left == right


def _values(requirement: PlanningRequirement, variant) -> dict:
    metadata = {
        **requirement.metadata,
        "requirement_key": requirement.key,
        "source_entity_type": requirement.source_entity_type,
        "source_entity_id": requirement.source_entity_id,
        "generated_reason": requirement.reason,
        "generation_version": GENERATION_VERSION,
    }
    suffix = variant.title_suffix or variant.variant_type
    return {
        "domain": requirement.domain,
        "title": f"{requirement.title} ({suffix})",
        "description": requirement.reason,
        "level": requirement.level,
        "earliest_start": requirement.earliest_start,
        "latest_start": requirement.latest_start,
        "deadline": requirement.deadline,
        "location": requirement.location,
        "context": requirement.context,
        "status": "active",
        "estimated_minutes": variant.duration_minutes,
        "completed_minutes": 0,
        "duration_min_minutes": variant.minimum_minutes,
        "duration_max_minutes": variant.maximum_minutes,
        "metadata_json": metadata,
        "candidate_group_id": requirement.key,
        "variant_type": variant.variant_type,
        "variant_rank": variant.rank,
        "mutually_exclusive": True,
        "variant_quality": variant.quality,
        "requirement_key": requirement.key,
        "source_entity_type": requirement.source_entity_type,
        "source_entity_id": requirement.source_entity_id,
        "goal_id": requirement.goal_id,
        "trajectory_id": requirement.trajectory_id,
        "generated_reason": requirement.reason,
        "generation_version": GENERATION_VERSION,
        "planning_priority": max(0, min(100, requirement.priority)),
    }


def reconcile_requirements(db: Session, user: UserProfile, domain: str, requirements: Iterable[PlanningRequirement]) -> DomainRefreshResult:
    requirements = list(requirements)
    keys = {item.key for item in requirements}
    existing = list(
        db.scalars(
            select(Action).where(
                Action.user_id == user.id,
                Action.domain == domain,
                Action.generation_version == GENERATION_VERSION,
            )
        ).all()
    )
    by_identity = {}
    for item in sorted(existing, key=lambda row: (row.status != "active", row.created_at), reverse=False):
        if item.requirement_key:
            by_identity.setdefault((item.requirement_key, item.variant_type), item)
    completed_keys = {item.requirement_key for item in existing if item.requirement_key and item.status == "completed"}
    counts = _Counts()

    for requirement in requirements:
        if requirement.key in completed_keys:
            continue
        desired_variants = {item.variant_type for item in requirement.variants}
        for variant in requirement.variants:
            values = _values(requirement, variant)
            action = by_identity.get((requirement.key, variant.variant_type))
            if action is None or action.status in {"cancelled", "archived", "missed"}:
                db.add(Action(user_id=user.id, **values))
                counts.created += 1
                continue
            changed = False
            for name, value in values.items():
                if name == "completed_minutes":
                    continue
                if not _same(getattr(action, name), value):
                    setattr(action, name, value)
                    changed = True
            if changed:
                action.version += 1
                counts.updated += 1
        for action in existing:
            if action.requirement_key == requirement.key and action.status == "active" and action.variant_type not in desired_variants:
                action.status = "archived"
                action.version += 1
                counts.archived += 1

    for action in existing:
        if action.status == "active" and action.requirement_key and action.requirement_key not in keys:
            action.status = "archived"
            action.version += 1
            counts.archived += 1

    changed = counts.created + counts.updated + counts.archived
    if changed:
        db.flush()
        append_event(
            db,
            user,
            event_type=f"{domain}.requirements.reconciled",
            aggregate_type=f"{domain}_requirements",
            aggregate_id=user.id,
            payload={
                "domain": domain,
                "requirement_count": len(requirements),
                "created": counts.created,
                "updated": counts.updated,
                "archived": counts.archived,
            },
        )
    return DomainRefreshResult(domain, len(requirements), counts.created, counts.updated, counts.archived)
