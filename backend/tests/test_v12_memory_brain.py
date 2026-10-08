from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.ai.gateway import AIGateway
from app.ai.providers import GeminiProvider
from app.ai.types import AIEmbeddingRequest
from app.api.deps import get_or_create_user
from app.assistant.context_builder import ContextBuilderV1
from app.assistant.schemas import AssistantRole
from app.assistant.tools import ToolRegistry
from app.conversations.service import ConversationService
from app.core.config import Settings
from app.database.models import (
    AIActionAudit,
    Episode,
    Event,
    MemoryEvidence,
    MemoryItem,
    MemoryProcessingJob,
    MemorySuppression,
    PatternEvidence,
    Recommendation,
    RecommendationOption,
    RecommendationOutcome,
    UserProfile,
)
from app.events.service import append_event
from app.memory.confidence import effective_confidence
from app.memory.consolidation import MemoryConsolidator
from app.memory.embeddings import EmbeddingService
from app.memory.jobs import MemoryJobProcessor
from app.memory.retrieval import MemoryRetrievalService
from app.memory.schemas import MemoryCandidate, MemoryCreate, MemoryUpdate, RecommendationCreate, RecommendationOptionCreate, RecommendationOutcomeCreate
from app.memory.service import MemoryService
from app.recommendations import service as recommendation_service
from app.skills.registry import SkillRegistry
from tests.conftest import AUTH_HEADERS


def _services():
    settings = Settings(database_url="sqlite://", ai_provider="fake")
    gateway = AIGateway(settings)
    embeddings = EmbeddingService(settings, gateway)
    return settings, MemoryService(embeddings), MemoryRetrievalService(settings, embeddings), MemoryConsolidator(settings, embeddings)


def test_embedding_gateway_routes_and_audits(db_session):
    user = get_or_create_user(db_session)
    settings, _, _, _ = _services()
    response = EmbeddingService(settings, AIGateway(settings)).embed(
        db_session,
        user,
        ["morning strength training"],
        task_type="RETRIEVAL_DOCUMENT",
        request_id="embedding-test",
    )
    assert len(response.vectors) == 1
    assert len(response.vectors[0]) == settings.embedding_dimensions
    audit = db_session.scalar(select(AIActionAudit).where(AIActionAudit.request_id == "embedding-test"))
    assert audit.capability == "EMBEDDING"
    assert audit.model == settings.ai_model_embedding


