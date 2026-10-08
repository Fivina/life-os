from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import OutboxEvent, UserProfile
from app.domains.base import DomainRefreshResult


logger = logging.getLogger("life_os.domains")


class DomainRefreshService:
    """Refresh domain needs independently so one optional domain cannot stop planning."""

    def refresh_user(
        self,
        db: Session,
        user: UserProfile,
        *,
        horizon_start: date | None = None,
        horizon_end: date | None = None,
    ) -> list[DomainRefreshResult]:
        start = horizon_start or date.today()
        end = horizon_end or start + timedelta(days=get_settings().planner_horizon_days - 1)
        handlers = [
            ("learning", self._learning),
            ("fitness", self._fitness),
            ("home", self._home),
            ("goals", self._goals),
        ]
        results: list[DomainRefreshResult] = []
        for name, handler in handlers:
            try:
                with db.begin_nested():
                    result = handler(db, user, start, end)
                results.append(result)
            except Exception as exc:
                logger.exception("domain_refresh_failed", extra={"domain": name, "user_id": user.id})
                results.append(DomainRefreshResult(name, 0, 0, 0, 0, (str(exc),)))
        return results

    @staticmethod
    def _learning(db: Session, user: UserProfile, start: date, end: date) -> DomainRefreshResult:
        from app.domains.learning.service import planning_requirements, sync_candidate_actions

        requirements = planning_requirements(db, user, horizon_start=start, horizon_end=end)
        sync_candidate_actions(db, user, horizon_start=start, horizon_end=end)
        return DomainRefreshResult("learning", len(requirements), 0, len(requirements), 0)

    @staticmethod
    def _fitness(db: Session, user: UserProfile, start: date, end: date) -> DomainRefreshResult:
        from app.domains.fitness.service import planning_requirements, sync_candidate_actions

        requirements = planning_requirements(db, user, horizon_start=start, horizon_end=end)
        sync_candidate_actions(db, user, horizon_start=start, horizon_end=end)
        return DomainRefreshResult("fitness", len(requirements), 0, len(requirements), 0)

    @staticmethod
    def _home(db: Session, user: UserProfile, start: date, end: date) -> DomainRefreshResult:
        from app.domains.home.service import refresh_actions

        return refresh_actions(db, user, horizon_start=start, horizon_end=end)

    @staticmethod
    def _goals(db: Session, user: UserProfile, start: date, end: date) -> DomainRefreshResult:
        from app.domains.goals.service import refresh_all_trajectories

        trajectories = refresh_all_trajectories(db, user)
        return DomainRefreshResult("goals", len(trajectories), 0, len(trajectories), 0)

    def refresh_all_users(self, db: Session) -> int:
        from sqlalchemy import select

        count = 0
        for user in db.scalars(select(UserProfile).order_by(UserProfile.id)).all():
            self.refresh_user(db, user)
            count += 1
        return count


class DomainOutboxHandler:
    """Event-driven requirement refresh layered beside existing delivery handlers."""

    relevant_prefixes = (
        "learning.", "fitness.", "home.", "goal.", "milestone.", "weekly_focus.",
        "inventory.", "kitchen.", "meal.", "receipt.", "shopping.", "finance.", "planning.", "plan.",
    )

    strategic_events = {
        "learning.study_session.completed",
        "learning.exam.updated",
        "learning.topic.updated",
        "learning.readiness.updated",
        "learning.risk.changed",
        "learning.study.skipped",
        "plan.block.missed",
        "planning.debt.created",
        "plan.replanned",
    }

    def __init__(self, db: Session, downstream=None) -> None:
        self.db = db
        self.downstream = downstream

    def publish(self, event: OutboxEvent) -> None:
        if self.downstream is not None:
            self.downstream.publish(event)
        if not event.event_type.startswith(self.relevant_prefixes) or event.event_type.endswith("requirements.reconciled"):
            return
        user = self.db.get(UserProfile, event.user_id)
        if user is not None:
            if event.event_type.startswith(("inventory.", "kitchen.", "meal.", "receipt.", "shopping.")):
                from app.domains.kitchen.service import sync_shopping_actions

                sync_shopping_actions(self.db, user)
            elif event.event_type.startswith("finance."):
                from app.domains.finance.service import refresh_recurring

                refresh_recurring(self.db, user)
            else:
                DomainRefreshService().refresh_user(self.db, user)
            if event.event_type in self.strategic_events:
                from app.strategy.service import PlanProposalService

                PlanProposalService().evaluate_relevant_event(
                    self.db,
                    user,
                    event_type=event.event_type,
                    payload=event.payload or {},
                )
