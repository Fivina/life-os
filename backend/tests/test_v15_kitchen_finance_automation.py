import base64
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.ai.gateway import AIGateway
from app.ai.providers import FakeAIProvider
from app.ai.types import AIProviderError, AIResponse, AIUsageMetadata
from app.core.config import Settings
from app.database.models import Action, FinanceTransaction, InventoryLot, MealFeedback, RecommendationOutcome, UserProfile
from app.domains.finance import service as finance_service
from app.domains.finance.schemas import BudgetCreate, CsvImportCreate, ImportRowUpdate
from app.domains.kitchen import receipts
from app.domains.kitchen.receipt_schemas import ReceiptUploadCreate
from app.domains.kitchen.schemas import MealPlanCompleteRequest, MealSelectionCreate, RecommendationRequest
from app.domains.kitchen import service as kitchen_service

from .conftest import AUTH_HEADERS


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nlife-os-v15-receipt").decode("ascii")


class ReceiptVisionProvider(FakeAIProvider):
    def complete(self, *, model, request):
        if request.metadata.get("mode") != "receipt_extraction":
            return super().complete(model=model, request=request)
        value = {
            "merchant": "REWE Markt 1234",
            "transaction_at": "2026-09-18T17:30:00+00:00",
            "currency": "EUR",
            "subtotal": 10.0,
            "tax": 0.7,
            "total": 10.7,
            "confidence": 0.94,
            "items": [
                {"raw_text": "Chicken 500g", "normalized_name": "Chicken breast", "quantity": 500, "unit": "g", "line_total": 8.5, "category": "food", "confidence_name": 0.98, "confidence_quantity": 0.96, "confidence_price": 0.97},
                {"raw_text": "Kitchen roll", "normalized_name": "Kitchen roll", "quantity": 1, "unit": "count", "line_total": 2.2, "category": "household", "confidence_name": 0.96, "confidence_quantity": 0.95, "confidence_price": 0.96},
            ],
        }
        return AIResponse(text=json.dumps(value), provider="fake", model=model, usage=AIUsageMetadata(), finish_status="STOP")


class FailingVisionProvider(FakeAIProvider):
    def complete(self, *, model, request):
        raise AIProviderError("provider_unavailable", "Vision is temporarily unavailable.", retryable=True)


def _user(db_session, suffix="one"):
    user = UserProfile(email=f"v15-{suffix}@example.test", auth_subject=f"v15-{suffix}", display_name="V15 User")
    db_session.add(user)
    db_session.flush()
    return user


def _settings(tmp_path):
    return Settings(database_url="sqlite://", ai_provider="fake", media_storage_path=str(tmp_path / "media"), development_auth_enabled=True)


def test_receipt_confirmation_is_secure_atomic_idempotent_and_scoped(db_session, tmp_path):
    user = _user(db_session)
    settings = _settings(tmp_path)
    gateway = AIGateway(settings, providers={"fake": ReceiptVisionProvider()})
    payload = ReceiptUploadCreate(filename="../../receipt.png", mime_type="image/png", content_base64=PNG, process=True)

    draft = receipts.create_import(db_session, user, settings, payload, gateway=gateway)
    duplicate = receipts.create_import(db_session, user, settings, payload, gateway=gateway)
    assert draft.id == duplicate.id
    assert draft.status == "extracted"
    assert draft.review_count == 0
    assert len(draft.lines) == 2

    confirmed = receipts.confirm_import(db_session, user, draft.id)
    repeated = receipts.confirm_import(db_session, user, draft.id)
    assert confirmed.status == repeated.status == "confirmed"
    assert confirmed.finance_transaction_id == repeated.finance_transaction_id
    assert db_session.query(InventoryLot).filter_by(user_id=user.id, source="receipt").count() == 1
    assert db_session.query(FinanceTransaction).filter_by(user_id=user.id, source="receipt").count() == 1
    household = next(line for line in confirmed.lines if line.category == "household")
    assert household.inventory_lot_id is None

    other = _user(db_session, "two")
    with pytest.raises(HTTPException) as error:
        receipts.get_import(db_session, other, draft.id)
    assert error.value.status_code == 404


