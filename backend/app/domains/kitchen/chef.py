from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attention.schemas import AttentionAction
from app.communication.composer import ResponseComposer
from app.communication.schemas import CommunicativeIntent, ResponseModePreference, SpeechAct, StructuredFact
from app.core.config import Settings
from app.database.models import MealHistory, Recipe, UserProfile
from app.domains.finance.contracts import GroceryBudgetSignal, grocery_budget_signal
from app.domains.fitness.contracts import FitnessNutritionContext, nutrition_context
from app.domains.kitchen import service as kitchen_service
from app.domains.kitchen.intent import MealIntentInterpretation, interpret_meal_intent
from app.domains.kitchen.schemas import (
    ChefIntentRecommendationRead,
    ChefIntentRequest,
    ChefMealOptionRead,
    ExpiryPriority,
    HeavinessPreference,
    IngredientRequirementRead,
    InventoryPreference,
    MealIntent,
)
from app.events.service import append_event
from app.memory.schemas import RecommendationCreate, RecommendationOptionCreate, RecommendationOutcomeCreate
from app.recommendations import service as recommendation_service


CHEF_POLICY_VERSION = "chef-candidate-v1"
MEAT_TERMS = {"meat", "beef", "chicken", "lamb", "turkey", "pork", "fish", "seafood"}


def _tokens(*values: str) -> set[str]:
    return {token for value in values for token in value.lower().replace("-", "_").split() if token}


def _recipe_terms(recipe: Recipe) -> set[str]:
    return _tokens(recipe.name, recipe.protein_family or "", *(recipe.tags or []))


def _hard_filter(recipe: Recipe, intent: MealIntent, ingredient_names: set[str]) -> list[str]:
    reasons: list[str] = []
    total_minutes = recipe.preparation_minutes + recipe.cooking_minutes
    if intent.max_total_minutes is not None and total_minutes > intent.max_total_minutes:
        reasons.append("exceeds_hard_total_time")
    if intent.max_active_minutes is not None and recipe.preparation_minutes > intent.max_active_minutes:
        reasons.append("exceeds_hard_active_time")
    excluded = set(intent.ingredient_exclusions)
    if excluded and any(any(exclusion in ingredient for exclusion in excluded) for ingredient in ingredient_names):
        reasons.append("explicit_ingredient_exclusion")
    terms = _recipe_terms(recipe)
    constraints = set(intent.dietary_constraints)
    if "vegetarian" in constraints and terms.intersection(MEAT_TERMS):
        reasons.append("vegetarian_constraint")
    if "vegan" in constraints and terms.intersection(MEAT_TERMS | {"egg", "eggs", "dairy", "cheese", "milk", "yogurt"}):
        reasons.append("vegan_constraint")
    required_equipment = {tag.split(":", 1)[1].lower() for tag in (recipe.tags or []) if tag.lower().startswith("equipment:")}
    if required_equipment.intersection(intent.unavailable_equipment):
        reasons.append("required_equipment_unavailable")
    return reasons


def _intent_factor(recipe: Recipe, intent: MealIntent) -> tuple[dict[str, float], list[str]]:
    terms = _recipe_terms(recipe)
    reasons: list[str] = []
    cuisine = 0.0
    if intent.cuisine_preferences and terms.intersection(intent.cuisine_preferences):
        cuisine = 12.0
        reasons.append("cuisine_match")
    style = 0.0
    if intent.styles and terms.intersection(intent.styles):
        style = 10.0
        reasons.append("style_match")
    protein = 0.0
    requested = set(intent.protein_preferences)
    if requested and (terms.intersection(requested) or ("meat" in requested and terms.intersection(MEAT_TERMS))):
        protein = 12.0
        reasons.append("protein_match")
    ingredient = 0.0
    if intent.ingredient_preferences and terms.intersection(intent.ingredient_preferences):
        ingredient = 5.0
        reasons.append("ingredient_match")
    return {
        "intent_match": min(12.0, cuisine + style + protein + ingredient),
        "cuisine_match": cuisine,
        "style_match": style,
        "protein_match": protein,
    }, reasons


