from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.ai.gateway import AIGateway
from app.ai.providers import FakeAIProvider
from app.ai.types import AIResponse, AIUsageMetadata
from app.api.deps import get_or_create_user
from app.communication.composer import ResponseComposer
from app.communication.schemas import CommunicativeIntent, ResponseModePreference, SpeechAct, StructuredFact
from app.attention.schemas import AttentionAction
from app.core.config import Settings
from app.database.models import CookingCompetencyEvidence, InventoryItem, InventoryLot, MealHistory, MealPlan, RecommendationOutcome
from app.domains.finance.contracts import grocery_budget_signal
from app.domains.fitness.contracts import nutrition_context
from app.domains.kitchen.chef import recommend_from_text
from app.domains.kitchen.intent import interpret_meal_intent
from app.domains.kitchen.schemas import ChefIntentRequest, MealIntent
from app.workspaces.service import ActiveWorkspaceService
from tests.conftest import AUTH_HEADERS


def _post(client, path: str, payload: dict):
    response = client.post(f"/api/v1{path}", headers=AUTH_HEADERS, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _recipe(client, name: str, *, prep: int = 10, cook: int = 10, protein: float = 35, family: str = "chicken", tags=None, ingredients=None, techniques=None):
    return _post(client, "/kitchen/recipes", {
        "name": name,
        "preparation_minutes": prep,
        "cooking_minutes": cook,
        "servings": 1,
        "calories_per_serving": 520,
        "protein_g_per_serving": protein,
        "carbs_g_per_serving": 45,
        "fat_g_per_serving": 16,
        "protein_family": family,
        "tags": tags or [family],
        "steps": ["Prepare", "Cook", "Serve"],
        "ingredients": ingredients or [{"ingredient_name": "Chicken", "quantity": 200, "unit": "g"}],
        "techniques": techniques or [],
    })


class MalformedMealIntentProvider(FakeAIProvider):
    def complete(self, *, model, request):
        return AIResponse(text='{"version":"meal-intent-v1","free_text_source":"bad","max_total_minutes":-4}', provider="fake", model=model, usage=AIUsageMetadata())


def test_meal_intent_examples_use_ai_gateway_and_malformed_output_falls_back(db_session):
    user = get_or_create_user(db_session)
    settings = Settings(database_url="sqlite://", ai_provider="fake", ai_enabled=True)
    gateway = AIGateway(settings, providers={"fake": FakeAIProvider()})
    result = interpret_meal_intent(db_session, user, ChefIntentRequest(request="Turkish mother food with meat"), settings, gateway=gateway)
    assert result.mode == "AI"
    assert result.intent.cuisine_preferences == ("turkish",)
    assert "home_style" in result.intent.styles and "meat" in result.intent.protein_preferences

    fast = interpret_meal_intent(db_session, user, ChefIntentRequest(request="I have 25 minutes"), settings, gateway=gateway)
    assert fast.intent.max_total_minutes == 25
    light = interpret_meal_intent(db_session, user, ChefIntentRequest(request="Something high protein but not too heavy"), settings, gateway=gateway)
    assert light.intent.protein_priority == "HIGH" and light.intent.heaviness_preference.value == "LIGHT_TO_MEDIUM"

    malformed = interpret_meal_intent(db_session, user, ChefIntentRequest(request="I have 20 minutes"), settings,
                                      gateway=AIGateway(settings, providers={"fake": MalformedMealIntentProvider()}))
    assert malformed.mode == "DETERMINISTIC_FALLBACK" and malformed.intent.max_total_minutes == 20
    assert malformed.warning and db_session.query(MealPlan).count() == 0


def test_typed_bridges_preserve_unknown_and_minimize_cross_domain_data(db_session):
    user = get_or_create_user(db_session)
    fitness = nutrition_context(db_session, user)
    budget = grocery_budget_signal(db_session, user)
    assert fitness.calories_target_daily is None and fitness.protein_target_g is None
    assert fitness.data_completeness == "UNKNOWN" and fitness.recovery_context == "UNKNOWN"
    assert budget.status == "UNKNOWN" and budget.grocery_budget_remaining is None
    assert not hasattr(budget, "transactions") and not hasattr(budget, "salary")


def test_natural_chef_hard_time_inventory_expiry_and_named_factors(client, db_session):
    expired = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    _post(client, "/kitchen/inventory", {"ingredient_name": "Chicken", "quantity": 500, "unit": "g", "expires_on": expired})
    for name, minutes, family, tags in [
        ("Etli quick stew", 20, "beef", ["turkish", "home_style", "meat"]),
        ("Chicken bowl", 22, "chicken", ["fresh", "chicken"]),
        ("Bean comfort plate", 25, "beans", ["comfort_food", "beans"]),
        ("Slow roast", 90, "beef", ["turkish", "home_style", "meat"]),
    ]:
        _recipe(client, name, prep=8, cook=minutes - 8, family=family, tags=tags)
    before = db_session.query(InventoryLot).one().quantity
    result = _post(client, "/kitchen/chef/recommend", {"request": "I have 25 minutes, Turkish mother food with meat", "limit": 5})
    assert result["intent"]["max_total_minutes"] == 25
    assert 3 <= len(result["options"]) <= 5
    assert all(option["total_minutes"] <= 25 for option in result["options"])
    assert all("time_fit" in option["score_factors"] and "inventory_fit" in option["score_factors"] for option in result["options"])
    assert all(option["estimated_grocery_delta"] is None for option in result["options"])
    assert db_session.query(InventoryLot).one().quantity == before

    no_shop = _post(client, "/kitchen/chef/recommend", {"request": "Chicken, use what I have", "limit": 5})
    assert all(option["recipe"]["name"] != "Chicken bowl" for option in no_shop["options"])


def test_selection_workspace_restart_actual_usage_idempotency_history_and_competency(client, db_session):
    _post(client, "/kitchen/inventory", {"ingredient_name": "Chicken", "quantity": 500, "unit": "g"})
    _post(client, "/kitchen/inventory", {"ingredient_name": "Rice", "quantity": 500, "unit": "g"})
    for index in range(3):
        _recipe(client, f"Chicken rice {index + 1}", family="chicken", tags=["home_style", "chicken"],
                ingredients=[{"ingredient_name": "Chicken", "quantity": 200, "unit": "g"}, {"ingredient_name": "Rice", "quantity": 100, "unit": "g"}],
                techniques=[{"key": "saute", "name": "Sauteing", "required_level": 1, "importance": 1}])
    recommendation = _post(client, "/kitchen/chef/recommend", {"request": "Home style chicken, high protein", "limit": 3})
    option = recommendation["options"][0]
    plan = _post(client, "/kitchen/meal-plans", {
        "recommendation_id": recommendation["recommendation_id"], "option_id": option["option_id"],
        "planned_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "servings": 1,
    })
    assert next(item for item in plan["planned_ingredients"] if item["ingredient_name"] == "Chicken")["quantity"] == 200
    assert db_session.query(InventoryLot).filter(InventoryLot.quantity == 500).count() == 2

    session = _post(client, "/kitchen/cooking-sessions", {"meal_plan_id": plan["id"], "conversation_thread_id": "chef-thread"})
    update = client.patch(f"/api/v1/kitchen/cooking-sessions/{session['id']}", headers=AUTH_HEADERS, json={"current_step_index": 1, "temporary_notes": "Using the wide pan"})
    assert update.status_code == 200, update.text
    db_session.commit()
    db_session.expire_all()
    user = get_or_create_user(db_session)
    restored = ActiveWorkspaceService().get_foreground_workspace(db_session, user)
    payload = ActiveWorkspaceService().reconstruct_payload(restored)
    assert payload.meal_plan_ref == plan["id"] and payload.current_step_index == 1 and payload.current_step == "Cook"

    completed = _post(client, f"/kitchen/meal-plans/{plan['id']}/complete", {
        "satisfaction": 5, "feedback": "Great, make this again",
        "actual_ingredients": [{"ingredient_name": "Chicken", "quantity": 240, "unit": "g"}, {"ingredient_name": "Rice", "quantity": 110, "unit": "g"}],
    })
    repeated = _post(client, f"/kitchen/meal-plans/{plan['id']}/complete", {
        "actual_ingredients": [{"ingredient_name": "Chicken", "quantity": 240, "unit": "g"}, {"ingredient_name": "Rice", "quantity": 110, "unit": "g"}],
    })
    assert completed["meal_history_id"] == repeated["meal_history_id"]
    quantities = {item.ingredient_name: item.quantity for item in db_session.query(InventoryItem).all()}
    assert quantities == {"Chicken": 260, "Rice": 390}
    meal = db_session.get(MealHistory, completed["meal_history_id"])
    assert {item["ingredient_name"] for item in meal.actual_usage_json} == {"Chicken", "Rice"}
    assert db_session.query(CookingCompetencyEvidence).count() == 1
    assert db_session.query(RecommendationOutcome).filter_by(outcome="completed").count() == 1


def test_meal_plan_modification_recalculates_usage_and_marks_nutrition_uncertainty(client):
    for name in ("Chicken", "Rice"):
        _post(client, "/kitchen/inventory", {"ingredient_name": name, "quantity": 500, "unit": "g"})
    for index in range(3):
        _recipe(client, f"Plan dish {index}", ingredients=[{"ingredient_name": "Chicken", "quantity": 200, "unit": "g"}, {"ingredient_name": "Rice", "quantity": 100, "unit": "g", "optional": True}])
    recommendation = _post(client, "/kitchen/chef/recommend", {"request": "Something with chicken", "limit": 3})
    plan = _post(client, "/kitchen/meal-plans", {"recommendation_id": recommendation["recommendation_id"], "option_id": recommendation["options"][0]["option_id"], "planned_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})
    response = client.patch(f"/api/v1/kitchen/meal-plans/{plan['id']}", headers=AUTH_HEADERS, json={"servings": 2, "excluded_ingredients": ["Rice"], "ingredient_substitutions": {"Chicken": "Turkey"}})
    assert response.status_code == 200, response.text
    modified = response.json()
    assert modified["planned_servings"] == 2 and len(modified["planned_ingredients"]) == 1
    assert modified["planned_ingredients"][0]["ingredient_name"] == "Turkey" and modified["planned_ingredients"][0]["quantity"] == 400
    assert modified["nutrition_snapshot"]["confidence"] == "PARTIAL"


def test_response_composer_rejects_invented_chef_arithmetic():
    intent = CommunicativeIntent(
        purpose=SpeechAct.inform, attention_action=AttentionAction.show_passively, reason_code="chef_option",
        facts=(StructuredFact(key="meal", value="Stew"), StructuredFact(key="protein", value=38, unit="g")),
        response_mode_preference=ResponseModePreference.generative, fallback_template_key="chef_option",
    )
    composer = ResponseComposer()
    assert "38" in composer.deterministic_text(intent)
    try:
        composer.validate_generated(intent, "Stew has 91 g protein.")
        assert False, "invented nutrition should be rejected"
    except ValueError:
        pass


def test_kitchen_has_no_direct_gemini_or_planblock_authority():
    root = Path(__file__).parents[1] / "app" / "domains" / "kitchen"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert "google.generativeai" not in imports
        assert "google.genai" not in imports
        assert "app.planning.service" not in imports
        assert "PlanBlock(" not in path.read_text(encoding="utf-8")