def test_receipt_provider_failure_stays_pending_without_canonical_mutation(db_session, tmp_path):
    user = _user(db_session, "failure")
    settings = _settings(tmp_path)
    gateway = AIGateway(settings, providers={"fake": FailingVisionProvider()})
    result = receipts.create_import(db_session, user, settings, ReceiptUploadCreate(filename="receipt.png", mime_type="image/png", content_base64=PNG, process=True), gateway=gateway)
    assert result.status == "pending_vision"
    assert "unavailable" in result.failure_reason.lower()
    assert db_session.query(InventoryLot).filter_by(user_id=user.id).count() == 0
    assert db_session.query(FinanceTransaction).filter_by(user_id=user.id).count() == 0


def test_finance_csv_review_dedupe_correction_budget_and_safe_to_spend(db_session):
    user = _user(db_session, "finance")
    csv_text = "date,merchant,amount,currency,reference\n2026-09-01,Salary,2000.00,EUR,salary-1\n2026-09-03,REWE Markt,-12.34,EUR,grocery-1\n2026-09-04,Mystery Shop,-5.01,EUR,mystery-1\n"
    first = finance_service.create_csv_import(db_session, user, CsvImportCreate(filename="bank.csv", content=csv_text))
    duplicate = finance_service.create_csv_import(db_session, user, CsvImportCreate(filename="copy.csv", content=csv_text))
    assert first.id == duplicate.id
    assert first.review_count == 1
    uncertain = next(row for row in first.rows if row.review_required)
    reviewed = finance_service.update_import_row(db_session, user, uncertain.id, ImportRowUpdate(category="Groceries", accept=True))
    assert reviewed.review_count == 0
    confirmed = finance_service.confirm_import(db_session, user, first.id)
    assert confirmed.status == "confirmed"
    assert db_session.query(FinanceTransaction).filter_by(user_id=user.id).count() == 3
    assert sum((row.amount for row in db_session.query(FinanceTransaction).filter_by(user_id=user.id, direction="expense")), Decimal("0")) == Decimal("17.35")

    follow_up = finance_service.create_csv_import(db_session, user, CsvImportCreate(filename="next.csv", content="date,merchant,amount,currency,reference\n2026-09-05,Mystery Shop,-6.00,EUR,mystery-2\n"))
    assert follow_up.review_count == 0
    assert follow_up.rows[0].category_name == "Groceries"
    finance_service.confirm_import(db_session, user, follow_up.id)
    budget = finance_service.create_budget(db_session, user, BudgetCreate(name="Groceries", category="Groceries", amount=Decimal("100.00"), month_start=date(2026, 9, 1), protected=True))
    assert budget.spent == Decimal("23.35")
    assert budget.remaining == Decimal("76.65")
    safe = finance_service.safe_to_spend(db_session, user, date(2026, 9, 1))
    assert safe.safe_to_spend == Decimal("1900.00")
    assert safe.assumptions


def test_recurring_expense_detection_requires_repeated_evidence(db_session):
    user = _user(db_session, "recurring")
    csv_text = "date,merchant,amount,currency,reference\n2026-06-01,Spotify,-10.99,EUR,sp-1\n2026-07-01,Spotify,-10.99,EUR,sp-2\n2026-08-01,Spotify,-10.99,EUR,sp-3\n"
    batch = finance_service.create_csv_import(db_session, user, CsvImportCreate(filename="recurring.csv", content=csv_text))
    finance_service.confirm_import(db_session, user, batch.id)
    recurring = finance_service.refresh_recurring(db_session, user)
    assert len(recurring) == 1
    assert recurring[0].evidence_count == 3
    assert 25 <= recurring[0].interval_days <= 35
    assert recurring[0].confidence >= 0.55


