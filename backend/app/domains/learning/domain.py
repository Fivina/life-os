from __future__ import annotations

from datetime import date, datetime
from sqlalchemy.orm import Session
from app.database.models import PlanBlock, UserProfile


class LearningDomain:
    name = "learning"

    def get_current_state(self, db: Session, user: UserProfile) -> dict:
        from app.domains.learning.service import status_summary
        return status_summary(db, user).model_dump(mode="json")

    def get_requirements(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date):
        from app.domains.learning.service import planning_requirements
        return planning_requirements(db, user, horizon_start=horizon_start, horizon_end=horizon_end)

    def refresh_actions(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date):
        from app.domains.learning.service import sync_candidate_actions
        return sync_candidate_actions(db, user, horizon_start=horizon_start, horizon_end=horizon_end)

    def get_constraints(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> list[dict]:
        return []

    def apply_execution_outcome(self, db: Session, user: UserProfile, block: PlanBlock, outcome: str, actual_minutes: int, occurred_at: datetime):
        from app.domains.learning.service import complete_learning_plan_block
        return complete_learning_plan_block(db, user, block, actual_minutes, occurred_at, completion_status=outcome)

    def get_summary_for_context(self, db: Session, user: UserProfile) -> dict:
        from app.domains.learning.service import learning_context
        return learning_context(db, user).model_dump(mode="json")

    def get_risk_state(self, db: Session, user: UserProfile) -> dict:
        active = self.get_current_state(db, user).get("active_exam") or {}
        return active.get("trajectory") or {}
