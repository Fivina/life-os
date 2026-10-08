from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ProspectiveThread, UserProfile
from app.movies.prospective import evaluate_movie_thread


def run_due_movie_checks(db: Session, user: UserProfile, *, now: datetime | None = None, limit: int = 50) -> dict[str, int]:
    when = now or datetime.now(UTC)
    rows = list(db.scalars(select(ProspectiveThread).where(
        ProspectiveThread.user_id == user.id,
        ProspectiveThread.domain == "leisure",
        ProspectiveThread.status == "OPEN",
        ProspectiveThread.intent == "WATCH_WHEN_AVAILABLE",
    ).order_by(ProspectiveThread.earliest_relevance.asc()).limit(max(1, min(limit, 100)))))
    checked = eligible = queued = 0
    for row in rows:
        next_check_raw = (row.metadata_json or {}).get("next_check_at")
        if next_check_raw:
            next_check = datetime.fromisoformat(next_check_raw)
            if (next_check.replace(tzinfo=UTC) if next_check.tzinfo is None else next_check) > when:
                continue
        result = evaluate_movie_thread(db, user, row, now=when)
        checked += 1
        eligible += int(result.eligible)
        queued += int(result.attention_item_id is not None)
        interval = timedelta(days=1 if result.eligible else 14)
        row.metadata_json = {**(row.metadata_json or {}), "next_check_at": (when + interval).isoformat(), "last_check_reason": result.reason_code}
    return {"checked": checked, "eligible": eligible, "queued": queued}
