from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.api.deps import get_or_create_user
from app.database.models import (
    AttentionItem,
    Commitment,
    Movie,
    MovieImportBatch,
    MovieViewing,
    MovieWatchlistItem,
    PatternEvidence,
    PlanBlock,
    ProspectiveThread,
    RecommendationOutcome,
)
from app.movies.imports import confirm_letterboxd, preview_letterboxd
from app.movies.prospective import create_movie_thread, evaluate_movie_thread
from app.movies.schemas import (
    LetterboxdImportPreviewRequest,
    MovieCreate,
    MovieRecommendationOutcomeCreate,
    MovieRecommendationRequest,
    ProspectiveMovieCreate,
    Showtime,
    ShowtimeSearchRequest,
    ViewingCreate,
    WatchlistCreate,
)
from app.movies.service import (
    add_watchlist,
    create_movie_recommendation,
    get_or_create_trajectory,
    log_viewing,
    record_movie_outcome,
    save_movie,
)
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 9, 27, 18, tzinfo=UTC)


def movie(db, user, title: str, *, year=2025, runtime=110, genres=None):
    data = save_movie(db, user, MovieCreate(title=title, release_year=year, runtime_minutes=runtime, genres=genres or []))
    return db.get(Movie, data.id)


def test_trajectory_uses_calendar_week_and_never_creates_productivity_debt(db_session):
    user = get_or_create_user(db_session)
    film = movie(db_session, user, "Sunday Film")
    log_viewing(db_session, user, ViewingCreate(movie_id=film.id, watched_at=datetime(2026, 9, 21, 20, tzinfo=UTC)))
    state = get_or_create_trajectory(db_session, user, now=NOW)
    assert state.period_start == datetime(2026, 9, 21, tzinfo=UTC)
    assert state.period_end == datetime(2026, 9, 28, tzinfo=UTC)
    assert state.completed_count == 1 and state.state == "BELOW_RANGE" and state.remaining_to_min == 1
    assert db_session.query(PlanBlock).count() == 0


def test_watchlist_is_idempotent_and_history_preserves_rewatches(db_session):
    user = get_or_create_user(db_session); film = movie(db_session, user, "Arrival", year=2016)
    first = add_watchlist(db_session, user, WatchlistCreate(movie_id=film.id, priority=80))
    second = add_watchlist(db_session, user, WatchlistCreate(movie_id=film.id, priority=90))
    assert first.id == second.id and db_session.query(MovieWatchlistItem).count() == 1
    one = log_viewing(db_session, user, ViewingCreate(movie_id=film.id, watched_at=NOW, idempotency_key="arrival-1"))
    duplicate = log_viewing(db_session, user, ViewingCreate(movie_id=film.id, watched_at=NOW, idempotency_key="arrival-1"))
    two = log_viewing(db_session, user, ViewingCreate(movie_id=film.id, watched_at=NOW + timedelta(days=1), idempotency_key="arrival-2"))
    assert one.id == duplicate.id and not one.rewatch and two.rewatch
    assert db_session.query(MovieViewing).count() == 2
    assert db_session.get(MovieWatchlistItem, first.id).status == "WATCHED"


def test_letterboxd_export_preview_confirm_is_strongly_identified_and_idempotent(db_session):
    user = get_or_create_user(db_session)
    csv_text = "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n2026-09-20,Arrival,2016,https://letterboxd.com/film/arrival/,4.5,Yes,sci-fi,2026-09-19\n"
    request = LetterboxdImportPreviewRequest(file_name="diary.csv", content=csv_text)
    first = preview_letterboxd(db_session, user, request)
    second = preview_letterboxd(db_session, user, request)
    assert first.id == second.id and first.summary["ready"] == 1
    confirmed = confirm_letterboxd(db_session, user, first.id)
    repeated = confirm_letterboxd(db_session, user, first.id)
    assert confirmed.status == repeated.status == "CONFIRMED"
    assert db_session.query(MovieImportBatch).count() == db_session.query(Movie).count() == db_session.query(MovieViewing).count() == 1
    viewing = db_session.query(MovieViewing).one()
    assert viewing.rating == 4.5 and viewing.rating_scale == 5 and viewing.rewatch is False


def test_letterboxd_ambiguous_row_requires_review_and_is_not_imported(db_session):
    user = get_or_create_user(db_session)
    result = preview_letterboxd(db_session, user, LetterboxdImportPreviewRequest(file_name="watchlist.csv", content="Date,Name,Year,Letterboxd URI\n2026-01-01,Dune,,\n"))
    assert result.rows[0].status == "REVIEW_REQUIRED"
    confirmed = confirm_letterboxd(db_session, user, result.id)
    assert confirmed.status == "PARTIAL" and db_session.query(Movie).count() == 0


