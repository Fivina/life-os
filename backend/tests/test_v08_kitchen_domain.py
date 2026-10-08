from datetime import UTC, datetime, timedelta

from app.database.models import InventoryLot

from .conftest import AUTH_HEADERS


def _post(client, path, payload):
    response = client.post(f"/api/v1{path}", headers=AUTH_HEADERS, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_inventory_lots_expiry_and_recipe_completion_consumes_oldest_lot(client, db_session):
    now = datetime.now(UTC)
    expiring = (now + timedelta(days=1)).date().isoformat()
    later = (now + timedelta(days=15)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    eggs = _post(client, "/kitchen/inventory", {"ingredient_name": "Eggs", "quantity": 6, "unit": "count", "expires_on": expiring})
    _post(client, f"/kitchen/inventory/{eggs['id']}/lots", {"quantity": 6, "unit": "count", "expires_at": later})
    target = _post(client, "/kitchen/nutrition-target", {"calories_target": 2400, "protein_g_target": 170})
    assert target["protein_g_target"] == 170
    recipe = _post(
        client,
        "/kitchen/recipes",
        {
            "name": "Egg scramble",
            "preparation_minutes": 5,
            "cooking_minutes": 8,
            "servings": 1,
            "calories_per_serving": 350,
            "protein_g_per_serving": 28,
            "protein_family": "eggs",
            "tags": ["breakfast"],
            "ingredients": [{"ingredient_name": "Eggs", "quantity": 3, "unit": "count"}],
        },
    )

    recs = client.get("/api/v1/kitchen/recommendations?no_shopping=true", headers=AUTH_HEADERS)
    assert recs.status_code == 200
    body = recs.json()
    assert body[0]["recipe"]["id"] == recipe["id"]
    assert body[0]["availability"] == "available"
    assert body[0]["score_factors"]["ingredient_expiry_value"] > 0

    meal = _post(client, f"/kitchen/recipes/{recipe['id']}/complete", {"servings": 1, "satisfaction": 5})
    assert meal["calories_snapshot"] == 350
    lots = db_session.query(InventoryLot).filter_by(inventory_item_id=eggs["id"]).order_by(InventoryLot.expires_at).all()
    assert lots[0].quantity == 3
    assert lots[1].quantity == 6
    progress = client.get("/api/v1/kitchen/nutrition/progress", headers=AUTH_HEADERS).json()
    assert progress["protein_g_consumed"] == 28


def test_manual_external_meal_updates_nutrition_without_inventory(client):
    _post(client, "/kitchen/nutrition-target", {"calories_target": 2000, "protein_g_target": 140})
    meal = _post(client, "/kitchen/meals/manual", {"name": "Cafe bowl", "calories": 650, "protein_g": 42, "source": "external"})
    assert meal["recipe_id"] is None
    progress = client.get("/api/v1/kitchen/nutrition/progress", headers=AUTH_HEADERS).json()
    assert progress["calories_consumed"] == 650
    assert progress["calories_remaining"] == 1350


def test_shopping_forecast_dedupes_and_syncs_planner_actions(client):
    _post(client, "/kitchen/inventory", {"ingredient_name": "Rice", "quantity": 500, "unit": "g"})
    recipe = _post(
        client,
        "/kitchen/recipes",
        {
            "name": "Chicken rice bowl",
            "preparation_minutes": 10,
            "cooking_minutes": 20,
            "servings": 1,
            "calories_per_serving": 620,
            "protein_g_per_serving": 48,
            "protein_family": "chicken",
            "ingredients": [
                {"ingredient_name": "Rice", "quantity": 100, "unit": "g"},
                {"ingredient_name": "Chicken breast", "quantity": 200, "unit": "g"},
            ],
        },
    )
    first = _post(client, "/kitchen/shopping-forecast", {"window_days": 3})
    second = _post(client, "/kitchen/shopping-forecast", {"window_days": 3})
    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["metadata_json"]["recipe_id"] == recipe["id"]
    assert first[0]["items"][0]["ingredient_name"] == "Chicken breast"

    actions = _post(client, "/kitchen/shopping-needs/sync-actions", {})
    assert actions[0]["domain"] == "kitchen"
    assert actions[0]["metadata_json"]["kitchen_shopping_need_id"] == first[0]["id"]
    planning_pool = client.get("/api/v1/actions?planning_pool=true&domain=kitchen", headers=AUTH_HEADERS).json()
    assert planning_pool[0]["context"] == "shopping"


def test_no_shopping_mode_filters_missing_recipes(client):
    _post(client, "/kitchen/inventory", {"ingredient_name": "Oats", "quantity": 300, "unit": "g"})
    _post(
        client,
        "/kitchen/recipes",
        {
            "name": "Oats",
            "servings": 1,
            "calories_per_serving": 420,
            "protein_g_per_serving": 18,
            "ingredients": [{"ingredient_name": "Oats", "quantity": 80, "unit": "g"}],
        },
    )
    _post(
        client,
        "/kitchen/recipes",
        {
            "name": "Salmon oats",
            "servings": 1,
            "calories_per_serving": 720,
            "protein_g_per_serving": 55,
            "ingredients": [{"ingredient_name": "Salmon", "quantity": 200, "unit": "g"}],
        },
    )
    recs = client.get("/api/v1/kitchen/recommendations?no_shopping=true", headers=AUTH_HEADERS).json()
    assert [item["recipe"]["name"] for item in recs] == ["Oats"]


def test_chef_assistant_can_read_kitchen_recommendations(client):
    _post(client, "/kitchen/inventory", {"ingredient_name": "Greek yogurt", "quantity": 2, "unit": "count"})
    _post(
        client,
        "/kitchen/recipes",
        {
            "name": "Yogurt bowl",
            "servings": 1,
            "calories_per_serving": 320,
            "protein_g_per_serving": 35,
            "ingredients": [{"ingredient_name": "Greek yogurt", "quantity": 1, "unit": "count"}],
        },
    )
    response = _post(client, "/assistant/message", {"message": "What should I eat without shopping?", "role": "CHEF"})
    assert response["response_type"] == "INFORMATION"
    assert "Yogurt bowl" in response["message"] or "recommendation" in response["message"].lower()
