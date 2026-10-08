from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.database.models import PlanBlock, UserProfile


@dataclass(frozen=True)
class ActionVariantSpec:
    variant_type: str
    duration_minutes: int
    minimum_minutes: int
    maximum_minutes: int
    rank: int
    quality: float = 1.0
    title_suffix: str | None = None


@dataclass(frozen=True)
class PlanningRequirement:
    key: str
    domain: str
    title: str
    source_entity_type: str
    source_entity_id: str
    reason: str
    deadline: datetime | None
    variants: tuple[ActionVariantSpec, ...]
    level: str = "maintenance"
    priority: int = 50
    earliest_start: datetime | None = None
    latest_start: datetime | None = None
    location: str | None = None
    context: str | None = None
    goal_id: str | None = None
    trajectory_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainRefreshResult:
    domain: str
    requirement_count: int
    created: int
    updated: int
    archived: int
    errors: tuple[str, ...] = ()


class DomainPlanningContract(Protocol):
    """Integration boundary: domains own truth and needs, Planner owns placement."""

    name: str

    def get_current_state(self, db: Session, user: UserProfile) -> dict[str, Any]: ...

    def get_requirements(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> list[PlanningRequirement]: ...

    def refresh_actions(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> DomainRefreshResult: ...

    def get_constraints(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> list[dict[str, Any]]: ...

    def apply_execution_outcome(self, db: Session, user: UserProfile, block: PlanBlock, outcome: str, actual_minutes: int, occurred_at: datetime) -> Any: ...

    def get_summary_for_context(self, db: Session, user: UserProfile) -> dict[str, Any]: ...

    def get_risk_state(self, db: Session, user: UserProfile) -> dict[str, Any]: ...
