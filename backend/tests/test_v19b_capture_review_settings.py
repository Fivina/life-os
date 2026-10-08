from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.deps import get_or_create_user
from app.assistant.schemas import AssistantMessageRequest
from app.assistant.service import AssistantService
from app.attention.manager import AttentionManager
from app.attention.schemas import AttentionAction, AttentionCandidate
from app.capture.schemas import CapturePolicyOutcome, CaptureStatus, QuickCaptureCreate
from app.capture.service import QuickCaptureService
from app.core.config import Settings
from app.database.models import (
    Course, Exam, FinanceTransaction, MediaAsset, MemoryItem, NotebookEntry, PlanBlock, QuickCapture,
    ReceiptImport, ReceiptLine, ReviewItem, ShoppingNeedItem, UserIntelligenceSettings,
)
from app.intelligence_settings.schemas import IntelligenceSettingsUpdate, ProactivityMode
from app.intelligence_settings.service import IntelligenceSettingsService
from app.review.schemas import ReviewAction, ReviewCreate
from app.review.service import ReviewQueueService
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    values = {"ai_enabled": False, "ai_provider": "fake", "development_auth_enabled": True, **overrides}
    return Settings(_env_file=None, **values)


def _exam(db, user, title: str = "Algorithms Final") -> Exam:
    course = Course(user_id=user.id, name="Algorithms", code="ALG")
    db.add(course); db.flush()
    exam = Exam(
        user_id=user.id, course_id=course.id, title=title, exam_date=date(2026, 10, 1),
        exam_at=datetime(2026, 10, 1, 10, tzinfo=UTC), target_preparation_minutes=600,
        estimated_required_hours=10, status="planned",
    )
    db.add(exam); db.flush()
    return exam


def test_exam_move_is_typed_proposal_then_applies_through_learning(db_session):
    user = get_or_create_user(db_session)
    exam = _exam(db_session, user)
    before_blocks = db_session.scalar(select(func.count(PlanBlock.id)))
    service = QuickCaptureService(_settings())
    proposed = service.capture(
        db_session, user,
        QuickCaptureCreate(text="My Algorithms exam moved to Friday.", now=NOW, timezone="UTC"),
        idempotency_key="exam-move-1",
    )
    assert proposed.intent_type.value == "UPDATE_EXAM_DATE"
    assert proposed.target_entity_id == exam.id
    assert proposed.structured_payload["new_date"] == "2026-10-02"
    assert proposed.policy_outcome == CapturePolicyOutcome.request_confirmation
    assert exam.exam_date == date(2026, 10, 1)
    applied = service.apply(db_session, user, proposed.id, expected_version=proposed.version)
    assert applied.status == CaptureStatus.applied
    assert exam.exam_date == date(2026, 10, 2)
    assert db_session.scalar(select(func.count(PlanBlock.id))) == before_blocks


def test_finance_and_shopping_capture_apply_idempotently(db_session):
    user = get_or_create_user(db_session)
    service = QuickCaptureService(_settings())
    finance = service.capture(db_session, user, QuickCaptureCreate(text="I paid 18 euros at Rewe.", now=NOW), idempotency_key="finance-1")
    assert finance.structured_payload == {
        "occurred_on": "2026-09-28", "amount": "18", "currency": "EUR", "merchant": "Rewe",
        "category": "Groceries", "description": None,
    }
    first = service.apply(db_session, user, finance.id)
    second = service.apply(db_session, user, finance.id)
    assert first.canonical_entity_id == second.canonical_entity_id
    transaction = db_session.get(FinanceTransaction, first.canonical_entity_id)
    assert transaction.amount == Decimal("18.00") and transaction.source == "quick_capture"
    shopping = service.capture(db_session, user, QuickCaptureCreate(text="I need detergent.", now=NOW), idempotency_key="shop-1")
    result = service.apply(db_session, user, shopping.id)
    assert db_session.get(ShoppingNeedItem, result.canonical_entity_id).ingredient_name == "detergent"
    assert db_session.scalar(select(func.count(ShoppingNeedItem.id))) == 1
    assert QuickCaptureService.is_likely_capture("I need detergent.") is True
    assert QuickCaptureService.is_likely_capture("I need to study macro for 90 minutes before Friday.") is False


