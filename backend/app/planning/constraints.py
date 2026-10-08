from __future__ import annotations

import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Constraint, MemoryItem, UserProfile
from app.planning.types import PlanningConstraint


WEEKDAYS = {name: index for index, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}


def _memory_constraint(memory: MemoryItem, planning_day, timezone_name: str) -> PlanningConstraint | None:
    metadata = memory.metadata_json or {}
    typed = metadata.get("planning_preference")
    if isinstance(typed, dict) and typed.get("type"):
        return PlanningConstraint(
            name=typed.get("name") or memory.content[:160],
            constraint_type=str(typed["type"]),
            payload=typed,
            strength=str(typed.get("strength") or "soft"),
            provenance="pinned_memory",
            domain=typed.get("domain"),
            penalty=float(typed.get("penalty") or 14),
        )

    text = memory.content.strip().lower()
    weekday = next((value for key, value in WEEKDAYS.items() if key in text), None)
    if weekday is not None and planning_day.weekday() != weekday:
        return None
    if weekday is not None and any(token in text for token in ("unavailable", "personal time", "never schedule", "do not schedule")):
        zone = ZoneInfo(timezone_name)
        if "evening" in text:
            start, end = time(18, 0), time(23, 59)
        elif "morning" in text:
            start, end = time(0, 0), time(12, 0)
        else:
            start, end = time(0, 0), time(23, 59)
        return PlanningConstraint(
            name=memory.content,
            constraint_type="unavailable_window",
            strength="hard",
            provenance="pinned_memory",
            starts_at=datetime.combine(planning_day, start, tzinfo=zone),
            ends_at=datetime.combine(planning_day, end, tzinfo=zone),
            penalty=100,
            payload={"memory_id": memory.id, "recognized_rule": "weekday_unavailable"},
        )

    match = re.search(r"(?:avoid|no|never).*?(?:work|meeting|schedule).*?after\s+(\d{1,2})(?::(\d{2}))?", text)
    if match:
        zone = ZoneInfo(timezone_name)
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        strength = "hard" if "never" in text or text.startswith("no ") else "soft"
        return PlanningConstraint(
            name=memory.content,
            constraint_type="unavailable_window",
            strength=strength,
            provenance="pinned_memory",
            starts_at=datetime.combine(planning_day, time(hour, minute), tzinfo=zone),
            ends_at=datetime.combine(planning_day, time(23, 59), tzinfo=zone),
            penalty=100 if strength == "hard" else 16,
            payload={"memory_id": memory.id, "recognized_rule": "work_after"},
        )
    if "prefer" in text and any(token in text for token in ("morning", "afternoon", "evening")):
        bucket = next(token for token in ("morning", "afternoon", "evening") if token in text)
        return PlanningConstraint(
            name=memory.content,
            constraint_type="preferred_time_bucket",
            strength="soft",
            provenance="pinned_memory",
            domain=memory.domain if memory.domain != "general" else None,
            penalty=10,
            payload={"memory_id": memory.id, "bucket": bucket, "recognized_rule": "preferred_time_bucket"},
        )
    return None


class PlanningConstraintResolver:
    def resolve(self, db: Session, user: UserProfile, *, planning_day, timezone_name: str) -> list[PlanningConstraint]:
        resolved: list[PlanningConstraint] = []
        rows = list(db.scalars(select(Constraint).where(Constraint.user_id == user.id, Constraint.is_active.is_(True))).all())
        for row in rows:
            resolved.append(
                PlanningConstraint(
                    name=row.name,
                    constraint_type=row.constraint_type,
                    payload=row.payload or {},
                    strength=row.strength,
                    provenance=row.provenance,
                    domain=row.domain,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    penalty=row.penalty,
                )
            )
        memories = list(
            db.scalars(
                select(MemoryItem).where(
                    MemoryItem.user_id == user.id,
                    MemoryItem.pinned.is_(True),
                    MemoryItem.status.in_(["active", "confirmed"]),
                    MemoryItem.deleted_at.is_(None),
                )
            ).all()
        )
        for memory in memories:
            item = _memory_constraint(memory, planning_day, timezone_name)
            if item is not None:
                resolved.append(item)
        return resolved

