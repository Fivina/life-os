from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.core.config import Settings
from app.standing_calendar.schemas import NormalizedFixture


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Provider keys must not be forwarded to redirects or environment proxies.
urlopen = build_opener(ProxyHandler({}), _NoRedirect()).open
MAX_RESPONSE_BYTES = 256 * 1024


class FixtureProviderError(RuntimeError):
    def __init__(self, message: str, *, transient: bool = False):
        super().__init__(message)
        self.transient = transient


class FixtureProvider(Protocol):
    provider_id: str
    def fetch(self, *, team_id: str) -> list[NormalizedFixture]: ...


STATUS_MAP = {
    "TBD": "SCHEDULED", "NS": "SCHEDULED",
    "1H": "CONFIRMED", "HT": "CONFIRMED", "2H": "CONFIRMED", "ET": "CONFIRMED",
    "BT": "CONFIRMED", "P": "CONFIRMED", "INT": "CONFIRMED", "LIVE": "CONFIRMED",
    "PST": "POSTPONED", "SUSP": "POSTPONED", "CANC": "CANCELLED", "ABD": "CANCELLED", "AWD": "COMPLETED", "WO": "COMPLETED",
    "FT": "COMPLETED", "AET": "COMPLETED", "PEN": "COMPLETED",
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value: return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise FixtureProviderError("Provider returned a timezone-naive kickoff.")
    return parsed.astimezone(UTC)


def normalize_api_football(raw: dict) -> NormalizedFixture:
    fixture = raw.get("fixture") or {}; teams = raw.get("teams") or {}; league = raw.get("league") or {}
    home = teams.get("home"); away = teams.get("away")
    home = home if isinstance(home, dict) else {}
    away = away if isinstance(away, dict) else {}
    raw_status = str((fixture.get("status") or {}).get("short") or "TBD").upper()
    if raw_status not in STATUS_MAP:
        raise FixtureProviderError("Unsupported fixture status.")
    status = STATUS_MAP[raw_status]
    kickoff = _parse_datetime(fixture.get("date"))
    if status == "POSTPONED" and raw_status == "PST" and not fixture.get("date"):
        kickoff = None
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    return NormalizedFixture(
        provider="api_football", source_fixture_id=str(fixture["id"]), status=status,
        kickoff_at=kickoff, home_team=str(home.get("name") or "Home"),
        away_team=str(away.get("name") or "Away"),
        home_team_logo_url=home.get("logo"), away_team_logo_url=away.get("logo"),
        competition=league.get("name"), venue=(fixture.get("venue") or {}).get("name"),
        source_updated_at=_parse_datetime(fixture.get("timestamp_updated") or fixture.get("updated_at")),
        raw_hash=hashlib.sha256(canonical.encode()).hexdigest(), raw_status=raw_status,
    )


class ApiFootballFixtureProvider:
    provider_id = "api_football"
    max_attempts = 3
    retry_backoff_seconds = 0.25

    def __init__(self, settings: Settings): self.settings = settings

    def fetch(
        self,
        *,
        team_id: str,
        # Retained as ignored keyword arguments for callers upgrading from the
        # former date-window adapter. The provider request is always next=1.
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[NormalizedFixture]:
        if not self.settings.api_football_api_key:
            raise FixtureProviderError("API_FOOTBALL_API_KEY is not configured.")
        query = urlencode({"team": team_id, "next": 1, "timezone": "UTC"})
        request = Request(f"{self.settings.api_football_base_url.rstrip('/')}/fixtures?{query}", headers={"x-apisports-key": self.settings.api_football_api_key})
        payload = None
        for attempt in range(self.max_attempts):
            try:
                with urlopen(request, timeout=self.settings.fixture_sync_timeout_seconds) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise FixtureProviderError("Fixture provider response exceeded the size limit.")
                    payload = json.loads(body.decode("utf-8"))
                break
            except HTTPError as exc:
                transient = exc.code in {408, 429} or 500 <= exc.code < 600
                if not transient or attempt + 1 == self.max_attempts:
                    raise FixtureProviderError(
                        f"Fixture provider request failed with HTTP {exc.code}.", transient=transient
                    ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt + 1 == self.max_attempts:
                    raise FixtureProviderError("Fixture provider request failed.", transient=True) from exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise FixtureProviderError("Fixture provider returned an invalid response.") from exc
            time.sleep(self.retry_backoff_seconds * (2 ** attempt))
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), list):
            raise FixtureProviderError("Fixture provider returned an invalid response.")
        if payload.get("errors"):
            raise FixtureProviderError("Fixture provider returned an error response.")
        fixtures = [normalize_api_football(item) for item in payload.get("response", [])[:1]]
        for fixture in fixtures:
            names = {fixture.home_team.casefold(), fixture.away_team.casefold()}
            if not any("beşiktaş" in name or "besiktas" in name for name in names):
                raise FixtureProviderError("Provider team identity validation failed for Beşiktaş.")
        return fixtures


def configured_provider(settings: Settings) -> FixtureProvider:
    if settings.fixture_provider == "api_football": return ApiFootballFixtureProvider(settings)
    raise FixtureProviderError(f"Unsupported fixture provider: {settings.fixture_provider}")