def test_notebook_idea_never_enters_quick_capture(db_session):
    user = get_or_create_user(db_session)
    response = AssistantService(_settings()).handle_message(
        db_session, user,
        AssistantMessageRequest(message="Write this down as an implementation idea: connect Moodle someday.", now=NOW),
    )
    assert response.mutation_result.entity_type == "notebook_entry"
    assert db_session.scalar(select(func.count(NotebookEntry.id))) == 1
    assert db_session.scalar(select(func.count(QuickCapture.id))) == 0


def test_ambiguous_exam_enters_one_review_and_stale_target_is_not_applied(db_session):
    user = get_or_create_user(db_session)
    first_exam = _exam(db_session, user, "Algorithms Midterm")
    _exam(db_session, user, "Algorithms Final")
    service = QuickCaptureService(_settings())
    first = service.capture(db_session, user, QuickCaptureCreate(text="Move the exam to Friday.", now=NOW), idempotency_key="ambiguous-1")
    replay = service.capture(db_session, user, QuickCaptureCreate(text="Move the exam to Friday.", now=NOW), idempotency_key="ambiguous-1")
    assert first.id == replay.id and first.review_required
    assert len(first.structured_payload["entity_candidates"]) == 2
    assert db_session.scalar(select(func.count(ReviewItem.id))) == 1

    resolved = service.capture(db_session, user, QuickCaptureCreate(text="My Algorithms Midterm exam moved to Friday.", now=NOW), idempotency_key="stale-1")
    assert resolved.review_required is False
    row = db_session.get(QuickCapture, resolved.id)
    row.review_required = True
    row.status = "PENDING_REVIEW"
    review, _ = ReviewQueueService().enqueue(db_session, user, ReviewCreate(
        review_type="QUICK_CAPTURE", source="quick_capture", source_ref=row.id,
        summary="Confirm exam date", question="Apply this exam date?", affected_domain="LEARNING",
        target_entity_type="exam", target_entity_id=first_exam.id,
        candidate_values=row.structured_payload_json, expected_target_version=first_exam.version,
    ))
    first_exam.version += 1
    outcome = ReviewQueueService().resolve(
        db_session, user, review.id, action=ReviewAction.accept,
        edited_values={}, expected_version=review.version,
    )
    assert outcome.item.status.value == "SUPERSEDED"
    assert row.status == "SUPERSEDED"
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(ReviewItem, review.id).status == "SUPERSEDED"


def test_unknown_finance_classification_goes_to_review_and_can_be_edited(db_session):
    user = get_or_create_user(db_session)
    service = QuickCaptureService(_settings())
    capture = service.capture(db_session, user, QuickCaptureCreate(text="I paid 27.80 euros at Amazon.", now=NOW), idempotency_key="amazon-1")
    assert capture.review_required and capture.review_item_id
    review = ReviewQueueService().get(db_session, user, capture.review_item_id)
    result = ReviewQueueService().resolve(
        db_session, user, review.id, action=ReviewAction.edit_and_accept,
        edited_values={"category": "Shopping"}, expected_version=review.version,
    )
    assert result.item.status.value == "RESOLVED"
    assert db_session.get(FinanceTransaction, result.canonical_entity_id).source == "quick_capture"


def test_receipt_and_memory_uncertainty_use_global_review_queue(db_session):
    user = get_or_create_user(db_session)
    asset = MediaAsset(
        user_id=user.id, kind="receipt", storage_key="test/receipt.png", mime_type="image/png",
        size_bytes=10, content_hash="a" * 64, source="test",
    )
    db_session.add(asset); db_session.flush()
    receipt = ReceiptImport(user_id=user.id, asset_id=asset.id, status="review_required")
    db_session.add(receipt); db_session.flush()
    line = ReceiptLine(
        user_id=user.id, receipt_import_id=receipt.id, line_number=1, raw_text="Bio Tom. 500",
        normalized_name=None, quantity=None, unit=None, category="other", confidence_name=0.3,
        confidence_quantity=0.2, confidence_price=0.4, review_required=True,
    )
    db_session.add(line); db_session.flush()
    queue = ReviewQueueService()
    receipt_review = queue.sync_receipt_uncertainty(db_session, user, receipt.id)[0]
    result = queue.resolve(
        db_session, user, receipt_review.id, action=ReviewAction.edit_and_accept,
        edited_values={"normalized_name": "tomatoes", "quantity": 0.5, "unit": "kg", "category": "food"},
        expected_version=receipt_review.version,
    )
    assert result.item.status.value == "RESOLVED"
    assert line.normalized_name == "tomatoes" and line.review_required is False

    memory = MemoryItem(
        user_id=user.id, memory_type="preference", domain="general", content="Maybe prefers early study",
        normalized_key="maybe prefers early study", confidence=0.3, importance=0.4,
        status="uncertain", source_kind="assistant",
    )
    db_session.add(memory); db_session.flush()
    memory_review = queue.enqueue_memory_candidate(db_session, user, memory.id)
    rejected = queue.resolve(
        db_session, user, memory_review.id, action=ReviewAction.reject,
        edited_values={}, expected_version=memory_review.version,
    )
    assert rejected.item.status.value == "DISMISSED"
    assert memory.status == "forgotten" and memory.deleted_at is not None


