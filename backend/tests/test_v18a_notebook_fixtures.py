from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.api.deps import get_or_create_user
from app.database.models import Action, Commitment, FixtureBinding, Goal, NotebookEntry, NotebookPromotion, Plan, PlanBlock
from app.notebook.schemas import NotebookEntryCreate
from app.notebook.service import create_entry, search_entries
from app.planning.schemas import PlanGenerateRequest
from app.planning.service import assemble_planning_context
from app.standing_calendar.schemas import NormalizedFixture
from app.standing_calendar.service import ensure_besiktas_rule, override_fixture, reconcile_fixture, sync_rule
from app.standing_calendar.schemas import FixtureOverrideRequest
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 9, 26, 8, tzinfo=UTC)


def fixture(*, fixture_id="9001", status="CONFIRMED", kickoff=None, raw_hash="a"):
    return NormalizedFixture(
        provider="api_football", source_fixture_id=fixture_id, status=status,
        kickoff_at=kickoff if kickoff is not None else NOW + timedelta(days=2),
        home_team="Beşiktaş", away_team="Fenerbahçe", competition="Süper Lig",
        venue="Tüpraş Stadyumu", raw_hash=raw_hash, raw_status="NS",
    )


class FakeProvider:
    provider_id = "api_football"
    def __init__(self, fixtures): self.fixtures = fixtures; self.calls = 0
    def fetch(self, **_): self.calls += 1; return self.fixtures


class FailingProvider:
    provider_id = "api_football"
    def fetch(self, **_):
        from app.standing_calendar.providers import FixtureProviderError
        raise FixtureProviderError("offline")


def test_assistant_parks_idea_without_roadmap_or_planner_mutation(client, db_session):
    response = client.post("/api/v1/assistant/message", headers=AUTH_HEADERS, json={
        "message": "write this down as an implementation idea: Add a quiet weekly review mode",
        "role": "GENERAL_ASSISTANT",
    })
    assert response.status_code == 200
    assert response.json()["model_tier"] == "NO_AI"
    assert "Nothing was added" in response.json()["message"]
    entry = db_session.query(NotebookEntry).one()
    assert entry.entry_type == "IMPLEMENTATION_IDEA"
    assert entry.metadata_json["execution_authority"] == "NONE"
    assert db_session.query(Goal).count() == db_session.query(Action).count() == 0
    assert db_session.query(Commitment).count() == db_session.query(Plan).count() == db_session.query(PlanBlock).count() == 0