def _inventory_features(db: Session, user: UserProfile, recipe: Recipe, intent: MealIntent) -> tuple[str, list[IngredientRequirementRead], list[str], list[str], float]:
    multiplier = intent.servings / recipe.servings
    requirements: list[IngredientRequirementRead] = []
    missing: list[str] = []
    expiring: list[str] = []
    required_rows = [item for item in kitchen_service._recipe_ingredients(db, user, recipe.id) if not item.optional]
    for ingredient in required_rows:
        required = kitchen_service._required_canonical(ingredient, multiplier)
        available, _, lots = kitchen_service._available_for_ingredient(db, user, ingredient)
        missing_amount = max(0.0, required - available)
        expiring_soon = any(
            lot.expires_at and kitchen_service._now() <= kitchen_service._aware(lot.expires_at) <= kitchen_service._now() + timedelta(days=kitchen_service.EXPIRY_SOON_DAYS)
            for lot in lots
        )
        if missing_amount > 1e-6:
            missing.append(ingredient.ingredient_name)
        if expiring_soon:
            expiring.append(ingredient.ingredient_name)
        requirements.append(IngredientRequirementRead(
            ingredient_name=ingredient.ingredient_name,
            required_quantity=round(kitchen_service._from_canonical(required, ingredient.unit), 3),
            available_quantity=round(kitchen_service._from_canonical(min(available, required), ingredient.unit), 3),
            missing_quantity=round(kitchen_service._from_canonical(missing_amount, ingredient.unit), 3),
            unit=ingredient.unit,
            expiring_soon=expiring_soon,
        ))
    if not missing:
        status = "FULLY_IN_STOCK"
    elif requirements and len(missing) / len(requirements) <= 0.4:
        status = "MOSTLY_IN_STOCK"
    else:
        status = "SHOPPING_REQUIRED"
    available_ratio = 1.0 - (len(missing) / len(requirements) if requirements else 0.0)
    return status, requirements, missing, sorted(set(expiring)), available_ratio


def _nutrition_features(recipe: Recipe, intent: MealIntent, progress, fitness: FitnessNutritionContext) -> tuple[dict, str, float, float, list[str]]:
    calories = round(recipe.calories_per_serving * intent.servings, 2)
    protein = round(recipe.protein_g_per_serving * intent.servings, 2)
    carbs = round(recipe.carbs_g_per_serving * intent.servings, 2) if recipe.carbs_g_per_serving is not None else None
    fat = round(recipe.fat_g_per_serving * intent.servings, 2) if recipe.fat_g_per_serving is not None else None
    confidence = "COMPLETE" if calories > 0 and protein > 0 and carbs is not None and fat is not None else "PARTIAL" if calories > 0 or protein > 0 else "UNKNOWN"
    reasons: list[str] = []
    protein_fit = 0.0
    desired_protein = intent.desired_protein_min_g
    if desired_protein is None and intent.protein_priority == "HIGH":
        desired_protein = max(25.0, min(60.0, (progress.protein_g_remaining or 50.0) * 0.5))
    if desired_protein is not None:
        protein_fit = min(14.0, 14.0 * protein / max(desired_protein, 1)) if protein <= desired_protein else 14.0
        if protein >= desired_protein:
            reasons.append("protein_target_fit")
    calorie_fit = 0.0
    target_max = intent.desired_calorie_max or progress.calories_remaining
    if target_max is not None:
        calorie_fit = 8.0 if calories <= max(target_max, 1) else max(-8.0, 8.0 - (calories - target_max) / 75.0)
        if calorie_fit > 0:
            reasons.append("calorie_target_fit")
    heaviness_fit = 0.0
    if intent.heaviness_preference in {HeavinessPreference.light, HeavinessPreference.light_to_medium}:
        heaviness_fit = 8.0 if calories <= 650 and (fat is None or fat <= 25) else -8.0
        if heaviness_fit > 0:
            reasons.append("heaviness_fit")
    recovery_fit = 4.0 if fitness.recovery_context == "POST_WORKOUT" and protein >= 25 else 0.0
    if recovery_fit:
        reasons.append("recovery_fit")
    return {
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "source": "canonical_recipe_snapshot",
    }, confidence, round(protein_fit + calorie_fit + heaviness_fit, 2), recovery_fit, reasons


