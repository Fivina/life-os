from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attention.manager import AttentionManager
from app.attention.schemas import AttentionAction, AttentionCandidate
from app.attention.service import AttentionItemService
from app.database.models import Movie, ProspectiveThread, UserProfile
from app.decision.schemas import EntityReference
from app.movies.providers import ManualShowtimeProvider, ShowtimeProvider
from app.movies.schemas import ProspectiveEvaluationRead, ProspectiveMovieCreate, ShowtimeSearchRequest
from app.planning.movie_feasibility import evaluate_movie_showtime
from app.threads.eligibility import ProspectiveThreadEligibilityService
from app.threads.schemas import DateApproachingTriggerConditions, ExternalObservationTriggerConditions, ProspectiveEvaluationContext, ProspectiveTriggerType
from app.threads.service import ProspectiveThreadService


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_movie_thread(db: Session, user: UserProfile, movie: Movie, payload: ProspectiveMovieCreate) -> ProspectiveThread:
    source_ref = f"movie:{movie.id}:watch_when_available"
    existing = db.scalar(select(ProspectiveThread).where(
        ProspectiveThread.user_id == user.id,
        ProspectiveThread.source_ref == source_ref,
        ProspectiveThread.status == "OPEN",
    ))
    if existing is not None:
        return existing
    if movie.release_date:
        target = datetime.combine(movie.release_date, time.min, tzinfo=UTC)
        trigger_type = ProspectiveTriggerType.date_approaching
        conditions = DateApproachingTriggerConditions(target_at=target, lead_minutes=21 * 24 * 60)
        earliest = target - timedelta(days=21)
        latest = target + timedelta(days=180)
    else:
        trigger_type = ProspectiveTriggerType.event_available
        conditions = ExternalObservationTriggerConditions(observation_key=f"movie_release:{movie.id}", expected_value=True)
        earliest = latest = None
    return ProspectiveThreadService().create(
        db,
        user,
        subject=f"Watch {movie.title} when it becomes available",
        intent="WATCH_WHEN_AVAILABLE",
        trigger_type=trigger_type,
        trigger_conditions=conditions,
        entities=(EntityReference(entity_type="movie", entity_id=movie.id, role="subject"),),
        domain="leisure",
        earliest_relevance=earliest,
        latest_relevance=latest,
        check_policy="ADAPTIVE_RELEASE_WINDOW",
        attention_policy=payload.attention_policy,
        source="movie_intent",
        source_ref=source_ref,
        confidence=1.0,
        metadata={"movie_id": movie.id, "release_date": movie.release_date.isoformat() if movie.release_date else None, "next_check_at": (earliest or (utcnow() + timedelta(days=30))).isoformat()},
    )


def synchronize_release_threads(db: Session, user: UserProfile, movie: Movie) -> int:
    if movie.release_date is None:
        return 0
    rows = list(db.scalars(select(ProspectiveThread).where(
        ProspectiveThread.user_id == user.id,
        ProspectiveThread.source_ref == f"movie:{movie.id}:watch_when_available",
        ProspectiveThread.status == "OPEN",
    ).with_for_update()))
    target = datetime.combine(movie.release_date, time.min, tzinfo=UTC)
    changed = 0
    for row in rows:
        desired = DateApproachingTriggerConditions(target_at=target, lead_minutes=21 * 24 * 60).model_dump(mode="json")
        if row.trigger_type != ProspectiveTriggerType.date_approaching.value or row.trigger_conditions_json != desired:
            row.trigger_type = ProspectiveTriggerType.date_approaching.value
            row.trigger_conditions_json = desired
            row.earliest_relevance = target - timedelta(days=21)
            row.latest_relevance = target + timedelta(days=180)
            row.metadata_json = {**(row.metadata_json or {}), "release_date": movie.release_date.isoformat(), "next_check_at": (target - timedelta(days=21)).isoformat()}
            row.version += 1
            changed += 1
    return changed


def evaluate_movie_thread(
    db: Session,
    user: UserProfile,
    thread: ProspectiveThread,
    *,
    now: datetime | None = None,
    showtime_request: ShowtimeSearchRequest | None = None,
    provider: ShowtimeProvider | None = None,
    release_available: bool | None = None,
) -> ProspectiveEvaluationRead:
    when = now or utcnow()
    observations = {}
    movie_id = str((thread.metadata_json or {}).get("movie_id") or _movie_ref(thread))
    if release_available is not None:
        observations[f"movie_release:{movie_id}"] = release_available
    eligibility = ProspectiveThreadEligibilityService().evaluate(
        thread,
        ProspectiveEvaluationContext(now=when, trigger_observations=observations),
    )
    if not eligibility.eligible:
        return ProspectiveEvaluationRead(thread_id=thread.id, eligible=False, reason_code=eligibility.reason_code, attention_action="SILENT")
    movie = db.get(Movie, movie_id)
    if movie is None:
        return ProspectiveEvaluationRead(thread_id=thread.id, eligible=True, reason_code="movie_missing", attention_action="SILENT")
    options = []
    if showtime_request:
        showtime_provider = provider or ManualShowtimeProvider(showtime_request.manual_showtimes)
        showtimes = showtime_provider.search_showtimes(
            movie_title=movie.title,
            city=showtime_request.city,
            window_start=showtime_request.window_start,
            window_end=showtime_request.window_end,
        )[:20]
        options = [evaluate_movie_showtime(db, user, item, default_runtime_minutes=movie.runtime_minutes or 150) for item in showtimes]
    feasible = [option for option in options if option.feasible]
    requested = AttentionAction.mention_when_natural if feasible else AttentionAction.show_passively
    if thread.attention_policy == AttentionAction.show_passively.value:
        requested = AttentionAction.show_passively
    candidate = AttentionCandidate(
        requested_action=requested,
        reason_code="movie_showtime_feasible" if feasible else "movie_release_relevant",
        subject=f"{movie.title} is becoming relevant",
        priority=62 if feasible else 42,
        urgency=0.45 if feasible else 0.2,
        evidence_quality=0.9,
        confidence=0.9,
        prospective_thread_id=thread.id,
        expires_at=thread.latest_relevance,
        payload={"movie_id": movie.id, "feasible_showtime_count": len(feasible), "showtime_count": len(options)},
    )
    decision = AttentionManager().decide(candidate)
    item_id = None
    if decision.action not in {AttentionAction.silent, AttentionAction.act_silently}:
        item, _ = AttentionItemService().enqueue(
            db,
            user,
            decision,
            deduplication_key=f"movie-thread:{thread.id}:{decision.reason_code}",
            payload={"movie_id": movie.id, "thread_id": thread.id, "showtimes": [item.model_dump(mode="json") for item in options[:5]]},
            metadata={"policy_version": "movie-prospective-v1"},
        )
        item_id = item.id
    return ProspectiveEvaluationRead(
        thread_id=thread.id,
        eligible=True,
        reason_code=eligibility.reason_code,
        attention_action=decision.action.value,
        attention_item_id=item_id,
        showtimes=options,
    )


def _movie_ref(thread: ProspectiveThread) -> str:
    for item in thread.entities_json or []:
        if item.get("entity_type") == "movie":
            return str(item.get("entity_id"))
    return ""