def test_chef_selection_creates_dependency_and_completion_updates_competency(client, db_session):
    def post(path, payload):
        response = client.post(f"/api/v1{path}", headers=AUTH_HEADERS, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    expires = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    post("/kitchen/inventory", {"ingredient_name": "Chicken breast", "quantity": 500, "unit": "g", "expires_on": expires})
    post("/kitchen/recipes", {
        "name": "Chicken rice", "preparation_minutes": 10, "cooking_minutes": 25, "servings": 1,
        "calories_per_serving": 620, "protein_g_per_serving": 55, "protein_family": "chicken",
        "steps": ["Slice chicken", "Cook rice", "Saute chicken"],
        "techniques": [{"key": "saute", "name": "Sauteing", "required_level": 1, "importance": 1}],
        "ingredients": [{"ingredient_name": "Chicken breast", "quantity": 200, "unit": "g"}, {"ingredient_name": "Rice", "quantity": 100, "unit": "g"}],
    })
    recommendation = post("/kitchen/chef/recommendations", {"limit": 5})
    option = recommendation["options"][0]
    planned_for = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
    plan = post("/kitchen/meal-plans", {"recommendation_id": recommendation["recommendation_id"], "option_id": option["option_id"], "planned_for": planned_for, "servings": 1})
    assert plan["shopping_action_id"] and plan["cooking_action_id"]
    cooking = db_session.get(Action, plan["cooking_action_id"])
    assert cooking.metadata_json["depends_on_action_id"] == plan["shopping_action_id"]
    required = client.get("/api/v1/kitchen/shopping-list", headers=AUTH_HEADERS).json()
    assert required[0]["priority_class"] == "required"
    for item_id in required[0]["source_item_ids"]:
        post(f"/kitchen/shopping-items/{item_id}/purchase", {"add_to_inventory": True})

    completed = post(f"/kitchen/meal-plans/{plan['id']}/complete", {"satisfaction": 5, "feedback": "Great texture and sauce"})
    repeated = post(f"/kitchen/meal-plans/{plan['id']}/complete", {"satisfaction": 5, "feedback": "Great texture and sauce"})
    assert completed["meal_history_id"] == repeated["meal_history_id"]
    competencies = client.get("/api/v1/kitchen/competencies", headers=AUTH_HEADERS).json()
    assert competencies[0]["technique_key"] == "saute"
    assert competencies[0]["evidence_count"] == 1
    assert db_session.query(MealFeedback).count() == 1
    outcomes = db_session.query(RecommendationOutcome).filter_by(recommendation_id=recommendation["recommendation_id"]).all()
    assert {row.outcome for row in outcomes} >= {"shown", "accepted", "completed"}


def test_inventory_adjustment_and_staple_forecast_are_deterministic(client):
    def post(path, payload):
        response = client.post(f"/api/v1{path}", headers=AUTH_HEADERS, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    milk = post("/kitchen/inventory", {
        "ingredient_name": "Milk",
        "quantity": 0.5,
        "unit": "l",
        "canonical_unit": "l",
        "is_staple": True,
        "restock_threshold": 1,
        "restock_target": 2,
    })
    forecast = post("/kitchen/shopping-forecast", {"window_days": 3, "limit": 5})
    restock = next(need for need in forecast if need["metadata_json"].get("kind") == "staple_restock")
    assert restock["items"][0]["priority_class"] == "restock"
    assert restock["items"][0]["quantity"] == 1.5
    assert "threshold" in restock["items"][0]["reason"]

    adjusted = post(f"/kitchen/inventory/{milk['id']}/mutations", {"operation": "adjust", "quantity": 1.25, "unit": "l", "reason": "Fridge count"})
    assert adjusted["total_quantity"] == 1.25
    consumed = post(f"/kitchen/inventory/{milk['id']}/mutations", {"operation": "consume", "quantity": 0.25, "unit": "l", "reason": "Breakfast"})
    assert consumed["total_quantity"] == 1

    repeated = post("/kitchen/shopping-forecast", {"window_days": 3, "limit": 5})
    assert all(need["metadata_json"].get("kind") != "staple_restock" for need in repeated)
    active = client.get("/api/v1/kitchen/shopping-needs", headers=AUTH_HEADERS).json()
    assert all(need["metadata_json"].get("kind") != "staple_restock" for need in active)