def _render_option(option: ChefMealOptionRead) -> str:
    facts = (
        StructuredFact(key="meal", value=option.recipe.name, source_ref=option.recipe.id),
        StructuredFact(key="time", value=option.total_minutes, unit="minutes", source_ref=option.recipe.id),
        StructuredFact(key="inventory", value=option.inventory_status, source_ref=option.recipe.id),
        StructuredFact(key="protein", value=option.nutrition.get("protein_g"), unit="g", source_ref=option.recipe.id),
        StructuredFact(key="missing_count", value=len(option.missing_ingredients), source_ref=option.recipe.id),
    )
    intent = CommunicativeIntent(
        purpose=SpeechAct.inform,
        attention_action=AttentionAction.show_passively,
        reason_code="chef_option",
        facts=facts,
        response_mode_preference=ResponseModePreference.deterministic,
        fallback_template_key="chef_option",
    )
    return ResponseComposer().deterministic_text(intent)


def _candidate(db: Session, user: UserProfile, recipe: Recipe, intent: MealIntent, progress, fitness: FitnessNutritionContext, budget: GroceryBudgetSignal) -> ChefMealOptionRead | None:
    ingredients = kitchen_service._recipe_ingredients(db, user, recipe.id)
    hard = _hard_filter(recipe, intent, {item.ingredient_name.lower() for item in ingredients})
    if hard:
        return None
    inventory_status, requirements, missing, expiring, available_ratio = _inventory_features(db, user, recipe, intent)
    if intent.inventory_preference == InventoryPreference.use_what_i_have and missing:
        return None
    if intent.inventory_preference == InventoryPreference.minimal_shopping and len(missing) > 1:
        return None
    factors, reasons = _intent_factor(recipe, intent)
    factors["time_fit"] = 10.0 if intent.max_total_minutes is not None else max(0.0, 8.0 - (recipe.preparation_minutes + recipe.cooking_minutes) / 20.0)
    factors["inventory_fit"] = round(18.0 * available_ratio, 2)
    factors["expiry_value"] = min(10.0, len(expiring) * (5.0 if intent.expiry_priority == ExpiryPriority.prefer_expiring else 3.0))
    nutrition, nutrition_confidence, nutrition_fit, recovery_fit, nutrition_reasons = _nutrition_features(recipe, intent, progress, fitness)
    factors["nutrition_fit"] = nutrition_fit
    factors["recovery_fit"] = recovery_fit
    factors["budget_fit"] = 0.0
    factors["preference_fit"] = kitchen_service._preference_score(db, user, recipe)
    recent = kitchen_service._recent_meals(db, user, 14)
    repeat_count = sum(1 for meal in recent[:8] if meal.recipe_id == recipe.id)
    factors["recent_repetition"] = -min(18.0, repeat_count * 9.0)
    factors["novelty_fit"] = 5.0 if not repeat_count and intent.novelty_preference.value != "FAMILIAR" else 0.0
    competency_fit, technique_opportunities = kitchen_service._technique_fit(db, user, recipe)
    factors["competency_fit"] = competency_fit
    factors["equipment_fit"] = 2.0
    reason_codes = reasons + nutrition_reasons
    if inventory_status == "FULLY_IN_STOCK":
        reason_codes.append("fully_in_stock")
    elif inventory_status == "MOSTLY_IN_STOCK":
        reason_codes.append("minimal_shopping")
    if expiring:
        reason_codes.append("uses_expiring_inventory")
    if repeat_count:
        reason_codes.append("recent_repeat_penalty")
    if budget.status == "UNKNOWN":
        reason_codes.append("grocery_cost_unknown")
    score = round(20.0 + sum(factors.values()), 2)
    option = ChefMealOptionRead(
        recipe=kitchen_service._recipe_read(db, user, recipe),
        score=score,
        score_factors=factors,
        reason_codes=list(dict.fromkeys(reason_codes)),
        why_it_fits="",
        total_minutes=recipe.preparation_minutes + recipe.cooking_minutes,
        active_minutes=recipe.preparation_minutes,
        nutrition=nutrition,
        nutrition_confidence=nutrition_confidence,
        inventory_status=inventory_status,
        ingredient_requirements=requirements,
        missing_ingredients=missing,
        expiring_ingredients_used=expiring,
        estimated_grocery_delta=None,
        grocery_currency=budget.currency,
        budget_status=budget.status,
        technique_opportunities=technique_opportunities,
    )
    return option.model_copy(update={"why_it_fits": _render_option(option)})