def test_gemini_embedding_payload_and_normalization(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"embeddings": [{"values": [2.0] * 128}], "usageMetadata": {"inputTokenCount": 4}}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["body"] = kwargs["json"]
        return Response()

    monkeypatch.setattr("app.ai.providers.httpx.post", fake_post)
    response = GeminiProvider(api_key="test-only").embed(
        model="gemini-embedding-001",
        request=AIEmbeddingRequest(texts=["hello memory"], dimensions=128, task_type="RETRIEVAL_DOCUMENT"),
    )
    item = captured["body"]["requests"][0]
    assert captured["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert item["embedContentConfig"] == {"outputDimensionality": 128, "taskType": "RETRIEVAL_DOCUMENT"}
    assert abs(sum(value * value for value in response.vectors[0]) - 1.0) < 0.000001


def test_memory_merge_confidence_and_no_world_revision(db_session):
    user = get_or_create_user(db_session)
    _, service, _, _ = _services()
    revision = user.world_revision
    candidate = MemoryCandidate(content="I prefer morning workouts", normalized_key="morning workouts", domain="fitness", polarity=1, explicit=True)
    first = service.remember(
        db_session,
        user,
        candidate,
        source_type="conversation_message",
        source_id="message-1",
        source_kind="explicit_user",
        evidence_kind="user_statement",
        user_confirmed=True,
    )
    second = service.remember(
        db_session,
        user,
        candidate,
        source_type="conversation_message",
        source_id="message-2",
        source_kind="explicit_user",
        evidence_kind="user_statement",
        user_confirmed=True,
    )
    assert first.id == second.id
    assert second.status == "active"
    assert second.confidence >= 0.92
    assert db_session.query(MemoryEvidence).filter_by(memory_id=first.id).count() == 2
    assert user.world_revision == revision


def test_pinned_memory_survives_contradiction(db_session):
    user = get_or_create_user(db_session)
    _, service, _, _ = _services()
    positive = service.create_explicit(
        db_session,
        user,
        MemoryCreate(content="I like late workouts", domain="fitness", polarity=1, pinned=True),
    )
    service.remember(
        db_session,
        user,
        MemoryCandidate(content="Late workouts are good", normalized_key=positive.normalized_key, domain="fitness", polarity=1, explicit=True),
        source_type="conversation_message",
        source_id="message-reinforcement",
        source_kind="explicit_user",
        evidence_kind="user_statement",
        user_confirmed=True,
    )
    assert db_session.get(MemoryItem, positive.id).content == "I like late workouts"
    replacement = service.remember(
        db_session,
        user,
        MemoryCandidate(content="I dislike late workouts", normalized_key=positive.normalized_key, domain="fitness", polarity=-1, explicit=True),
        source_type="conversation_message",
        source_id="message-contradiction",
        source_kind="explicit_user",
        evidence_kind="user_statement",
        user_confirmed=True,
    )
    original = db_session.get(MemoryItem, positive.id)
    assert original.status == "active"
    assert original.pinned is True
    assert replacement.status == "uncertain"
    assert replacement.supersedes_memory_id == original.id


def test_retrieval_is_bounded_and_forgetting_excludes_memory(db_session):
    user = get_or_create_user(db_session)
    settings, service, retrieval, _ = _services()
    created = []
    for index in range(9):
        created.append(service.create_explicit(db_session, user, MemoryCreate(content=f"I prefer workout routine {index}", domain="fitness", polarity=1)))
    results = retrieval.search_memories(db_session, user, "preferred workout routine", domain="fitness", limit=20)
    assert 0 < len(results) <= settings.memory_retrieval_limit
    forgotten = created[0]
    service.forget(db_session, user, forgotten.id)
    assert all(item.memory.id != forgotten.id for item in retrieval.search_memories(db_session, user, "workout routine", domain="fitness"))


def test_confirmed_memory_ages_conservatively(db_session):
    user = get_or_create_user(db_session)
    _, service, _, _ = _services()
    created = service.create_explicit(db_session, user, MemoryCreate(content="I prefer concise answers"))
    memory = db_session.get(MemoryItem, created.id)
    memory.last_observed_at = datetime.now(UTC) - timedelta(days=2000)
    memory.last_confirmed_at = memory.last_observed_at
    assert effective_confidence(memory) >= memory.confidence * 0.72
    memory.pinned = True
    assert effective_confidence(memory) == 1.0


def test_assistant_curates_explicit_memory_but_not_transient_state(client, db_session):
    first = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "I prefer morning workouts.", "role": "GENERAL_ASSISTANT", "timezone": "UTC"},
    )
    assert first.status_code == 200
    assert db_session.query(MemoryProcessingJob).filter_by(status="pending").count() == 1
    MemoryJobProcessor(Settings(database_url="sqlite://", ai_provider="fake")).process_pending(db_session)
    memories = client.get("/api/v1/memories", headers=AUTH_HEADERS)
    assert memories.status_code == 200
    assert any("morning workouts" in item["content"].lower() for item in memories.json())

    second = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "My workout is at 18:00 today.", "role": "GENERAL_ASSISTANT", "timezone": "UTC"},
    )
    assert second.status_code == 200
    assert db_session.query(MemoryItem).count() == 1


def test_context_separates_memory_from_canonical_state(db_session):
    user = get_or_create_user(db_session)
    settings, service, retrieval, _ = _services()
    service.create_explicit(db_session, user, MemoryCreate(content="I prefer vegetarian dinners", domain="kitchen", polarity=1))
    tools = ToolRegistry()
    skills = SkillRegistry(settings, tools).load()
    conversations = ConversationService(settings)
    thread = conversations.create_thread(db_session, user, title="Memory context", default_skill="chef")
    bundle = ContextBuilderV1(settings, skills, tools, conversations, retrieval).build(
        db_session,
        user,
        role="CHEF",
        skill=skills.get("chef"),
        thread=thread,
        user_request="What dinner should I make?",
        now=datetime.now(UTC),
        timezone="UTC",
        request_id="context-memory",
    )
    assert "semantic_memory" in bundle.dynamic_context
    assert "canonical" in bundle.dynamic_context
    assert bundle.dynamic_context["semantic_memory"]["authority"].startswith("personal recollection")


