from __future__ import annotations

from datetime import date, datetime
from sqlalchemy.orm import Session
from app.database.models import PlanBlock, UserProfile


class HomeDomain:
    name = "home"

    def get_current_state(self, db: Session, user: UserProfile) -> dict:
        from app.domains.home.service import overview
        return overview(db, user).model_dump(mode="json")

    def get_requirements(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date):
        from app.domains.home.service import requirements
        return requirements(db, user, horizon_start=horizon_start, horizon_end=horizon_end)

    def refresh_actions(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date):
        from app.domains.home.service import refresh_actions
        return refresh_actions(db, user, horizon_start=horizon_start, horizon_end=horizon_end)

    def get_constraints(self, db: Session, user: UserProfile, *, horizon_start: date, horizon_end: date) -> list[dict]:
        return []

    def apply_execution_outcome(self, db: Session, user: UserProfile, block: PlanBlock, outcome: str, actual_minutes: int, occurred_at: datetime):
        if outcome != "completed":
            return None
        from app.domains.home.service import complete_plan_block
        return complete_plan_block(db, user, block, occurred_at)

    def get_summary_for_context(self, db: Session, user: UserProfile) -> dict:
        return self.get_current_state(db, user)

    def get_risk_state(self, db: Session, user: UserProfile) -> dict:
        state = self.get_current_state(db, user)
        return {"overdue_count": sum(1 for item in state.get("due", []) if item.get("due_status") == "overdue")}