def test_stale_canonical_correction_is_superseded_without_mutation(db_session):
    user = get_or_create_user(db_session)
    exam = _exam(db_session, user)
    original_date = exam.exam_date
    review, _ = ReviewQueueService().enqueue(db_session, user, ReviewCreate(
        review_type="CANONICAL_CORRECTION", source="integrity_check", source_ref="candidate-1",
        summary="Possible exam correction", question="Should the exam date be corrected?",
        affected_domain="LEARNING", target_entity_type="exam", target_entity_id=exam.id,
        candidate_values={"exam_date": "2026-10-09"}, expected_target_version=exam.version,
    ))
    exam.version += 1
    resolved = ReviewQueueService().resolve(
        db_session, user, review.id, action=ReviewAction.accept,
        edited_values={}, expected_version=review.version,
    )
    assert resolved.item.status.value == "SUPERSEDED"
    assert exam.exam_date == original_date


def test_settings_drive_budget_attention_and_skill_disable_without_secrets(db_session):
    user = get_or_create_user(db_session)
    service = IntelligenceSettingsService(_settings(gemini_api_key="secret-test-key", ai_provider="gemini"))
    updated = service.update(db_session, user, IntelligenceSettingsUpdate(
        proactivity_mode=ProactivityMode.quiet, monthly_ai_budget_eur=3,
        disabled_skills=["self-core"],
    ))
    assert updated.proactivity_mode == ProactivityMode.quiet and updated.monthly_ai_budget_eur == 3
    surface = service.control_surface(db_session, user).model_dump(mode="json")
    assert "secret-test-key" not in str(surface)
    assert surface["usage"]["budget_eur"] == 3
    assert next(item for item in surface["skills"] if item["name"] == "self-core")["enabled"] is False
    candidate = AttentionCandidate(
        requested_action=AttentionAction.mention_when_natural, reason_code="test", subject="Low urgency",
        priority=50, urgency=0.2, evidence_quality=0.9, confidence=0.9, reversible=True,
    )
    decision = AttentionManager().decide(candidate, proactivity_mode="QUIET")
    assert decision.action == AttentionAction.silent and decision.reason_code == "quiet_mode_nonurgent"
    with pytest.raises(HTTPException) as error:
        AssistantService(_settings()).handle_message(db_session, user, AssistantMessageRequest(message="What is next?", now=NOW))
    assert error.value.status_code == 409
    assert db_session.scalar(select(func.count(UserIntelligenceSettings.id))) == 1


def test_authenticated_capture_review_and_settings_api(client):
    capture_response = client.post(
        "/api/v1/quick-capture", headers={**AUTH_HEADERS, "Idempotency-Key": "api-amazon-1"},
        json={"text": "I paid 12 euros at Unknown Store.", "now": NOW.isoformat()},
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()
    assert capture["review_required"] is True and capture["review_item_id"]
    reviews = client.get("/api/v1/review", headers=AUTH_HEADERS)
    assert reviews.status_code == 200 and len(reviews.json()) == 1
    settings_response = client.get("/api/v1/settings/intelligence", headers=AUTH_HEADERS)
    assert settings_response.status_code == 200
    body = settings_response.json()
    assert set(body) == {"settings", "memory", "patterns", "conversations", "skills", "providers", "agents", "active_agent_runtime", "live_agents_enabled", "credential_management_available", "usage", "privacy"}
    assert "api_key" not in str(body).lower()