def recommend_from_text(db: Session, user: UserProfile, request: ChefIntentRequest, settings: Settings, *, gateway=None) -> ChefIntentRecommendationRead:
    interpretation: MealIntentInterpretation = interpret_meal_intent(db, user, request, settings, gateway=gateway)
    intent = interpretation.intent
    fitness = nutrition_context(db, user)
    progress = kitchen_service.daily_nutrition_progress(db, user)
    budget = grocery_budget_signal(db, user)
    recipes = list(db.scalars(select(Recipe).where(Recipe.user_id == user.id, Recipe.active.is_(True))).all())
    candidates = [item for recipe in recipes if (item := _candidate(db, user, recipe, intent, progress, fitness, budget)) is not None]
    candidates.sort(key=lambda item: (-item.score, item.total_minutes, item.recipe.name.lower()))
    candidates = candidates[: request.limit]
    if not candidates:
        return ChefIntentRecommendationRead(
            intent=intent,
            interpretation_mode=interpretation.mode,
            interpretation_warning=interpretation.warning,
            options=[],
            response_text="I couldn't find a saved recipe that satisfies those constraints. Nothing was changed.",
        )
    signature = sha256(f"{user.id}|{user.world_revision}|{intent.model_dump_json()}".encode()).hexdigest()[:32]
    created = recommendation_service.create_recommendation(db, user, RecommendationCreate(
        domain="kitchen",
        kind="meal",
        title="Chef meal options",
        reason="Deterministic ranking from a validated MealIntent and canonical domain signals.",
        context_snapshot=jsonable_encoder({
            "policy_version": CHEF_POLICY_VERSION,
            "meal_intent": intent.model_dump(mode="json"),
            "fitness_context": asdict(fitness),
            "grocery_budget_signal": asdict(budget),
            "full_finance_data_used": False,
            "ai_arithmetic_used": False,
        }),
        options=[RecommendationOptionCreate(
            label=item.recipe.name,
            rank=index,
            score=item.score,
            payload_json={
                "score_factors": item.score_factors,
                "reason_codes": item.reason_codes,
                "nutrition": item.nutrition,
                "nutrition_confidence": item.nutrition_confidence,
                "inventory_status": item.inventory_status,
                "ingredient_requirements": [value.model_dump(mode="json") for value in item.ingredient_requirements],
                "missing_ingredients": item.missing_ingredients,
                "expiring_ingredients_used": item.expiring_ingredients_used,
                "estimated_grocery_delta": None,
                "total_minutes": item.total_minutes,
                "active_minutes": item.active_minutes,
            },
            reference_type="recipe",
            reference_id=item.recipe.id,
        ) for index, item in enumerate(candidates, start=1)],
        idempotency_key=f"chef-intent:{signature}",
    ))
    option_by_recipe = {option.reference_id: option for option in created.options}
    candidates = [item.model_copy(update={"recommendation_id": created.id, "option_id": option_by_recipe[item.recipe.id].id}) for item in candidates]
    for item in candidates:
        recommendation_service.record_outcome(
            db,
            user,
            RecommendationOutcomeCreate(
                domain="kitchen",
                recommendation_type="meal",
                recommendation_summary=item.recipe.name,
                outcome="shown",
                source_entity_type="recipe",
                source_entity_id=item.recipe.id,
                recommendation_id=created.id,
                option_id=item.option_id,
                idempotency_key=f"shown:{item.option_id}",
            ),
        )
    append_event(db, user, event_type="kitchen.recommendation_created", aggregate_type="recommendation", aggregate_id=created.id,
                 payload={"recommendation_id": created.id, "option_count": len(candidates), "policy_version": CHEF_POLICY_VERSION}, outbox=True)
    return ChefIntentRecommendationRead(
        intent=intent,
        interpretation_mode=interpretation.mode,
        interpretation_warning=interpretation.warning,
        recommendation_id=created.id,
        options=candidates,
        response_text=f"I found {len(candidates)} meal option{'s' if len(candidates) != 1 else ''} that fit the constraints.",
    )