def test_notebook_crud_search_fallback_review_and_idempotent_promote(client, db_session, monkeypatch):
    headers = {**AUTH_HEADERS, "Idempotency-Key": "idea-1"}
    body = {"entry_type": "IMPLEMENTATION_IDEA", "title": "Offline capture", "content": "Capture ideas offline", "tags": ["Product"]}
    first = client.post("/api/v1/notebook", headers=headers, json=body)
    second = client.post("/api/v1/notebook", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert db_session.query(NotebookEntry).count() == 1

    from app.memory.embeddings import EmbeddingService
    monkeypatch.setattr(EmbeddingService, "embed", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    results = client.get("/api/v1/notebook/search?q=offline", headers=AUTH_HEADERS)
    assert results.status_code == 200 and results.json()[0]["lexical_score"] > 0
    entry_id = first.json()["id"]
    assert client.post(f"/api/v1/notebook/{entry_id}/review", headers=AUTH_HEADERS).json()["status"] == "REVIEWED"
    promote_headers = {**AUTH_HEADERS, "Idempotency-Key": "promote-1"}
    p1 = client.post(f"/api/v1/notebook/{entry_id}/promote", headers=promote_headers, json={"destination_type": "MANUAL_DEVELOPMENT_REVIEW"})
    p2 = client.post(f"/api/v1/notebook/{entry_id}/promote", headers=promote_headers, json={"destination_type": "MANUAL_DEVELOPMENT_REVIEW"})
    assert p1.json()["id"] == p2.json()["id"]
    assert db_session.query(NotebookPromotion).count() == 1
    assert db_session.query(Action).count() == db_session.query(Goal).count() == 0


def test_fixture_reconciliation_is_idempotent_updates_and_preserves_source_identity(db_session):
    user = get_or_create_user(db_session); rule = ensure_besiktas_rule(db_session, user, now=NOW)
    provider = FakeProvider([fixture()])
    first = sync_rule(db_session, user, rule, provider=provider, now=NOW)
    second = sync_rule(db_session, user, rule, provider=provider, now=NOW + timedelta(minutes=1))
    assert (first.created, second.noop) == (1, 1)
    assert db_session.query(Commitment).count() == db_session.query(FixtureBinding).count() == 1
    binding = db_session.query(FixtureBinding).one(); original_id = binding.commitment_id
    changed = fixture(kickoff=NOW + timedelta(days=3), raw_hash="b")
    result = sync_rule(db_session, user, rule, provider=FakeProvider([changed]), now=NOW + timedelta(minutes=2))
    db_session.refresh(binding)
    assert result.updated == 1 and binding.commitment_id == original_id
    assert db_session.get(Commitment, original_id).starts_at.replace(tzinfo=UTC) == changed.kickoff_at


def test_cancel_postpone_failure_and_explicit_override_are_safe(db_session):
    user = get_or_create_user(db_session); rule = ensure_besiktas_rule(db_session, user, now=NOW)
    sync_rule(db_session, user, rule, provider=FakeProvider([fixture()]), now=NOW)
    binding = db_session.query(FixtureBinding).one(); commitment = db_session.get(Commitment, binding.commitment_id)
    override_fixture(db_session, user, binding.id, FixtureOverrideRequest(protected=False))
    assert commitment.level == "optional" and binding.protection_overridden
    postponed = fixture(status="POSTPONED", kickoff=None, raw_hash="p").model_copy(update={"kickoff_at": None})
    sync_rule(db_session, user, rule, provider=FakeProvider([postponed]), now=NOW + timedelta(hours=1))
    assert commitment.status == "postponed" and commitment.starts_at is None
    before = commitment.version
    failed = sync_rule(db_session, user, rule, provider=FailingProvider(), now=NOW + timedelta(hours=2))
    assert failed.status == "FAILED" and commitment.version == before
    cancelled = fixture(status="CANCELLED", raw_hash="c")
    sync_rule(db_session, user, rule, provider=FakeProvider([cancelled]), now=NOW + timedelta(hours=3))
    assert commitment.status == "cancelled"


def test_confirmed_fixture_is_protected_planner_commitment_until_override(db_session):
    user = get_or_create_user(db_session); rule = ensure_besiktas_rule(db_session, user, now=NOW)
    match = fixture(kickoff=NOW + timedelta(hours=2))
    sync_rule(db_session, user, rule, provider=FakeProvider([match]), now=NOW)
    context = assemble_planning_context(db_session, user, PlanGenerateRequest(planning_date=NOW.date(), timezone="UTC", horizon_start=NOW, horizon_end=NOW + timedelta(hours=12)))
    assert len(context.hard_commitments) == 1
    binding = db_session.query(FixtureBinding).one()
    override_fixture(db_session, user, binding.id, FixtureOverrideRequest(protected=False))
    context = assemble_planning_context(db_session, user, PlanGenerateRequest(planning_date=NOW.date(), timezone="UTC", horizon_start=NOW, horizon_end=NOW + timedelta(hours=12)))
    assert context.hard_commitments == []


def test_direct_notebook_save_enqueues_embedding_without_blocking(db_session):
    user = get_or_create_user(db_session)
    row = create_entry(db_session, user, NotebookEntryCreate(title="A", content="B"), idempotency_key="x")
    assert row.embedding_vector is None
    assert search_entries(db_session, user, "B")
