from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Event, UserProfile, WorldRevision
from app.realtime.schemas import RealtimeCatchup, RealtimeStateEvent, RealtimeStateEventType


DOMAIN_INVALIDATIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("inventory.", "kitchen.", "meal.", "recipe.", "receipt."), ("inventory", "kitchen", "shopping_list", "meal_plans", "cooking_session")),
    (("shopping.", "kitchen.shopping"), ("shopping_list", "shopping_needs", "kitchen")),
    (("finance.",), ("finance_summary",)),
    (("plan.", "planning."), ("current_plan", "calendar", "plan_horizon")),
    (("strategy.proposal",), ("plan_proposals", "attention_items")),
    (("workspace.",), ("active_workspace", "global_workspace")),
    (("conversation.",), ("conversations",)),
    (("learning.", "study."), ("learning_status", "calendar", "plan_proposals")),
    (("fitness.", "workout."), ("fitness_status", "calendar")),
    (("state.", "check_in."), ("latest_state", "global_workspace")),
    (("goal.", "milestone.", "weekly_focus."), ("goals", "current_plan")),
    (("attention.",), ("attention_items",)),
    (("memory.", "personal_model."), ("personal_model", "global_workspace")),
    (("notebook.",), ("notebook_entries",)),
    (("standing_rule.", "fixture."), ("standing_calendar_rules", "calendar", "current_plan")),
    (("movie.", "leisure."), ("movies", "movie_watchlist", "movie_history", "movie_recommendations", "leisure_trajectory")),
    (("opportunity.", "social."), ("opportunities", "opportunity_recommendations", "opportunity_sources", "social_trajectory", "social_activities")),
    (("commitment.",), ("calendar", "current_plan")),
    (("quick_capture.",), ("quick_captures", "review_queue")),
    (("review_item.",), ("review_queue", "quick_captures")),
    (("intelligence_settings.",), ("intelligence_settings", "assistant_policy")),
)


def invalidations_for(event: Event) -> tuple[str, ...]:
    keys: list[str] = []
    for prefixes, invalidations in DOMAIN_INVALIDATIONS:
        if any(event.event_type.startswith(prefix) for prefix in prefixes):
            keys.extend(invalidations)
    conversation_id = event.payload.get("conversation_id")
    if conversation_id:
        keys.append(f"conversation:{conversation_id}")
    if not keys:
        keys.append("world")
    return tuple(dict.fromkeys(keys))


def _domain(event: Event) -> str:
    prefix = event.event_type.split(".", 1)[0]
    return {
        "meal": "kitchen",
        "inventory": "kitchen",
        "shopping": "kitchen",
        "recipe": "kitchen",
        "study": "learning",
        "workout": "fitness",
        "plan": "planning",
        "strategy": "planning",
        "conversation": "communication",
        "workspace": "workspace",
        "notebook": "notebook",
        "fixture": "calendar",
        "standing_rule": "calendar",
    }.get(prefix, prefix)


def _operation(event_type: str) -> str:
    suffix = event_type.rsplit(".", 1)[-1].upper()
    return {
        "CREATED": "CREATE",
        "STARTED": "CREATE",
        "UPDATED": "UPDATE",
        "CHANGED": "UPDATE",
        "COMPLETED": "UPDATE",
        "RESUMED": "UPDATE",
        "PAUSED": "UPDATE",
        "ACCEPTED": "UPDATE",
        "REJECTED": "UPDATE",
        "ARCHIVED": "ARCHIVE",
        "DELETED": "DELETE",
    }.get(suffix, "UPDATE")


class RealtimeStateService:
    """Builds transport-neutral invalidations from committed WorldRevision history."""

    def changes_since(
        self,
        db: Session,
        user: UserProfile,
        *,
        after_revision: int,
        limit: int = 250,
    ) -> RealtimeCatchup:
        current = int(db.scalar(select(func.max(WorldRevision.revision)).where(WorldRevision.user_id == user.id)) or 0)
        earliest = db.scalar(select(func.min(WorldRevision.revision)).where(WorldRevision.user_id == user.id))
        if after_revision > current:
            return self._resync(after_revision, current, "client_revision_ahead")
        if earliest is not None and after_revision < int(earliest) - 1:
            return self._resync(after_revision, current, "history_pruned")
        rows = list(db.execute(
            select(WorldRevision, Event)
            .join(Event, Event.id == WorldRevision.event_id)
            .where(WorldRevision.user_id == user.id, WorldRevision.revision > after_revision)
            .order_by(WorldRevision.revision.asc())
            .limit(limit + 1)
        ))
        if len(rows) > limit:
            return self._resync(after_revision, current, "catchup_limit_exceeded")
        if current > after_revision and not rows:
            return self._resync(after_revision, current, "revision_history_missing")
        expected = after_revision + 1
        events: list[RealtimeStateEvent] = []
        for revision, event in rows:
            if revision.revision != expected:
                return self._resync(after_revision, current, "revision_gap")
            events.append(self.to_state_event(event, revision.revision))
            expected += 1
        return RealtimeCatchup(
            after_revision=after_revision,
            current_revision=current,
            events=events,
        )

    @staticmethod
    def to_state_event(event: Event, revision: int) -> RealtimeStateEvent:
        return RealtimeStateEvent(
            event_id=event.id,
            world_revision=revision,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            domain=_domain(event),
            entity_type=event.aggregate_type,
            entity_id=event.aggregate_id,
            operation=_operation(event.event_type),
            invalidates=invalidations_for(event),
            conversation_id=event.payload.get("conversation_id"),
            workspace_id=event.payload.get("workspace_id"),
            correlation_id=event.payload.get("correlation_id"),
            causation_id=event.payload.get("causation_id"),
        )

    @staticmethod
    def heartbeat(current_revision: int) -> RealtimeStateEvent:
        return RealtimeStateEvent(
            event_kind=RealtimeStateEventType.heartbeat,
            event_id=f"heartbeat:{current_revision}",
            world_revision=current_revision,
            occurred_at=datetime.now(UTC),
            event_type="realtime.heartbeat",
            domain="system",
            entity_type="world_revision",
            entity_id=str(current_revision),
            operation="OBSERVE",
            invalidates=(),
        )

    @staticmethod
    def resync_event(current_revision: int, reason_code: str) -> RealtimeStateEvent:
        return RealtimeStateEvent(
            event_kind=RealtimeStateEventType.resync_required,
            event_id=f"resync:{current_revision}:{reason_code}",
            world_revision=current_revision,
            occurred_at=datetime.now(UTC),
            event_type="realtime.resync_required",
            domain="system",
            entity_type="world_revision",
            entity_id=str(current_revision),
            operation="RESYNC",
            invalidates=("world",),
        )

    @staticmethod
    def _resync(after_revision: int, current: int, reason: str) -> RealtimeCatchup:
        return RealtimeCatchup(
            after_revision=after_revision,
            current_revision=current,
            events=[],
            resync_required=True,
            reason_code=reason,
        )