def test_consolidation_creates_bounded_episode_without_revision_change(db_session):
    user = get_or_create_user(db_session)
    settings, _, _, consolidator = _services()
    settings.memory_consolidation_event_threshold = 3
    start = datetime.now(UTC) - timedelta(hours=2)
    for index in range(3):
        append_event(
            db_session,
            user,
            event_type="fitness.workout.completed",
            aggregate_type="workout_session",
            aggregate_id=f"session-{index}",
            payload={"domain": "fitness"},
            outbox=False,
        )
    db_session.flush()
    before = user.world_revision
    result = consolidator.consolidate_user(db_session, user, period_start=start, period_end=datetime.now(UTC) + timedelta(seconds=1))
    assert result.status == "completed"
    assert result.source_event_count == 3
    assert db_session.query(Episode).count() == 1
    assert user.world_revision == before


def test_memory_api_supports_pin_correct_and_forget(client):
    created = client.post(
        "/api/v1/memories",
        headers=AUTH_HEADERS,
        json={"content": "I prefer quiet study sessions", "domain": "learning", "polarity": 1},
    )
    assert created.status_code == 200
    memory_id = created.json()["id"]
    pinned = client.post(f"/api/v1/memories/{memory_id}/pin", headers=AUTH_HEADERS)
    assert pinned.status_code == 200
    assert pinned.json()["pinned"] is True
    corrected = client.patch(
        f"/api/v1/memories/{memory_id}",
        headers=AUTH_HEADERS,
        json={"content": "I prefer silent study sessions", "expected_version": pinned.json()["version"]},
    )
    assert corrected.status_code == 200
    corrected_id = corrected.json()["id"]
    assert corrected_id != memory_id
    forgotten = client.post(f"/api/v1/memories/{corrected_id}/forget", headers=AUTH_HEADERS)
    assert forgotten.status_code == 200
    assert forgotten.json()["status"] == "forgotten"
    assert client.get("/api/v1/memories", headers=AUTH_HEADERS).json() == []


def test_memory_export_keeps_provenance_but_omits_raw_vectors(client):
    created = client.post(
        "/api/v1/memories",
        headers=AUTH_HEADERS,
        json={"content": "I prefer focused morning planning", "domain": "planning", "polarity": 1},
    )
    assert created.status_code == 200
    exported = client.get("/api/v1/export", headers=AUTH_HEADERS)
    assert exported.status_code == 200
    tables = exported.json()["tables"]
    assert tables["memory_items"][0]["content"] == "I prefer focused morning planning"
    assert "embedding_vector" not in tables["memory_items"][0]
    assert tables["memory_evidence"][0]["memory_id"] == created.json()["id"]


def test_semantic_memory_policy_rejects_canonical_and_transient_facts(client):
    canonical = client.post(
        "/api/v1/memories",
        headers=AUTH_HEADERS,
        json={"content": "I have 3 eggs", "domain": "kitchen", "memory_type": "personal_fact"},
    )
    assert canonical.status_code == 422
    assert canonical.json()["detail"]["reason"] == "canonical_state"

    transient = client.post(
        "/api/v1/memories",
        headers=AUTH_HEADERS,
        json={"content": "I am tired today", "domain": "general", "memory_type": "personal_fact"},
    )
    assert transient.status_code == 422
    assert transient.json()["detail"]["reason"] == "transient_state"


