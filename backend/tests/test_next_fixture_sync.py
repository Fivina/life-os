from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from app.api.deps import get_or_create_user
from app.core.config import Settings
from app.database.models import Commitment, FixtureBinding
from app.standing_calendar.providers import ApiFootballFixtureProvider, FixtureProviderError, normalize_api_football
from app.standing_calendar.schemas import NormalizedFixture
from app.standing_calendar.service import ensure_besiktas_rule, sync_rule
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


class JsonResponse:
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def raw_fixture(*, fixture_id: int = 9001, kickoff: datetime | None = None) -> dict:
    kickoff = kickoff or NOW + timedelta(days=30)
    return {
        "fixture": {"id": fixture_id, "date": kickoff.isoformat(), "status": {"short": "NS"}},
        "teams": {
            "home": {"id": 549, "name": "Beşiktaş"},
            "away": {"id": 611, "name": "Fenerbahçe"},
        },
        "league": {"name": "Süper Lig"},
    }


def normalized_fixture(*, fixture_id: str = "9001", kickoff: datetime | None = None, raw_hash: str = "a"):
    return NormalizedFixture(
        provider="api_football",
        source_fixture_id=fixture_id,
        status="SCHEDULED",
        kickoff_at=kickoff or NOW + timedelta(days=30),
        home_team="Beşiktaş",
        away_team="Fenerbahçe",
        competition="Süper Lig",
        raw_hash=raw_hash,
        raw_status="NS",
    )


class RecordingProvider:
    provider_id = "api_football"

    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.calls = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return self.fixtures


def provider_settings() -> Settings:
    return Settings(_env_file=None, api_football_api_key="test-key")


def test_api_football_requests_team_next_one_without_date_window(monkeypatch):
    requests = []

    def fake_urlopen(request, *, timeout):
        requests.append((request, timeout))
        return JsonResponse({"response": [raw_fixture()]})

    monkeypatch.setattr("app.standing_calendar.providers.urlopen", fake_urlopen)
    provider = ApiFootballFixtureProvider(provider_settings())

    fixtures = provider.fetch(team_id="549", from_date="2026-10-08", to_date="2026-10-22")

    assert len(fixtures) == 1
    query = parse_qs(urlparse(requests[0][0].full_url).query)
    assert query == {"team": ["549"], "next": ["1"], "timezone": ["UTC"]}
    assert "from" not in query and "to" not in query


def test_provider_defensively_keeps_only_one_next_fixture(monkeypatch):
    monkeypatch.setattr(
        "app.standing_calendar.providers.urlopen",
        lambda *_args, **_kwargs: JsonResponse({"response": [raw_fixture(), raw_fixture(fixture_id=9002)]}),
    )

    fixtures = ApiFootballFixtureProvider(provider_settings()).fetch(team_id="549")

    assert [fixture.source_fixture_id for fixture in fixtures] == ["9001"]


def test_provider_normalizes_next_fixture_with_unconfirmed_tbd_kickoff():
    raw = raw_fixture()
    raw["fixture"]["date"] = None
    raw["fixture"]["status"]["short"] = "TBD"

    fixture = normalize_api_football(raw)

    assert fixture.status == "SCHEDULED"
    assert fixture.raw_status == "TBD"
    assert fixture.kickoff_at is None


def test_transient_retries_are_bounded_with_backoff(monkeypatch):
    attempts = []
    sleeps = []

    def unavailable(*_args, **_kwargs):
        attempts.append(None)
        raise URLError("offline")

    monkeypatch.setattr("app.standing_calendar.providers.urlopen", unavailable)
    monkeypatch.setattr("app.standing_calendar.providers.time.sleep", sleeps.append)

    with pytest.raises(FixtureProviderError) as caught:
        ApiFootballFixtureProvider(provider_settings()).fetch(team_id="549")

    assert caught.value.transient is True
    assert len(attempts) == 3
    assert sleeps == [0.25, 0.5]


def test_non_transient_http_error_is_not_retried(monkeypatch):
    attempts = []

    def bad_request(request, **_kwargs):
        attempts.append(None)
        raise HTTPError(request.full_url, 400, "bad request", {}, BytesIO())

    monkeypatch.setattr("app.standing_calendar.providers.urlopen", bad_request)
    monkeypatch.setattr(
        "app.standing_calendar.providers.time.sleep",
        lambda *_: pytest.fail("permanent failures must not be retried"),
    )

    with pytest.raises(FixtureProviderError) as caught:
        ApiFootballFixtureProvider(provider_settings()).fetch(team_id="549")

    assert caught.value.transient is False
    assert len(attempts) == 1


def test_existing_rule_upgrades_to_daily_next_fixture_sync(db_session):
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)
    rule.next_sync_at = NOW + timedelta(days=14)
    rule.source_config_json = {"team_id": "549", "team_name": "Beşiktaş", "lookahead_days": 14}
    rule.metadata_json = {"team_identity_verified_at": "2026-09-26"}
    version = rule.version
    db_session.flush()

    upgraded = ensure_besiktas_rule(db_session, user, now=NOW + timedelta(hours=1))

    assert upgraded.id == rule.id
    assert upgraded.sync_interval_days == 1
    assert upgraded.next_sync_at == NOW + timedelta(hours=1)
    assert upgraded.source_config_json == {"team_id": "549", "team_name": "Beşiktaş", "next": 1}
    assert upgraded.metadata_json["fixture_sync_mode"] == "NEXT_FIXTURE"
    assert upgraded.version == version + 1


