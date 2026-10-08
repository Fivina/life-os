from __future__ import annotations

import json
from datetime import date, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.movies.schemas import MetadataMovie, Showtime


class MovieMetadataProviderError(RuntimeError):
    pass


class MovieMetadataProvider(Protocol):
    provider_id: str

    def search(self, query: str, *, year: int | None = None, limit: int = 10) -> list[MetadataMovie]: ...
    def get(self, external_id: str) -> MetadataMovie: ...


class DisabledMovieMetadataProvider:
    provider_id = "disabled"

    def search(self, query: str, *, year: int | None = None, limit: int = 10) -> list[MetadataMovie]:
        return []

    def get(self, external_id: str) -> MetadataMovie:
        raise MovieMetadataProviderError("Movie metadata provider is not configured.")


class TMDBMovieMetadataProvider:
    provider_id = "tmdb"

    def __init__(self, token: str, *, base_url: str = "https://api.themoviedb.org/3", language: str = "en-US", timeout: float = 10.0):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.timeout = timeout

    def search(self, query: str, *, year: int | None = None, limit: int = 10) -> list[MetadataMovie]:
        params = {"query": query, "include_adult": "false", "language": self.language, "page": 1}
        if year is not None:
            params["primary_release_year"] = year
        payload = self._request("/search/movie", params)
        return [self._normalize(item) for item in payload.get("results", [])[:max(1, min(limit, 20))]]

    def get(self, external_id: str) -> MetadataMovie:
        return self._normalize(self._request(f"/movie/{external_id}", {"language": self.language}))

    def _request(self, path: str, params: dict) -> dict:
        request = Request(
            f"{self.base_url}{path}?{urlencode(params)}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MovieMetadataProviderError("Movie metadata provider is temporarily unavailable.") from exc

    def _normalize(self, item: dict) -> MetadataMovie:
        raw_date = item.get("release_date")
        release_date = date.fromisoformat(raw_date) if raw_date else None
        genres = tuple(g["name"] for g in item.get("genres", []) if isinstance(g, dict) and g.get("name"))
        poster_path = item.get("poster_path")
        return MetadataMovie(
            provider=self.provider_id,
            external_id=str(item["id"]),
            title=item.get("title") or item.get("original_title") or "Untitled",
            original_title=item.get("original_title"),
            release_date=release_date,
            runtime_minutes=item.get("runtime"),
            genres=genres,
            overview=item.get("overview") or None,
            poster_url=f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
            source_url=f"https://www.themoviedb.org/movie/{item['id']}",
            provider_rating=item.get("vote_average"),
            provider_vote_count=item.get("vote_count"),
        )


class ShowtimeProvider(Protocol):
    provider_id: str

    def search_showtimes(self, *, movie_title: str, city: str, window_start: datetime, window_end: datetime) -> list[Showtime]: ...


class ManualShowtimeProvider:
    provider_id = "manual"

    def __init__(self, showtimes: list[Showtime] | None = None):
        self.showtimes = showtimes or []

    def search_showtimes(self, *, movie_title: str, city: str, window_start: datetime, window_end: datetime) -> list[Showtime]:
        return [
            item for item in self.showtimes
            if item.city.casefold() == city.casefold() and window_start <= item.starts_at <= window_end
        ]


def metadata_provider(settings: Settings | None = None) -> MovieMetadataProvider:
    config = settings or get_settings()
    if config.movie_metadata_provider.lower() == "tmdb" and config.tmdb_api_token:
        return TMDBMovieMetadataProvider(
            config.tmdb_api_token,
            base_url=config.tmdb_api_base_url,
            language=config.movie_metadata_language,
            timeout=config.movie_metadata_timeout_seconds,
        )
    return DisabledMovieMetadataProvider()
