from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.api.deps import get_or_create_user
from app.database.models import Commitment, FixtureBinding
from app.standing_calendar.providers import normalize_api_football
from app.standing_calendar.schemas import NormalizedFixture
from app.standing_calendar.service import ensure_besiktas_rule, reconcile_fixture
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 10, 3, 8, tzinfo=UTC)
HOME_LOGO = "https://media.api-sports.io/football/teams/549.png"
AWAY_LOGO = "https://media.api-sports.io/football/teams/611.png"


def provider_fixture():
    return {
        "fixture": {"id": 9001, "date": "2026-10-04T18:00:00+00:00", "status": {"short": "NS"}},
        "teams": {
            "home": {"id": 549, "name": "Beşiktaş", "logo": HOME_LOGO},
            "away": {"id": 611, "name": "Fenerbahçe", "logo": AWAY_LOGO},
        },
        "league": {"name": "Süper Lig"},
    }


def test_source_team_logos_are_preserved_without_changing_fixture_identity():
    raw = provider_fixture()
    original = deepcopy(raw)
    normalized = normalize_api_football(raw)
    assert raw == original
    assert normalized.source_fixture_id == "9001"
    assert normalized.home_team == "Beşiktaş"
    assert normalized.away_team == "Fenerbahçe"
    assert normalized.home_team_logo_url == HOME_LOGO
    assert normalized.away_team_logo_url == AWAY_LOGO


@pytest.mark.parametrize("logo", [
    None, "", 123, {}, "/teams/549.png", "//media.api-sports.io/549.png",
    "javascript:alert(1)", "data:image/png;base64,AAAA", "file:///C:/badge.png",
    "https://user:secret@example.com/badge.png", "https:example.com/badge.png",
    "https://", "https://example.com/a b.png", "https://example.com/a\nb.png",
])
def test_invalid_optional_logo_does_not_drop_an_otherwise_valid_match(logo):
    raw = provider_fixture()
    raw["teams"]["home"]["logo"] = logo
    normalized = normalize_api_football(raw)
    assert normalized.home_team_logo_url is None
    assert normalized.away_team_logo_url == AWAY_LOGO
    assert normalized.kickoff_at == datetime(2026, 10, 4, 18, tzinfo=UTC)


def test_provider_without_artwork_keeps_default_name_and_logo_fallbacks():
    raw = provider_fixture()
    raw["teams"] = {"home": None, "away": {"name": "Visitor"}}
    normalized = normalize_api_football(raw)
    assert normalized.home_team == "Home"
    assert normalized.away_team == "Visitor"
    assert normalized.home_team_logo_url is normalized.away_team_logo_url is None
    data = normalized.model_dump(exclude={"home_team_logo_url", "away_team_logo_url"})
    data["provider"] = "another_provider"
    other = NormalizedFixture(**data)
    assert other.home_team_logo_url is other.away_team_logo_url is None


def test_existing_fixture_backfills_logos_and_exposes_them_without_rescheduling(client, db_session):
    user = get_or_create_user(db_session)
    rule = ensure_besiktas_rule(db_session, user, now=NOW)
    normalized = normalize_api_football(provider_fixture())
    assert reconcile_fixture(db_session, user, rule, normalized, now=NOW) == "created"
    binding = db_session.query(FixtureBinding).one()
    commitment = db_session.get(Commitment, binding.commitment_id)
    original_commitment = (commitment.id, commitment.version, commitment.starts_at, commitment.ends_at)
    legacy = dict(binding.normalized_json)
    legacy.pop("home_team_logo_url")
    legacy.pop("away_team_logo_url")
    binding.normalized_json = legacy
    binding_version = binding.version
    db_session.commit()

    assert reconcile_fixture(db_session, user, rule, normalized, now=NOW) == "noop"
    assert binding.version == binding_version + 1
    assert (commitment.id, commitment.version, commitment.starts_at, commitment.ends_at) == original_commitment
    assert reconcile_fixture(db_session, user, rule, normalized, now=NOW) == "noop"
    assert binding.version == binding_version + 1
    db_session.commit()

    response = client.get(f"/api/v1/standing-calendar-rules/{rule.id}/fixtures", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()[0]["normalized_json"]["home_team_logo_url"] == HOME_LOGO
    assert response.json()[0]["normalized_json"]["away_team_logo_url"] == AWAY_LOGO
