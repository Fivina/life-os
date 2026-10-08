from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    LeisureTrajectory,
    Movie,
    MovieExternalId,
    MovieViewing,
    MovieWatchlistItem,
    PatternEvidence,
    RecommendationOption,
    UserProfile,
)
from app.events.service import append_event
from app.memory.schemas import RecommendationCreate, RecommendationOptionCreate, RecommendationOutcomeCreate, RecommendationOutcomeRead, RecommendationRead
from app.movies.schemas import (
    LeisureTrajectoryRead,
    LeisureTrajectoryUpdate,
    MetadataMovie,
    MovieCreate,
    MovieRead,
    MovieRecommendationOutcomeCreate,
    MovieRecommendationRequest,
    ViewingCreate,
    ViewingRead,
    WatchlistCreate,
    WatchlistRead,
)
from app.recommendations import service as recommendation_service


MOOD_GENRES = {
    "LIGHT": {"comedy", "family", "animation", "romance"},
    "ENERGETIC": {"action", "adventure", "music"},
    "TENSE": {"thriller", "crime", "horror", "mystery"},
    "REFLECTIVE": {"drama", "documentary", "history"},
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _emit(db: Session, user: UserProfile, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> None:
    append_event(
        db,
        user,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        outbox=True,
    )


def _period_bounds(now: datetime, week_starts_on: int) -> tuple[datetime, datetime]:
    current = _aware(now)
    start_date = current.date() - timedelta(days=(current.weekday() - week_starts_on) % 7)
    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    return start, start + timedelta(days=7)


def get_or_create_trajectory(db: Session, user: UserProfile, *, now: datetime | None = None) -> LeisureTrajectoryRead:
    row = db.scalar(select(LeisureTrajectory).where(LeisureTrajectory.user_id == user.id, LeisureTrajectory.leisure_type == "MOVIE"))
    if row is None:
        row = LeisureTrajectory(user_id=user.id, leisure_type="MOVIE", period="WEEK", target_min=2, target_max=3, week_starts_on=0, status="ACTIVE")
        db.add(row)
        db.flush()
        _emit(db, user, "leisure.trajectory_created", "leisure_trajectory", row.id, {"target_min": 2, "target_max": 3, "period": "WEEK"})
    return trajectory_read(db, user, row, now=now)


def update_trajectory(db: Session, user: UserProfile, payload: LeisureTrajectoryUpdate, *, now: datetime | None = None) -> LeisureTrajectoryRead:
    row = db.scalar(select(LeisureTrajectory).where(LeisureTrajectory.user_id == user.id, LeisureTrajectory.leisure_type == "MOVIE").with_for_update())
    if row is None:
        get_or_create_trajectory(db, user, now=now)
        row = db.scalar(select(LeisureTrajectory).where(LeisureTrajectory.user_id == user.id, LeisureTrajectory.leisure_type == "MOVIE").with_for_update())
    assert row is not None
    row.target_min = payload.target_min
    row.target_max = payload.target_max
    row.week_starts_on = payload.week_starts_on
    row.status = payload.status
    row.version += 1
    _emit(db, user, "leisure.trajectory_updated", "leisure_trajectory", row.id, payload.model_dump())
    return trajectory_read(db, user, row, now=now)


def trajectory_read(db: Session, user: UserProfile, row: LeisureTrajectory, *, now: datetime | None = None) -> LeisureTrajectoryRead:
    start, end = _period_bounds(now or utcnow(), row.week_starts_on)
    count = int(db.scalar(select(func.count(MovieViewing.id)).where(MovieViewing.user_id == user.id, MovieViewing.watched_at >= start, MovieViewing.watched_at < end)) or 0)
    state = "PAUSED" if row.status != "ACTIVE" else "BELOW_RANGE" if count < row.target_min else "ABOVE_RANGE" if count > row.target_max else "IN_RANGE"
    return LeisureTrajectoryRead(
        id=row.id,
        leisure_type=row.leisure_type,
        period=row.period,
        target_min=row.target_min,
        target_max=row.target_max,
        week_starts_on=row.week_starts_on,
        status=row.status,
        period_start=start,
        period_end=end,
        completed_count=count,
        state=state,
        remaining_to_min=max(0, row.target_min - count),
    )


def movie_read(db: Session, row: Movie) -> MovieRead:
    external_ids = list(db.scalars(select(MovieExternalId).where(MovieExternalId.movie_id == row.id).order_by(MovieExternalId.provider.asc())))
    return MovieRead(
        id=row.id,
        title=row.title,
        original_title=row.original_title,
        release_year=row.release_year,
        release_date=row.release_date,
        runtime_minutes=row.runtime_minutes,
        genres=[str(value) for value in (row.genres_json or [])],
        overview=row.overview,
        poster_url=row.poster_url,
        metadata_source=row.metadata_source,
        external_ids=external_ids,
    )


def get_movie(db: Session, movie_id: str) -> Movie:
    row = db.get(Movie, movie_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found.")
    return row


def list_movies(db: Session, *, query: str | None = None, limit: int = 50) -> list[MovieRead]:
    statement = select(Movie)
    if query:
        statement = statement.where(Movie.title.ilike(f"%{query.strip()}%"))
    rows = list(db.scalars(statement.order_by(Movie.title.asc(), Movie.release_year.desc()).limit(max(1, min(limit, 100)))))
    return [movie_read(db, row) for row in rows]


def upsert_movie(db: Session, payload: MovieCreate | MetadataMovie) -> tuple[Movie, bool]:
    if isinstance(payload, MetadataMovie):
        data = MovieCreate(
            title=payload.title,
            original_title=payload.original_title,
            release_year=payload.release_date.year if payload.release_date else None,
            release_date=payload.release_date,
            runtime_minutes=payload.runtime_minutes,
            genres=list(payload.genres),
            overview=payload.overview,
            poster_url=payload.poster_url,
            provider=payload.provider,
            external_id=payload.external_id,
            source_url=payload.source_url,
        )
        metadata = {"provider_rating": payload.provider_rating, "provider_vote_count": payload.provider_vote_count}
    else:
        data = payload
        metadata = {}
    row = None
    if data.provider and data.external_id:
        external = db.scalar(select(MovieExternalId).where(MovieExternalId.provider == data.provider.lower(), MovieExternalId.external_id == data.external_id))
        row = db.get(Movie, external.movie_id) if external else None
    if row is None and data.release_year is not None:
        matches = list(db.scalars(select(Movie).where(func.lower(Movie.title) == data.title.casefold(), Movie.release_year == data.release_year).limit(2)))
        row = matches[0] if len(matches) == 1 else None
    created = row is None
    if row is None:
        row = Movie(title=data.title, release_year=data.release_year, genres_json=[])
        db.add(row)
        db.flush()
    row.title = data.title
    row.original_title = data.original_title or row.original_title
    row.release_year = data.release_year or (data.release_date.year if data.release_date else row.release_year)
    row.release_date = data.release_date or row.release_date
    row.runtime_minutes = data.runtime_minutes or row.runtime_minutes
    row.genres_json = sorted(set(data.genres or row.genres_json or []), key=str.casefold)
    row.overview = data.overview or row.overview
    row.poster_url = data.poster_url or row.poster_url
    if data.provider:
        row.metadata_source = data.provider.lower()
        row.metadata_updated_at = utcnow()
        row.metadata_json = {**(row.metadata_json or {}), **{k: v for k, v in metadata.items() if v is not None}}
        external = db.scalar(select(MovieExternalId).where(MovieExternalId.provider == data.provider.lower(), MovieExternalId.external_id == data.external_id))
        if external is None:
            db.add(MovieExternalId(movie_id=row.id, provider=data.provider.lower(), external_id=data.external_id or "", source_url=data.source_url))
    db.flush()
    return row, created


def save_movie(db: Session, user: UserProfile, payload: MovieCreate) -> MovieRead:
    row, created = upsert_movie(db, payload)
    _emit(db, user, "movie.created" if created else "movie.updated", "movie", row.id, {"movie_id": row.id, "title": row.title, "source": payload.provider or "manual"})
    return movie_read(db, row)


def add_watchlist(db: Session, user: UserProfile, payload: WatchlistCreate) -> WatchlistRead:
    movie = get_movie(db, payload.movie_id)
    row = db.scalar(select(MovieWatchlistItem).where(MovieWatchlistItem.user_id == user.id, MovieWatchlistItem.movie_id == movie.id).with_for_update())
    created = row is None
    if row is None:
        row = MovieWatchlistItem(user_id=user.id, movie_id=movie.id)
        db.add(row)
    row.status = "ACTIVE"
    row.priority = payload.priority
    row.notes = payload.notes
    row.source = payload.source
    row.source_ref = payload.source_ref
    row.removed_at = None
    db.flush()
    _emit(db, user, "movie.watchlist_added" if created else "movie.watchlist_updated", "movie_watchlist_item", row.id, {"movie_id": movie.id, "status": row.status})
    return _watchlist_read(db, row, movie)


def remove_watchlist(db: Session, user: UserProfile, item_id: str) -> WatchlistRead:
    row = db.scalar(select(MovieWatchlistItem).where(MovieWatchlistItem.id == item_id, MovieWatchlistItem.user_id == user.id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    row.status = "REMOVED"
    row.removed_at = utcnow()
    row.version += 1
    _emit(db, user, "movie.watchlist_removed", "movie_watchlist_item", row.id, {"movie_id": row.movie_id})
    return _watchlist_read(db, row, get_movie(db, row.movie_id))


def list_watchlist(db: Session, user: UserProfile, *, include_removed: bool = False) -> list[WatchlistRead]:
    statement = select(MovieWatchlistItem).where(MovieWatchlistItem.user_id == user.id)
    if not include_removed:
        statement = statement.where(MovieWatchlistItem.status == "ACTIVE")
    rows = list(db.scalars(statement.order_by(MovieWatchlistItem.priority.desc(), MovieWatchlistItem.added_at.desc())))
    return [_watchlist_read(db, row, get_movie(db, row.movie_id)) for row in rows]


def _watchlist_read(db: Session, row: MovieWatchlistItem, movie: Movie) -> WatchlistRead:
    return WatchlistRead(
        id=row.id, movie_id=row.movie_id, status=row.status, priority=row.priority, source=row.source,
        source_ref=row.source_ref, notes=row.notes, added_at=row.added_at, movie=movie_read(db, movie),
    )


def log_viewing(db: Session, user: UserProfile, payload: ViewingCreate) -> ViewingRead:
    movie = get_movie(db, payload.movie_id)
    if payload.idempotency_key:
        existing = db.scalar(select(MovieViewing).where(MovieViewing.user_id == user.id, MovieViewing.idempotency_key == payload.idempotency_key))
        if existing is not None:
            return _viewing_read(db, existing, movie)
    prior_count = int(db.scalar(select(func.count(MovieViewing.id)).where(MovieViewing.user_id == user.id, MovieViewing.movie_id == movie.id)) or 0)
    row = MovieViewing(
        user_id=user.id, movie_id=movie.id, watched_at=_aware(payload.watched_at), source=payload.source,
        source_ref=payload.source_ref, rewatch=prior_count > 0, rating=payload.rating,
        rating_scale=payload.rating_scale if payload.rating is not None else None, liked=payload.liked,
        notes=payload.notes, recommendation_id=payload.recommendation_id,
        recommendation_option_id=payload.recommendation_option_id, idempotency_key=payload.idempotency_key,
    )
    db.add(row)
    watchlist = db.scalar(select(MovieWatchlistItem).where(MovieWatchlistItem.user_id == user.id, MovieWatchlistItem.movie_id == movie.id).with_for_update())
    if watchlist is not None and watchlist.status == "ACTIVE":
        watchlist.status = "WATCHED"
    db.flush()
    _emit(db, user, "movie.watched", "movie_viewing", row.id, {"movie_id": movie.id, "rewatch": row.rewatch, "rating": row.rating})
    return _viewing_read(db, row, movie)


def list_viewings(db: Session, user: UserProfile, *, limit: int = 100) -> list[ViewingRead]:
    rows = list(db.scalars(select(MovieViewing).where(MovieViewing.user_id == user.id).order_by(MovieViewing.watched_at.desc()).limit(max(1, min(limit, 500)))))
    return [_viewing_read(db, row, get_movie(db, row.movie_id)) for row in rows]


def _viewing_read(db: Session, row: MovieViewing, movie: Movie) -> ViewingRead:
    return ViewingRead(
        id=row.id, movie_id=row.movie_id, watched_at=row.watched_at, source=row.source, source_ref=row.source_ref,
        rewatch=row.rewatch, rating=row.rating, rating_scale=row.rating_scale, liked=row.liked, notes=row.notes,
        recommendation_id=row.recommendation_id, recommendation_option_id=row.recommendation_option_id,
        movie=movie_read(db, movie),
    )


def create_movie_recommendation(db: Session, user: UserProfile, request: MovieRecommendationRequest, *, now: datetime | None = None) -> RecommendationRead:
    when = _aware(now or utcnow())
    watched_rows = list(db.scalars(select(MovieViewing).where(MovieViewing.user_id == user.id).order_by(MovieViewing.watched_at.desc()).limit(100)))
    watched_ids = {item.movie_id for item in watched_rows}
    recent_rows = [item for item in watched_rows if _aware(item.watched_at) >= when - timedelta(days=30)]
    recent_genres: Counter[str] = Counter()
    for viewing in recent_rows:
        for genre in get_movie(db, viewing.movie_id).genres_json or []:
            recent_genres[str(genre).casefold()] += 1
    watchlist_rows = list(db.scalars(select(MovieWatchlistItem).where(MovieWatchlistItem.user_id == user.id, MovieWatchlistItem.status == "ACTIVE")))
    watchlist_by_movie = {row.movie_id: row for row in watchlist_rows}
    statement = select(Movie)
    if request.watchlist_only:
        statement = statement.where(Movie.id.in_(list(watchlist_by_movie) or ["__none__"]))
    candidates = list(db.scalars(statement.order_by(Movie.title.asc()).limit(250)))
    patterns = list(db.scalars(select(PatternEvidence).where(PatternEvidence.user_id == user.id, PatternEvidence.status == "ACTIVE").order_by(PatternEvidence.confidence.desc()).limit(50)))
    scored: list[tuple[float, Movie, dict]] = []
    preferred = {value.casefold() for value in request.preferred_genres}
    mood_genres = MOOD_GENRES.get(request.mood, set())
    for movie in candidates:
        if movie.id in watched_ids and not request.include_rewatches:
            continue
        if request.available_minutes is not None and movie.runtime_minutes is not None and movie.runtime_minutes > request.available_minutes:
            continue
        genres = {str(value).casefold() for value in (movie.genres_json or [])}
        factors: dict[str, float] = {}
        watchlist = watchlist_by_movie.get(movie.id)
        if watchlist:
            factors["watchlist"] = 22 + watchlist.priority / 10
        if request.available_minutes is not None and movie.runtime_minutes is not None:
            slack = request.available_minutes - movie.runtime_minutes
            factors["runtime_fit"] = max(0, 20 - slack / 15)
        if preferred and genres:
            factors["explicit_genre"] = 15 * len(preferred & genres) / len(preferred)
        if mood_genres and genres:
            factors["mood_fit"] = 8 * min(1, len(mood_genres & genres))
        repetition = sum(recent_genres[genre] for genre in genres)
        if repetition:
            factors["recent_repetition"] = -min(15, repetition * 3)
        if movie.id not in watched_ids:
            factors["novelty"] = 8
        factors["metadata_quality"] = min(8, sum(bool(value) for value in (movie.runtime_minutes, movie.release_date, movie.overview, movie.poster_url, movie.genres_json)) * 1.6)
        learned = _learned_genre_support(patterns, genres)
        if learned:
            factors["learned_preference"] = learned
        scored.append((round(sum(factors.values()), 4), movie, factors))
    scored.sort(key=lambda item: (-item[0], item[1].title.casefold(), item[1].release_year or 0))
    selected = scored[: request.limit]
    options = [
        RecommendationOptionCreate(
            label=movie.title,
            rank=index,
            score=score,
            reference_type="movie",
            reference_id=movie.id,
            payload_json={
                "movie_id": movie.id,
                "runtime_minutes": movie.runtime_minutes,
                "genres": movie.genres_json or [],
                "release_year": movie.release_year,
                "poster_url": movie.poster_url,
                "score_factors": factors,
                "explanation": _explanation(factors),
            },
        )
        for index, (score, movie, factors) in enumerate(selected, start=1)
    ]
    request_json = request.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(request_json, sort_keys=True).encode()).hexdigest()[:16]
    result = recommendation_service.create_recommendation(
        db,
        user,
        RecommendationCreate(
            domain="leisure",
            kind="movie",
            title="Movies for this moment",
            reason="Filtered by available time and actual movie history, then ranked by inspectable factors.",
            context_snapshot={**request_json, "policy_version": "movie-recommendation-v1", "candidate_count": len(scored)},
            options=options,
            idempotency_key=f"movie-rec:{when.date().isoformat()}:{digest}",
        ),
    )
    _emit(db, user, "movie.recommendation_created", "recommendation", result.id, {"recommendation_id": result.id, "option_count": len(options), "policy_version": "movie-recommendation-v1"})
    return result


def _learned_genre_support(patterns: Iterable[PatternEvidence], genres: set[str]) -> float:
    support = 0.0
    for pattern in patterns:
        scope = pattern.scope or {}
        if str(scope.get("domain", "")).casefold() not in {"leisure", "movie", "movies"}:
            continue
        pattern_genres = {str(value).casefold() for value in scope.get("genres", [])}
        if pattern_genres & genres:
            support = max(support, min(10.0, pattern.confidence * 10.0))
    return round(support, 4)


def _explanation(factors: dict[str, float]) -> list[str]:
    labels = {
        "watchlist": "Already on your watchlist",
        "runtime_fit": "Fits the time available",
        "explicit_genre": "Matches the genres you chose",
        "mood_fit": "Matches the mood you selected",
        "novelty": "Adds variety",
        "learned_preference": "Supported by repeated accepted outcomes",
        "metadata_quality": "Has complete decision details",
        "recent_repetition": "Reduced to avoid repeating recent genres",
    }
    return [labels[key] for key, value in sorted(factors.items(), key=lambda item: -abs(item[1])) if value != 0][:4]


def record_movie_outcome(
    db: Session,
    user: UserProfile,
    recommendation_id: str,
    payload: MovieRecommendationOutcomeCreate,
    *,
    watched_at: datetime | None = None,
) -> RecommendationOutcomeRead:
    option = db.scalar(select(RecommendationOption).where(RecommendationOption.id == payload.option_id, RecommendationOption.recommendation_id == recommendation_id, RecommendationOption.user_id == user.id))
    if option is None or option.reference_type != "movie" or not option.reference_id:
        raise HTTPException(status_code=404, detail="Movie recommendation option not found.")
    mapped = {"SELECTED": "accepted", "WATCHED": "completed", "REJECTED": "rejected"}[payload.outcome]
    genres = list((option.payload_json or {}).get("genres", []))
    outcome = recommendation_service.record_outcome(
        db,
        user,
        RecommendationOutcomeCreate(
            domain="leisure",
            recommendation_type="movie",
            recommendation_summary=f"{payload.outcome.title()}: {option.label}",
            outcome=mapped,
            recommendation_id=recommendation_id,
            option_id=option.id,
            source_entity_type="movie",
            source_entity_id=option.reference_id,
            feedback_text=payload.feedback_text,
            idempotency_key=payload.idempotency_key,
            metadata_json={
                "movie_outcome": payload.outcome,
                "score_factors": (option.payload_json or {}).get("score_factors", {}),
                "memory_candidate": {
                    "normalized_key": f"movie-genres:{','.join(sorted(str(g).casefold() for g in genres))}",
                    "memory_type": "preference",
                    "domain": "leisure",
                    "claim": f"Repeatedly accepts movie options with genres: {', '.join(genres)}",
                    "scope": {"domain": "leisure", "genres": genres},
                } if genres and payload.outcome in {"SELECTED", "WATCHED"} else None,
            },
        ),
    )
    if payload.outcome == "WATCHED":
        log_viewing(
            db,
            user,
            ViewingCreate(
                movie_id=option.reference_id,
                watched_at=watched_at or utcnow(),
                recommendation_id=recommendation_id,
                recommendation_option_id=option.id,
                source="recommendation",
                source_ref=outcome.id,
                idempotency_key=f"movie-outcome:{outcome.id}",
            ),
        )
    _emit(db, user, f"movie.recommendation_{payload.outcome.lower()}", "recommendation_outcome", outcome.id, {"recommendation_id": recommendation_id, "movie_id": option.reference_id, "outcome": payload.outcome})
    return outcome