def test_forgotten_source_is_suppressed_and_does_not_resurrect(db_session):
    user = get_or_create_user(db_session)
    _, service, retrieval, _ = _services()
    candidate = MemoryCandidate(
        content="I dislike olives",
        normalized_key="olives",
        domain="kitchen",
        polarity=-1,
        explicit=True,
    )
    memory = service.remember(
        db_session,
        user,
        candidate,
        source_type="conversation_message",
        source_id="message-olives",
        source_kind="explicit_user",
        evidence_kind="user_statement",
        user_confirmed=True,
    )
    service.forget(db_session, user, memory.id)
    assert db_session.query(MemorySuppression).filter_by(user_id=user.id, source_id="message-olives").count() == 1
    with pytest.raises(HTTPException) as exc:
        service.remember(
            db_session,
            user,
            candidate,
            source_type="conversation_message",
            source_id="message-olives",
            source_kind="explicit_user",
            evidence_kind="user_statement",
            user_confirmed=True,
        )
    assert exc.value.status_code == 409
    assert retrieval.search_memories(db_session, user, "olives", domain="kitchen") == []


def test_user_correction_supersedes_old_memory_and_future_retrieval(db_session):
    user = get_or_create_user(db_session)
    _, service, retrieval, _ = _services()
    old = service.create_explicit(db_session, user, MemoryCreate(content="I dislike olives", domain="kitchen", polarity=-1))
    corrected = service.update(
        db_session,
        user,
        old.id,
        payload=MemoryUpdate(
            content="Actually I like olives now",
            polarity=1,
            expected_version=old.version,
        ),
        request_id="correct-olives",
    )
    previous = db_session.get(MemoryItem, old.id)
    assert corrected.id != old.id
    assert corrected.supersedes_memory_id == old.id
    assert previous.status == "contradicted"
    results = retrieval.search_memories(db_session, user, "olives", domain="kitchen")
    assert any(item.memory.id == corrected.id for item in results)
    assert all(item.memory.id != old.id for item in results)


def test_retrieval_filters_domain_type_and_user(db_session):
    user = get_or_create_user(db_session)
    other = UserProfile(email="other-memory@example.test", display_name="Other")
    db_session.add(other)
    db_session.flush()
    _, service, retrieval, _ = _services()
    kitchen = service.create_explicit(
        db_session,
        user,
        MemoryCreate(content="I prefer spicy dinners", domain="kitchen", memory_type="domain_preference", importance=0.9, pinned=True),
    )
    service.create_explicit(db_session, user, MemoryCreate(content="I prefer quiet study", domain="learning", memory_type="domain_preference"))
    service.create_explicit(db_session, other, MemoryCreate(content="I prefer spicy dinners too", domain="kitchen", memory_type="domain_preference"))
    results = retrieval.search_memories(
        db_session,
        user,
        "spicy dinner preference",
        domains=["kitchen"],
        memory_types=["domain_preference"],
        limit=20,
    )
    assert results[0].memory.id == kitchen.id
    assert all(item.memory.domain in {"kitchen", "general", "global"} for item in results)
    assert all(db_session.get(MemoryItem, item.memory.id).user_id == user.id for item in results)


def test_recommendation_options_outcomes_events_and_user_scope(db_session):
    user = get_or_create_user(db_session)
    other = UserProfile(email="other-recommendation@example.test", display_name="Other")
    db_session.add(other)
    db_session.flush()
    created = recommendation_service.create_recommendation(
        db_session,
        user,
        RecommendationCreate(
            domain="kitchen",
            kind="meal",
            title="Dinner options",
            idempotency_key="dinner-1",
            options=[
                RecommendationOptionCreate(label="Teriyaki", rank=1, score=0.9),
                RecommendationOptionCreate(label="Pasta", rank=2, score=0.8),
            ],
        ),
    )
    replay = recommendation_service.create_recommendation(
        db_session,
        user,
        RecommendationCreate(domain="kitchen", kind="meal", title="Duplicate", idempotency_key="dinner-1"),
    )
    assert replay.id == created.id
    assert db_session.query(RecommendationOption).filter_by(recommendation_id=created.id).count() == 2
    outcome = recommendation_service.record_outcome(
        db_session,
        user,
        RecommendationOutcomeCreate(
            recommendation_id=created.id,
            option_id=created.options[0].id,
            domain="kitchen",
            recommendation_type="meal",
            recommendation_summary="Teriyaki",
            outcome="accepted",
            idempotency_key="dinner-outcome-1",
        ),
    )
    assert outcome.accepted is True
    assert db_session.query(MemoryProcessingJob).filter_by(source_id=outcome.id).count() == 1
    assert any(event.event_type == "recommendation.accepted" for event in db_session.query(Event).all())
    with pytest.raises(HTTPException):
        recommendation_service.get_recommendation(db_session, other, created.id)


