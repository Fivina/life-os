from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import UserProfile
from app.planning.schemas import PlanGenerateRequest
from app.planning.service import generate_plan, get_current_plan


class MorningPlanner:
    """Idempotent user/date-scoped plan creation for worker and first access."""

    def ensure(self, db: Session, user: UserProfile, *, timezone_name: str = "Europe/Berlin", now: datetime | None = None):
        zone = ZoneInfo(timezone_name)
        local_now = now.astimezone(zone) if now and now.tzinfo else now.replace(tzinfo=zone) if now else datetime.now(zone)
        existing = get_current_plan(db, user, local_now.date())
        if existing is not None:
            return existing, False
        plan = generate_plan(
            db,
            user,
            PlanGenerateRequest(planning_date=local_now.date(), timezone=timezone_name, expected_world_revision=user.world_revision),
            replan_reason="MORNING_AUTOMATION",
            planning_now=local_now,
        )
        return plan, True

    def run_due(self, db: Session, *, timezone_name: str = "Europe/Berlin", now: datetime | None = None) -> int:
        zone = ZoneInfo(timezone_name)
        local_now = now.astimezone(zone) if now and now.tzinfo else now.replace(tzinfo=zone) if now else datetime.now(zone)
        if local_now.hour < get_settings().planner_morning_hour:
            return 0
        generated = 0
        for user in db.scalars(select(UserProfile).order_by(UserProfile.id)).all():
            _, created = self.ensure(db, user, timezone_name=timezone_name, now=local_now)
            generated += 1 if created else 0
        return generated