def test_fixture_beyond_fourteen_days_is_synced_and_rescheduled_idempotently(db_session):
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)
    first_kickoff = NOW + timedelta(days=30)
    provider = RecordingProvider([normalized_fixture(kickoff=first_kickoff)])

    first = sync_rule(db_session, user, rule, provider=provider, now=NOW)
    second = sync_rule(db_session, user, rule, provider=provider, now=NOW + timedelta(minutes=1))
    binding = db_session.query(FixtureBinding).one()
    commitment_id = binding.commitment_id

    moved_kickoff = first_kickoff + timedelta(days=2)
    moved = sync_rule(
        db_session,
        user,
        rule,
        provider=RecordingProvider([normalized_fixture(kickoff=moved_kickoff, raw_hash="b")]),
        now=NOW + timedelta(minutes=2),
    )

    db_session.refresh(binding)
    commitment = db_session.get(Commitment, commitment_id)
    assert (first.created, second.noop, moved.updated) == (1, 1, 1)
    assert provider.calls == [{"team_id": "549"}, {"team_id": "549"}]
    assert db_session.query(FixtureBinding).count() == db_session.query(Commitment).count() == 1
    assert binding.commitment_id == commitment_id
    assert commitment.starts_at.replace(tzinfo=UTC) == moved_kickoff
    assert rule.next_sync_at == NOW + timedelta(minutes=2, days=1)
    assert rule.metadata_json["current_next_fixture_id"] == "9001"


def test_successful_empty_response_clears_pointer_without_deleting_cached_fixture(db_session):
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)
    sync_rule(db_session, user, rule, provider=RecordingProvider([normalized_fixture()]), now=NOW)
    binding = db_session.query(FixtureBinding).one()
    commitment_id = binding.commitment_id

    result = sync_rule(db_session, user, rule, provider=RecordingProvider([]), now=NOW + timedelta(days=1))

    assert result.status == "SUCCESS" and result.fetched == 0
    assert rule.metadata_json["fixture_sync_mode"] == "NEXT_FIXTURE"
    assert rule.metadata_json["current_next_fixture_id"] is None
    assert db_session.get(FixtureBinding, binding.id) is not None
    assert db_session.get(Commitment, commitment_id) is not None


def test_provider_failure_retains_last_successful_next_fixture_pointer(db_session):
    class FailingProvider:
        provider_id = "api_football"

        def fetch(self, **_kwargs):
            raise FixtureProviderError("temporary", transient=True)

    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)
    sync_rule(db_session, user, rule, provider=RecordingProvider([normalized_fixture()]), now=NOW)

    result = sync_rule(db_session, user, rule, provider=FailingProvider(), now=NOW + timedelta(hours=1))

    assert result.status == "FAILED"
    assert rule.metadata_json["current_next_fixture_id"] == "9001"


def test_typed_rule_projection_distinguishes_unknown_failure_and_known_empty(client, db_session):
    class FailingProvider:
        provider_id = "api_football"

        def fetch(self, **_kwargs):
            raise FixtureProviderError("temporary", transient=True)

    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)

    initial = client.get(f"/api/v1/standing-calendar-rules/{rule.id}", headers=AUTH_HEADERS).json()
    assert initial["next_fixture_selection_known"] is False
    assert initial["current_next_fixture_id"] is None

    sync_rule(db_session, user, rule, provider=RecordingProvider([normalized_fixture()]), now=NOW)
    selected = client.get(f"/api/v1/standing-calendar-rules/{rule.id}", headers=AUTH_HEADERS).json()
    assert selected["next_fixture_selection_known"] is True
    assert selected["current_next_fixture_id"] == "9001"

    sync_rule(db_session, user, rule, provider=FailingProvider(), now=NOW + timedelta(hours=1))
    failed = client.get(f"/api/v1/standing-calendar-rules/{rule.id}", headers=AUTH_HEADERS).json()
    assert failed["next_fixture_selection_known"] is True
    assert failed["current_next_fixture_id"] == "9001"

    sync_rule(db_session, user, rule, provider=RecordingProvider([]), now=NOW + timedelta(days=1))
    empty = client.get(f"/api/v1/standing-calendar-rules/{rule.id}", headers=AUTH_HEADERS).json()
    assert empty["next_fixture_selection_known"] is True
    assert empty["current_next_fixture_id"] is None


@pytest.mark.parametrize(
    ("error", "expected_delay"),
    [
        (FixtureProviderError("temporary", transient=True), timedelta(hours=6)),
        (FixtureProviderError("configuration", transient=False), timedelta(days=1)),
    ],
)
def test_service_schedules_fast_retry_only_for_transient_provider_failures(db_session, error, expected_delay):
    class FailingProvider:
        provider_id = "api_football"

        def fetch(self, **_kwargs):
            raise error

    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)

    result = sync_rule(db_session, user, rule, provider=FailingProvider(), now=NOW)

    assert result.status == "FAILED"
    assert rule.next_sync_at == NOW + expected_delay
    assert db_session.query(FixtureBinding).count() == db_session.query(Commitment).count() == 0