def test_memory_jobs_are_idempotent_and_do_not_duplicate_ai_cost(client, db_session):
    response = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "I prefer concise daily plans.", "role": "GENERAL_ASSISTANT", "timezone": "UTC"},
    )
    assert response.status_code == 200
    processor = MemoryJobProcessor(Settings(database_url="sqlite://", ai_provider="fake"))
    assert processor.process_pending(db_session) == 1
    first_costing_calls = db_session.query(AIActionAudit).filter_by(skill_name="memory-curator").count()
    assert first_costing_calls >= 2  # one curation call and one embedding call
    assert processor.process_pending(db_session) == 0
    assert db_session.query(AIActionAudit).filter_by(skill_name="memory-curator").count() == first_costing_calls
    assert db_session.query(MemoryItem).count() == 1


def test_ai_disabled_falls_back_to_lexical_memory_retrieval(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(database_url="sqlite://", ai_provider="fake", ai_enabled=False)
    embeddings = EmbeddingService(settings, AIGateway(settings))
    service = MemoryService(embeddings)
    retrieval = MemoryRetrievalService(settings, embeddings)
    service.create_explicit(db_session, user, MemoryCreate(content="I prefer savory breakfasts", domain="kitchen"))
    results = retrieval.search_memories(db_session, user, "savory breakfast", domain="kitchen")
    assert len(results) == 1
    assert results[0].components["semantic"] > 0


def test_context_v2_keeps_patterns_memories_and_episodes_separate_and_scoped(db_session):
    user = get_or_create_user(db_session)
    settings, service, retrieval, _ = _services()
    settings.memory_context_max_chars = 1800
    service.create_explicit(db_session, user, MemoryCreate(content="I prefer meals under 45 minutes", domain="kitchen"))
    service.create_explicit(db_session, user, MemoryCreate(content="I prefer silent study sessions", domain="learning"))
    db_session.add(
        PatternEvidence(
            user_id=user.id,
            pattern_type="routine",
            scope={"key": "kitchen|evening"},
            claim="Evening kitchen recommendations are often accepted.",
            evidence_n=20,
            weighted_support=0.8,
            confidence=0.8,
            last_updated=datetime.now(UTC),
            status="ACTIVE",
        )
    )
    db_session.add(
        PatternEvidence(
            user_id=user.id,
            pattern_type="routine",
            scope={"key": "learning|afternoon"},
            claim="Afternoon study is reliable.",
            evidence_n=20,
            weighted_support=0.8,
            confidence=0.8,
            last_updated=datetime.now(UTC),
            status="ACTIVE",
        )
    )
    db_session.flush()
    tools = ToolRegistry()
    skills = SkillRegistry(settings, tools).load()
    conversations = ConversationService(settings)
    thread = conversations.create_thread(db_session, user, title="Scoped memory", default_skill="chef")
    bundle = ContextBuilderV1(settings, skills, tools, conversations, retrieval).build(
        db_session,
        user,
        role="CHEF",
        skill=skills.get("chef"),
        thread=thread,
        user_request="What dinner would suit me?",
        now=datetime.now(UTC),
        timezone="UTC",
        request_id="context-v2",
    )
    memory_contents = [item["content"] for item in bundle.dynamic_context["semantic_memory"]["items"]]
    pattern_claims = [item["claim"] for item in bundle.dynamic_context["behavioral_patterns"]["items"]]
    assert any("45 minutes" in content for content in memory_contents)
    assert all("study" not in content for content in memory_contents)
    assert pattern_claims == ["Evening kitchen recommendations are often accepted."]
    assert "authority" in bundle.dynamic_context["semantic_memory"]
    assert "authority" in bundle.dynamic_context["behavioral_patterns"]


def test_consolidation_is_idempotent_and_trivial_batch_creates_no_episode(db_session):
    user = get_or_create_user(db_session)
    settings, _, _, consolidator = _services()
    start = datetime.now(UTC) - timedelta(hours=1)
    append_event(db_session, user, event_type="notification.sent", aggregate_type="notification", aggregate_id="n-1", payload={}, outbox=False)
    end = datetime.now(UTC) + timedelta(seconds=1)
    first = consolidator.consolidate_user(db_session, user, period_start=start, period_end=end)
    second = consolidator.consolidate_user(db_session, user, period_start=start, period_end=end)
    assert first.id == second.id
    assert db_session.query(Episode).count() == 0


def test_memory_api_filters_details_diagnostics_and_tools(client):
    created = client.post(
        "/api/v1/memories",
        headers={**AUTH_HEADERS, "Idempotency-Key": "memory-api-filter"},
        json={"content": "I prefer concise learning notes", "domain": "learning", "memory_type": "domain_preference"},
    )
    assert created.status_code == 200
    memory_id = created.json()["id"]
    assert len(client.get("/api/v1/memories?domain=learning&memory_type=domain_preference&status=active", headers=AUTH_HEADERS).json()) == 1
    assert client.get("/api/v1/memories?domain=kitchen", headers=AUTH_HEADERS).json() == []
    detail = client.get(f"/api/v1/memories/{memory_id}", headers=AUTH_HEADERS)
    assert detail.status_code == 200
    assert detail.json()["evidence"][0]["source_id"] == "memory-api-filter"
    diagnostics = client.get("/api/v1/memories/diagnostics", headers=AUTH_HEADERS)
    assert diagnostics.status_code == 200
    assert diagnostics.json()["active_memories"] == 1
    registry = ToolRegistry()
    for name in ["memory_search", "memory_explain", "memory_remember", "memory_correct", "memory_pin", "memory_unpin", "memory_forget"]:
        assert registry.get(name).name == name


def test_explicit_remember_command_uses_confirmed_fast_path(client, db_session):
    response = client.post(
        "/api/v1/assistant/message",
        headers=AUTH_HEADERS,
        json={"message": "Remember that I hate olives.", "role": "GENERAL_ASSISTANT", "timezone": "UTC"},
    )
    assert response.status_code == 200
    memory = db_session.scalar(select(MemoryItem).where(MemoryItem.domain == "kitchen"))
    assert memory is not None
    assert memory.user_confirmed is True
    assert memory.polarity == -1
    assert db_session.query(MemoryProcessingJob).count() == 0


def test_repeated_recommendation_outcomes_create_evidence_backed_memory(db_session):
    user = get_or_create_user(db_session)
    candidate = {
        "memory_type": "domain_preference",
        "domain": "kitchen",
        "content": "Usually prefers spicy meal recommendations.",
        "normalized_key": "spicy meal recommendations",
        "polarity": 1,
        "importance": 0.6,
        "explicit": False,
    }
    for index in range(3):
        recommendation_service.record_outcome(
            db_session,
            user,
            RecommendationOutcomeCreate(
                domain="kitchen",
                recommendation_type="meal",
                recommendation_summary=f"Spicy meal {index}",
                outcome="accepted",
                idempotency_key=f"spicy-{index}",
                metadata_json={"memory_candidate": candidate},
            ),
        )
    processor = MemoryJobProcessor(Settings(database_url="sqlite://", ai_provider="fake"))
    assert processor.process_pending(db_session) == 3
    memory = db_session.scalar(select(MemoryItem).where(MemoryItem.normalized_key == "spicy meal recommendations"))
    assert memory is not None
    assert db_session.query(MemoryEvidence).filter_by(memory_id=memory.id, source_type="recommendation_outcome").count() == 3
    assert db_session.query(MemoryItem).filter_by(normalized_key="spicy meal recommendations").count() == 1
