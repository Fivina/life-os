from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.models import ProspectiveThread, UserProfile
from app.database.session import get_db
from app.memory.schemas import RecommendationOutcomeRead, RecommendationRead
from app.movies import imports, service
from app.movies.providers import metadata_provider
from app.movies.prospective import create_movie_thread, evaluate_movie_thread, synchronize_release_threads
from app.movies.schemas import (
    LeisureTrajectoryRead,
    LeisureTrajectoryUpdate,
    LetterboxdImportPreviewRequest,
    MetadataMovie,
    MovieCreate,
    MovieImportBatchRead,
    MovieImportRowRead,
    MovieRead,
    MovieRecommendationOutcomeCreate,
    MovieRecommendationRequest,
    ProspectiveEvaluationRead,
    ProspectiveMovieCreate,
    ShowtimeSearchRequest,
    ViewingCreate,
    ViewingRead,
    WatchlistCreate,
    WatchlistRead,
)


router = APIRouter(tags=["leisure", "movies"])


@router.get("/leisure/trajectory", response_model=LeisureTrajectoryRead)
def get_trajectory(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.get_or_create_trajectory(db, user); db.commit(); return result


@router.put("/leisure/trajectory", response_model=LeisureTrajectoryRead)
def put_trajectory(payload: LeisureTrajectoryUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.update_trajectory(db, user, payload); db.commit(); return result


@router.get("/movies/metadata/search", response_model=list[MetadataMovie])
def search_metadata(q: str = Query(min_length=1, max_length=200), year: int | None = Query(default=None, ge=1888, le=2200), limit: int = Query(default=10, ge=1, le=20)):
    return metadata_provider().search(q, year=year, limit=limit)


@router.post("/movies/metadata/{external_id}/save", response_model=MovieRead)
def save_metadata_movie(external_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    normalized = metadata_provider().get(external_id)
    result = service.save_movie(db, user, MovieCreate(
        title=normalized.title, original_title=normalized.original_title,
        release_year=normalized.release_date.year if normalized.release_date else None,
        release_date=normalized.release_date, runtime_minutes=normalized.runtime_minutes,
        genres=list(normalized.genres), overview=normalized.overview, poster_url=normalized.poster_url,
        provider=normalized.provider, external_id=normalized.external_id, source_url=normalized.source_url,
    ))
    synchronize_release_threads(db, user, service.get_movie(db, result.id))
    db.commit(); return result


@router.get("/movies", response_model=list[MovieRead])
def list_movies(q: str | None = Query(default=None, max_length=200), limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_movies(db, query=q, limit=limit)


@router.post("/movies", response_model=MovieRead)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.save_movie(db, user, payload); db.commit(); return result


@router.get("/movies/watchlist", response_model=list[WatchlistRead])
def get_watchlist(include_removed: bool = False, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_watchlist(db, user, include_removed=include_removed)


@router.post("/movies/watchlist", response_model=WatchlistRead)
def add_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.add_watchlist(db, user, payload); db.commit(); return result


@router.delete("/movies/watchlist/{item_id}", response_model=WatchlistRead)
def remove_watchlist(item_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.remove_watchlist(db, user, item_id); db.commit(); return result


@router.get("/movies/history", response_model=list[ViewingRead])
def get_history(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_viewings(db, user, limit=limit)


@router.post("/movies/history", response_model=ViewingRead)
def add_history(payload: ViewingCreate, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    data = payload if payload.idempotency_key or not idempotency_key else payload.model_copy(update={"idempotency_key": idempotency_key})
    result = service.log_viewing(db, user, data); db.commit(); return result


@router.post("/movies/imports/letterboxd/preview", response_model=MovieImportBatchRead)
def preview_letterboxd(payload: LetterboxdImportPreviewRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = imports.preview_letterboxd(db, user, payload); db.commit(); return result


@router.post("/movies/imports/{batch_id}/confirm", response_model=MovieImportBatchRead)
def confirm_import(batch_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = imports.confirm_letterboxd(db, user, batch_id); db.commit(); return result


@router.post("/movies/imports/rows/{row_id}/resolve/{movie_id}", response_model=MovieImportRowRead)
def resolve_import_row(row_id: str, movie_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = imports.resolve_import_row(db, user, row_id, movie_id); db.commit(); return result


@router.post("/movies/recommendations", response_model=RecommendationRead)
def recommend_movies(payload: MovieRecommendationRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.create_movie_recommendation(db, user, payload); db.commit(); return result


@router.post("/movies/recommendations/{recommendation_id}/outcomes", response_model=RecommendationOutcomeRead)
def movie_outcome(recommendation_id: str, payload: MovieRecommendationOutcomeCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.record_movie_outcome(db, user, recommendation_id, payload); db.commit(); return result


@router.get("/movies/prospective")
def list_movie_threads(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    rows = list(db.scalars(select(ProspectiveThread).where(ProspectiveThread.user_id == user.id, ProspectiveThread.domain == "leisure", ProspectiveThread.intent == "WATCH_WHEN_AVAILABLE").order_by(ProspectiveThread.created_at.desc()).limit(100)))
    return [{"id": row.id, "subject": row.subject, "status": row.status, "trigger_type": row.trigger_type, "earliest_relevance": row.earliest_relevance, "latest_relevance": row.latest_relevance, "metadata": row.metadata_json} for row in rows]


@router.post("/movies/prospective")
def create_prospective(payload: ProspectiveMovieCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    movie = service.get_movie(db, payload.movie_id)
    row = create_movie_thread(db, user, movie, payload); db.commit()
    return {"id": row.id, "subject": row.subject, "status": row.status, "trigger_type": row.trigger_type, "earliest_relevance": row.earliest_relevance, "latest_relevance": row.latest_relevance, "metadata": row.metadata_json}


@router.post("/movies/prospective/{thread_id}/evaluate", response_model=ProspectiveEvaluationRead)
def evaluate_prospective(thread_id: str, payload: ShowtimeSearchRequest | None = None, release_available: bool | None = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    thread = db.scalar(select(ProspectiveThread).where(ProspectiveThread.id == thread_id, ProspectiveThread.user_id == user.id))
    if thread is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Prospective movie thread not found.")
    result = evaluate_movie_thread(db, user, thread, showtime_request=payload, release_available=release_available)
    db.commit(); return result
