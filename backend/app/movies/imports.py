from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, date, datetime, time
from pathlib import PurePath
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Movie, MovieExternalId, MovieImportBatch, MovieImportRow, UserProfile
from app.events.service import append_event
from app.movies.schemas import LetterboxdImportPreviewRequest, MovieCreate, MovieImportBatchRead, MovieImportRowRead, ViewingCreate, WatchlistCreate
from app.movies.service import add_watchlist, log_viewing, upsert_movie, utcnow


KINDS_BY_NAME = {
    "watchlist": "WATCHLIST",
    "diary": "DIARY",
    "watched": "WATCHED",
    "ratings": "RATINGS",
}


def _kind(file_name: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    stem = PurePath(file_name).stem.casefold()
    for token, kind in KINDS_BY_NAME.items():
        if token in stem:
            return kind
    raise HTTPException(status_code=422, detail="Choose whether this Letterboxd file is a watchlist, diary, watched list, or ratings export.")


def _letterboxd_id(uri: str | None) -> str | None:
    if not uri:
        return None
    parsed = urlparse(uri.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if "film" in parts:
        index = parts.index("film")
        if index + 1 < len(parts):
            return parts[index + 1]
    return None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    return None


def _row_value(row: dict[str, str], *names: str) -> str | None:
    lowered = {str(key).strip().casefold(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.casefold())
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def preview_letterboxd(db: Session, user: UserProfile, payload: LetterboxdImportPreviewRequest) -> MovieImportBatchRead:
    content_hash = hashlib.sha256(payload.content.encode("utf-8-sig")).hexdigest()
    existing = db.scalar(select(MovieImportBatch).where(MovieImportBatch.user_id == user.id, MovieImportBatch.provider == "letterboxd_export", MovieImportBatch.content_hash == content_hash))
    if existing is not None:
        return batch_read(db, existing)
    kind = _kind(payload.file_name, payload.source_kind)
    batch = MovieImportBatch(user_id=user.id, provider="letterboxd_export", file_name=payload.file_name, content_hash=content_hash, status="PREVIEW")
    db.add(batch)
    db.flush()
    reader = csv.DictReader(io.StringIO(payload.content.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="The CSV file has no header row.")
    counts = {"ready": 0, "review_required": 0, "errors": 0, "total": 0}
    for index, raw in enumerate(reader, start=1):
        title = _row_value(raw, "Name", "Title")
        year_raw = _row_value(raw, "Year")
        uri = _row_value(raw, "Letterboxd URI", "URI")
        external_id = _letterboxd_id(uri)
        watched_date = _date(_row_value(raw, "Watched Date", "Date"))
        rating_raw = _row_value(raw, "Rating")
        try:
            year = int(year_raw) if year_raw else None
            rating = float(rating_raw) if rating_raw else None
        except ValueError:
            year, rating = None, None
        normalized = {
            "title": title,
            "year": year,
            "letterboxd_uri": uri,
            "letterboxd_id": external_id,
            "watched_date": watched_date.isoformat() if watched_date else None,
            "rating": rating,
            "rewatch": (_row_value(raw, "Rewatch") or "").casefold() in {"yes", "true", "1"},
            "tags": _row_value(raw, "Tags"),
        }
        error = None
        status = "READY"
        movie_id = None
        if not title:
            status, error = "ERROR", "Missing movie title."
        elif external_id:
            external = db.scalar(select(MovieExternalId).where(MovieExternalId.provider == "letterboxd", MovieExternalId.external_id == external_id))
            movie_id = external.movie_id if external else None
        elif year is not None:
            matches = list(db.scalars(select(Movie).where(func.lower(Movie.title) == title.casefold(), Movie.release_year == year).limit(2)))
            if len(matches) == 1:
                movie_id = matches[0].id
            else:
                status, error = "REVIEW_REQUIRED", "No stable Letterboxd identity; confirm the title/year match manually."
        else:
            status, error = "REVIEW_REQUIRED", "No stable Letterboxd identity or release year."
        source_key = hashlib.sha256(f"{kind}|{index}|{uri or ''}|{title or ''}|{year or ''}|{watched_date or ''}".encode()).hexdigest()[:40]
        db.add(MovieImportRow(batch_id=batch.id, user_id=user.id, source_kind=kind, source_row_key=source_key, normalized_json=normalized, status=status, error=error, movie_id=movie_id))
        counts["total"] += 1
        count_key = {"READY": "ready", "REVIEW_REQUIRED": "review_required", "ERROR": "errors"}[status]
        counts[count_key] += 1
    batch.summary_json = counts
    db.flush()
    append_event(db, user, event_type="movie.import_previewed", aggregate_type="movie_import_batch", aggregate_id=batch.id, payload={"batch_id": batch.id, **counts}, outbox=True)
    return batch_read(db, batch)


def confirm_letterboxd(db: Session, user: UserProfile, batch_id: str) -> MovieImportBatchRead:
    batch = db.scalar(select(MovieImportBatch).where(MovieImportBatch.id == batch_id, MovieImportBatch.user_id == user.id).with_for_update())
    if batch is None:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    if batch.status == "CONFIRMED":
        return batch_read(db, batch)
    rows = list(db.scalars(select(MovieImportRow).where(MovieImportRow.batch_id == batch.id).order_by(MovieImportRow.created_at.asc()).with_for_update()))
    imported = skipped = 0
    for row in rows:
        if row.status == "IMPORTED":
            skipped += 1
            continue
        if row.status != "READY":
            continue
        data = row.normalized_json or {}
        movie = db.get(Movie, row.movie_id) if row.movie_id else None
        if movie is None:
            movie, _ = upsert_movie(db, MovieCreate(
                title=data["title"], release_year=data.get("year"), provider="letterboxd",
                external_id=data.get("letterboxd_id"), source_url=data.get("letterboxd_uri"),
            ))
        row.movie_id = movie.id
        source_ref = f"letterboxd:{row.source_row_key}"
        if row.source_kind == "WATCHLIST":
            item = add_watchlist(db, user, WatchlistCreate(movie_id=movie.id, source="letterboxd_export", source_ref=source_ref))
            row.watchlist_item_id = item.id
        else:
            watched_date = _date(data.get("watched_date")) or date.today()
            viewing = log_viewing(db, user, ViewingCreate(
                movie_id=movie.id,
                watched_at=datetime.combine(watched_date, time(hour=12), tzinfo=UTC),
                rating=data.get("rating"),
                rating_scale=5 if data.get("rating") is not None else None,
                source="letterboxd_export",
                source_ref=source_ref,
                idempotency_key=source_ref,
                notes=f"Letterboxd tags: {data['tags']}" if data.get("tags") else None,
            ))
            row.viewing_id = viewing.id
        row.status = "IMPORTED"
        imported += 1
    unresolved = sum(row.status in {"REVIEW_REQUIRED", "ERROR"} for row in rows)
    batch.status = "PARTIAL" if unresolved else "CONFIRMED"
    batch.confirmed_at = utcnow()
    batch.summary_json = {**(batch.summary_json or {}), "imported": imported, "already_imported": skipped, "unresolved": unresolved}
    append_event(db, user, event_type="movie.import_confirmed", aggregate_type="movie_import_batch", aggregate_id=batch.id, payload={"batch_id": batch.id, "imported": imported, "unresolved": unresolved}, outbox=True)
    db.flush()
    return batch_read(db, batch)


def resolve_import_row(db: Session, user: UserProfile, row_id: str, movie_id: str) -> MovieImportRowRead:
    row = db.scalar(select(MovieImportRow).where(MovieImportRow.id == row_id, MovieImportRow.user_id == user.id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Import row not found.")
    if db.get(Movie, movie_id) is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    row.movie_id = movie_id
    row.status = "READY"
    row.error = None
    db.flush()
    return row_read(row)


def batch_read(db: Session, batch: MovieImportBatch) -> MovieImportBatchRead:
    rows = list(db.scalars(select(MovieImportRow).where(MovieImportRow.batch_id == batch.id).order_by(MovieImportRow.created_at.asc())))
    return MovieImportBatchRead(
        id=batch.id, provider=batch.provider, file_name=batch.file_name, status=batch.status,
        summary=batch.summary_json or {}, confirmed_at=batch.confirmed_at, rows=[row_read(row) for row in rows],
    )


def row_read(row: MovieImportRow) -> MovieImportRowRead:
    return MovieImportRowRead(
        id=row.id, source_kind=row.source_kind, source_row_key=row.source_row_key, status=row.status,
        error=row.error, normalized=row.normalized_json or {}, movie_id=row.movie_id,
    )