def test_movie_recommendation_filters_runtime_and_watched_and_explains_score(db_session):
    user = get_or_create_user(db_session)
    watched = movie(db_session, user, "Already Seen", runtime=90, genres=["Drama"])
    long = movie(db_session, user, "Too Long", runtime=220, genres=["Action"])
    watchlist = movie(db_session, user, "Tonight", runtime=105, genres=["Comedy"])
    other = movie(db_session, user, "Alternative", runtime=100, genres=["Drama"])
    log_viewing(db_session, user, ViewingCreate(movie_id=watched.id, watched_at=NOW))
    add_watchlist(db_session, user, WatchlistCreate(movie_id=watchlist.id, priority=100))
    db_session.add(PatternEvidence(user_id=user.id, pattern_type="movie_genre", scope={"domain": "leisure", "genres": ["Comedy"]}, claim="Repeated comedy choice", evidence_n=4, weighted_support=3.2, confidence=0.8, status="ACTIVE"))
    db_session.flush()
    recommendation = create_movie_recommendation(db_session, user, MovieRecommendationRequest(available_minutes=120, preferred_genres=["Comedy"], mood="LIGHT", limit=3), now=NOW)
    ids = [option.reference_id for option in recommendation.options]
    assert watchlist.id in ids and watched.id not in ids and long.id not in ids
    top = next(option for option in recommendation.options if option.reference_id == watchlist.id)
    assert top.payload_json["score_factors"]["watchlist"] > 0
    assert top.payload_json["score_factors"]["learned_preference"] == 8
    assert top.payload_json["explanation"]
    assert db_session.query(PlanBlock).count() == 0


def test_selected_is_not_watched_and_watched_creates_history(db_session):
    user = get_or_create_user(db_session); film = movie(db_session, user, "Choice", runtime=100)
    recommendation = create_movie_recommendation(db_session, user, MovieRecommendationRequest(limit=3), now=NOW)
    option = next(item for item in recommendation.options if item.reference_id == film.id)
    selected = record_movie_outcome(db_session, user, recommendation.id, MovieRecommendationOutcomeCreate(option_id=option.id, outcome="SELECTED", idempotency_key="selected"))
    assert selected.outcome == "accepted" and db_session.query(MovieViewing).count() == 0
    watched = record_movie_outcome(db_session, user, recommendation.id, MovieRecommendationOutcomeCreate(option_id=option.id, outcome="WATCHED", idempotency_key="watched"), watched_at=NOW)
    assert watched.outcome == "completed" and db_session.query(MovieViewing).count() == 1
    assert db_session.query(RecommendationOutcome).count() == 2


def test_prospective_movie_stays_dormant_then_surfaces_feasible_showtime_once(db_session):
    user = get_or_create_user(db_session)
    film = movie(db_session, user, "Future Film", year=2027)
    film.release_date = (NOW + timedelta(days=40)).date(); db_session.flush()
    thread = create_movie_thread(db_session, user, film, ProspectiveMovieCreate(movie_id=film.id))
    dormant = evaluate_movie_thread(db_session, user, thread, now=NOW)
    assert not dormant.eligible and dormant.attention_action == "SILENT"
    showtime = Showtime(provider="manual", external_id="show-1", starts_at=NOW + timedelta(days=25, hours=2), ends_at=NOW + timedelta(days=25, hours=4), venue="Cinema", city="Berlin")
    request = ShowtimeSearchRequest(movie_id=film.id, city="Berlin", window_start=NOW + timedelta(days=25), window_end=NOW + timedelta(days=26), manual_showtimes=[showtime])
    active = evaluate_movie_thread(db_session, user, thread, now=NOW + timedelta(days=25), showtime_request=request)
    repeated = evaluate_movie_thread(db_session, user, thread, now=NOW + timedelta(days=25), showtime_request=request)
    assert active.eligible and active.attention_action == "MENTION_WHEN_NATURAL"
    assert active.showtimes[0].feasible and repeated.attention_item_id == active.attention_item_id
    assert db_session.query(AttentionItem).count() == 1


def test_protected_showtime_conflict_is_not_scheduled_or_booked(db_session):
    user = get_or_create_user(db_session)
    film = movie(db_session, user, "Conflict Film", year=2026); film.release_date = NOW.date(); db_session.flush()
    thread = create_movie_thread(db_session, user, film, ProspectiveMovieCreate(movie_id=film.id))
    starts = NOW + timedelta(hours=2); ends = starts + timedelta(hours=2)
    db_session.add(Commitment(user_id=user.id, title="Exam", starts_at=starts, ends_at=ends, level="hard", commitment_type="hard", status="active")); db_session.flush()
    request = ShowtimeSearchRequest(movie_id=film.id, city="Berlin", window_start=NOW, window_end=NOW + timedelta(days=1), manual_showtimes=[Showtime(provider="manual", external_id="x", starts_at=starts, ends_at=ends, venue="Cinema", city="Berlin")])
    result = evaluate_movie_thread(db_session, user, thread, now=NOW, showtime_request=request)
    assert not result.showtimes[0].feasible and result.showtimes[0].requires_plan_proposal
    assert db_session.query(PlanBlock).count() == 0


def test_assistant_release_phrase_creates_dormant_thread_without_calendar_mutation(client, db_session):
    response = client.post("/api/v1/assistant/message", headers=AUTH_HEADERS, json={"message": "I want to see the next Avengers when it releases", "role": "GENERAL_ASSISTANT"})
    assert response.status_code == 200 and response.json()["model_tier"] == "NO_AI"
    assert "Nothing was booked" in response.json()["message"]
    assert db_session.query(ProspectiveThread).count() == db_session.query(Movie).count() == 1
    assert db_session.query(Commitment).count() == db_session.query(PlanBlock).count() == 0
