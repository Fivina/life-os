from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from math import floor
from types import SimpleNamespace

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionRead
from app.actions.service import create_action, list_actions
from app.database.models import (
    Action,
    ActiveWorkspace,
    CookingCompetency,
    CookingCompetencyEvidence,
    CookingTechnique,
    FinanceTransaction,
    Ingredient,
    InventoryItem,
    InventoryLot,
    MealFeedback,
    MealHistory,
    MealPlan,
    MemoryItem,
    NutritionTarget,
    PreferenceEvidence,
    Recommendation,
    RecommendationOption,
    RecommendationOutcome,
    Recipe,
    RecipeIngredient,
    RecipeTechnique,
    ShoppingNeed,
    ShoppingNeedItem,
    UserProfile,
)
from app.domains.finance.contracts import grocery_budget_context
from app.domains.fitness.contracts import nutrition_context as fitness_nutrition_context
from app.domains.kitchen.normalization import normalize_name, resolve_ingredient
from app.domains.kitchen.schemas import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryMutationCreate,
    InventoryStapleUpdate,
    InventoryLotCreate,
    InventoryLotRead,
    KitchenStatusRead,
    ChefRecommendationSetRead,
    CompetencyRead,
    MealCompleteRequest,
    MealHistoryRead,
    MealManualCreate,
    MealRecommendationRead,
    MealPlanCompleteRequest,
    MealPlanModifyRequest,
    MealPlanRead,
    MealSelectionCreate,
    NutritionProgressRead,
    NutritionTargetRead,
    NutritionTargetUpsert,
    RecipeCreate,
    RecipeIngredientRead,
    RecipeRead,
    RecommendationRequest,
    ShoppingForecastRequest,
    ShoppingAggregateRead,
    ShoppingNeedItemRead,
    ShoppingNeedRead,
    ManualShoppingNeedCreate,
    ShoppingPurchaseCreate,
    CookingSessionStartRequest,
    CookingSessionUpdateRequest,
)
from app.events.service import append_event
from app.memory.schemas import RecommendationCreate, RecommendationOptionCreate, RecommendationOutcomeCreate
from app.recommendations import service as recommendation_service
from app.workspaces.schemas import CookingWorkspacePayload, WorkspaceType, workspace_to_read
from app.workspaces.service import ActiveWorkspaceService

MASS_UNITS = {"g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "l": 1000.0}
COUNT_UNITS = {"count": 1.0}
SERVING_UNITS = {"serving": 1.0}
UNIT_ALIASES = {
    "item": "count",
    "items": "count",
    "each": "count",
    "tub": "count",
    "pack": "count",
    "package": "count",
    "container": "count",
    "can": "count",
    "servings": "serving",
}
EXPIRY_SOON_DAYS = 3


@dataclass(frozen=True)
class Quantity:
    amount: float
    unit: str
    family: str


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_unit(unit: str) -> str:
    return UNIT_ALIASES.get(unit.strip().lower(), unit.strip().lower())


def _quantity(amount: float, unit: str) -> Quantity:
    normalized = _normalize_unit(unit)
    if normalized in MASS_UNITS:
        return Quantity(amount * MASS_UNITS[normalized], "g", "mass")
    if normalized in VOLUME_UNITS:
        return Quantity(amount * VOLUME_UNITS[normalized], "ml", "volume")
    if normalized in COUNT_UNITS:
        return Quantity(amount, "count", "count")
    if normalized in SERVING_UNITS:
        return Quantity(amount, "serving", "serving")
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported unit: {unit}.")


def _ensure_compatible(required_unit: str, lot_unit: str) -> None:
    required = _quantity(1, required_unit)
    actual = _quantity(1, lot_unit)
    if required.family != actual.family:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Incompatible units: cannot use {lot_unit} for {required_unit}.",
        )


def _from_canonical(amount: float, canonical_unit: str) -> float:
    unit = _normalize_unit(canonical_unit)
    if unit == "kg":
        return amount / 1000
    if unit == "l":
        return amount / 1000
    return amount


def _expires_at_from_payload(payload: InventoryItemCreate | InventoryLotCreate) -> datetime | None:
    if getattr(payload, "expires_at", None):
        return payload.expires_at
    expires_on = getattr(payload, "expires_on", None)
    if expires_on:
        return datetime.combine(expires_on, time(23, 59, 59), tzinfo=UTC)
    return None


def _start_end_for_day(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0, 0), tzinfo=UTC)
    return start, start + timedelta(days=1)


def _expiry_status(lots: list[InventoryLot], now: datetime | None = None) -> str:
    active_expiries = [_aware(lot.expires_at) for lot in lots if lot.status == "active" and lot.quantity > 0 and lot.expires_at]
    if not active_expiries:
        return "no_expiry"
    current = now or _now()
    soon = current + timedelta(days=EXPIRY_SOON_DAYS)
    if any(expiry < current for expiry in active_expiries):
        return "expired"
    if any(expiry.date() == current.date() for expiry in active_expiries):
        return "expires_today"
    if any(expiry <= soon for expiry in active_expiries):
        return "expires_soon"
    return "later"


def _active_lots_for_item(db: Session, user: UserProfile, item_id: str) -> list[InventoryLot]:
    return list(
        db.scalars(
            select(InventoryLot)
            .where(InventoryLot.user_id == user.id, InventoryLot.inventory_item_id == item_id, InventoryLot.status == "active", InventoryLot.quantity > 0)
            .order_by(InventoryLot.expires_at.asc().nulls_last(), InventoryLot.purchased_at.asc().nulls_last(), InventoryLot.created_at.asc())
        ).all()
    )


def _item_total(db: Session, user: UserProfile, item: InventoryItem) -> float:
    lots = _active_lots_for_item(db, user, item.id)
    total = 0.0
    for lot in lots:
        _ensure_compatible(item.canonical_unit, lot.unit)
        total += _quantity(lot.quantity, lot.unit).amount
    return round(_from_canonical(total, item.canonical_unit), 3)


def _sync_legacy_quantity(db: Session, user: UserProfile, item: InventoryItem) -> None:
    item.quantity = _item_total(db, user, item)
    item.unit = item.canonical_unit


def _inventory_read(db: Session, user: UserProfile, item: InventoryItem) -> InventoryItemRead:
    lots = _active_lots_for_item(db, user, item.id)
    total = _item_total(db, user, item)
    return InventoryItemRead(
        id=item.id,
        ingredient_name=item.ingredient_name,
        quantity=item.quantity,
        unit=item.unit,
        expires_on=item.expires_on,
        source=item.source,
        category=item.category,
        canonical_unit=item.canonical_unit,
        default_storage_location=item.default_storage_location,
        is_staple=item.is_staple,
        restock_threshold=item.restock_threshold,
        restock_target=item.restock_target,
        active=item.active,
        notes=item.notes,
        total_quantity=total,
        expiry_status=_expiry_status(lots),
        lots=[InventoryLotRead.model_validate(lot) for lot in lots],
        version=item.version,
    )


def _recipe_ingredients(db: Session, user: UserProfile, recipe_id: str) -> list[RecipeIngredient]:
    return list(
        db.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.user_id == user.id, RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index.asc(), RecipeIngredient.created_at.asc())
        ).all()
    )


def _recipe_read(db: Session, user: UserProfile, recipe: Recipe) -> RecipeRead:
    ingredients = _recipe_ingredients(db, user, recipe.id)
    technique_rows = list(db.scalars(select(RecipeTechnique).where(RecipeTechnique.user_id == user.id, RecipeTechnique.recipe_id == recipe.id)).all())
    techniques = []
    for link in technique_rows:
        technique = db.get(CookingTechnique, link.technique_id)
        if technique:
            techniques.append({"id": technique.id, "key": technique.key, "name": technique.name, "required_level": link.required_level, "importance": link.importance})
    return RecipeRead(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        preparation_minutes=recipe.preparation_minutes,
        cooking_minutes=recipe.cooking_minutes,
        servings=recipe.servings,
        calories_per_serving=recipe.calories_per_serving,
        protein_g_per_serving=recipe.protein_g_per_serving,
        carbs_g_per_serving=recipe.carbs_g_per_serving,
        fat_g_per_serving=recipe.fat_g_per_serving,
        protein_family=recipe.protein_family,
        difficulty=recipe.difficulty,
        tags=recipe.tags or [],
        steps=recipe.steps_json or [],
        techniques=techniques,
        active=recipe.active,
        notes=recipe.notes,
        ingredients=[RecipeIngredientRead.model_validate(item) for item in ingredients],
        version=recipe.version,
    )


def _shopping_need_read(db: Session, user: UserProfile, need: ShoppingNeed) -> ShoppingNeedRead:
    items = list(
        db.scalars(
            select(ShoppingNeedItem)
            .where(ShoppingNeedItem.user_id == user.id, ShoppingNeedItem.shopping_need_id == need.id)
            .order_by(ShoppingNeedItem.created_at.asc())
        ).all()
    )
    return ShoppingNeedRead(
        id=need.id,
        title=need.title,
        status=need.status,
        required_by=need.required_by,
        reason=need.reason,
        source=need.source,
        forecast_window_days=need.forecast_window_days,
        metadata_json=need.metadata_json,
        meal_plan_id=need.meal_plan_id,
        action_id=need.action_id,
        estimated_total=float(need.estimated_total) if need.estimated_total is not None else None,
        currency=need.currency,
        items=[ShoppingNeedItemRead.model_validate(item) for item in items],
        version=need.version,
    )


def _find_item_for_ingredient(db: Session, user: UserProfile, ingredient_name: str, inventory_item_id: str | None = None) -> InventoryItem | None:
    if inventory_item_id:
        item = db.get(InventoryItem, inventory_item_id)
        return item if item and item.user_id == user.id else None
    normalized = normalize_name(ingredient_name)
    return db.scalar(select(InventoryItem).outerjoin(Ingredient, Ingredient.id == InventoryItem.ingredient_id).where(InventoryItem.user_id == user.id, InventoryItem.active.is_(True), (Ingredient.normalized_name == normalized) | (InventoryItem.ingredient_name.ilike(ingredient_name))))


def add_inventory_item(db: Session, user: UserProfile, payload: InventoryItemCreate) -> InventoryItemRead:
    name = (payload.ingredient_name or payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ingredient_name is required.")
    canonical_unit = payload.unit if payload.canonical_unit == "count" and payload.unit != "count" else payload.canonical_unit
    ingredient = resolve_ingredient(db, user, name, default_unit=canonical_unit, category=payload.category, source=payload.source)
    item = db.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.ingredient_id == ingredient.id, InventoryItem.active.is_(True)))
    if item is None:
        item = InventoryItem(user_id=user.id, ingredient_id=ingredient.id, ingredient_name=ingredient.name, quantity=0, unit=canonical_unit, expires_on=payload.expires_on, source=payload.source, category=payload.category, canonical_unit=canonical_unit, default_storage_location=payload.default_storage_location, is_staple=bool(payload.is_staple), restock_threshold=payload.restock_threshold, restock_target=payload.restock_target, notes=payload.notes)
        db.add(item)
        db.flush()
    else:
        _ensure_compatible(item.canonical_unit, payload.unit)
        if payload.is_staple is not None:
            item.is_staple = payload.is_staple
        if payload.restock_threshold is not None:
            item.restock_threshold = payload.restock_threshold
        if payload.restock_target is not None:
            item.restock_target = payload.restock_target
    if item.is_staple and item.restock_threshold is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A staple needs a restock threshold.")
    if item.restock_target is not None and item.restock_threshold is not None and item.restock_target < item.restock_threshold:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Restock target must be at least the threshold.")
    if payload.quantity > 0:
        lot = InventoryLot(
            user_id=user.id,
            inventory_item_id=item.id,
            quantity=payload.quantity,
            unit=payload.unit,
            purchased_at=_now(),
            expires_at=_expires_at_from_payload(payload),
            storage_location=payload.default_storage_location,
            source=payload.source,
            status="active",
        )
        _ensure_compatible(item.canonical_unit, lot.unit)
        db.add(lot)
        db.flush()
    _sync_legacy_quantity(db, user, item)
    append_event(
        db,
        user,
        event_type="kitchen.inventory.changed",
        aggregate_type="inventory_item",
        aggregate_id=item.id,
        payload={"inventory_item_id": item.id, "ingredient_name": item.ingredient_name, "quantity": item.quantity, "unit": item.unit},
        outbox=True,
    )
    return _inventory_read(db, user, item)


def add_inventory_lot(db: Session, user: UserProfile, item_id: str, payload: InventoryLotCreate) -> InventoryItemRead:
    item = db.get(InventoryItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")
    _ensure_compatible(item.canonical_unit, payload.unit)
    lot = InventoryLot(
        user_id=user.id,
        inventory_item_id=item.id,
        quantity=payload.quantity,
        unit=payload.unit,
        purchased_at=payload.purchased_at or _now(),
        expires_at=_expires_at_from_payload(payload),
        storage_location=payload.storage_location or item.default_storage_location,
        source=payload.source,
        status="active",
        notes=payload.notes,
    )
    db.add(lot)
    db.flush()
    _sync_legacy_quantity(db, user, item)
    item.version += 1
    append_event(
        db,
        user,
        event_type="kitchen.inventory.changed",
        aggregate_type="inventory_item",
        aggregate_id=item.id,
        payload={"inventory_item_id": item.id, "lot_id": lot.id, "quantity": payload.quantity, "unit": payload.unit},
        outbox=True,
    )
    return _inventory_read(db, user, item)


def list_inventory(db: Session, user: UserProfile) -> list[InventoryItemRead]:
    items = list(
        db.scalars(
            select(InventoryItem)
            .where(InventoryItem.user_id == user.id, InventoryItem.active.is_(True))
            .order_by(InventoryItem.ingredient_name.asc())
        ).all()
    )
    return [_inventory_read(db, user, item) for item in items]


def update_inventory_staple(db: Session, user: UserProfile, item_id: str, payload: InventoryStapleUpdate) -> InventoryItemRead:
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")
    if payload.is_staple and payload.restock_threshold is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A staple needs a restock threshold.")
    if payload.restock_target is not None and payload.restock_threshold is not None and payload.restock_target < payload.restock_threshold:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Restock target must be at least the threshold.")
    item.is_staple = payload.is_staple
    item.restock_threshold = payload.restock_threshold if payload.is_staple else None
    item.restock_target = payload.restock_target if payload.is_staple else None
    item.version += 1
    append_event(db, user, event_type="inventory.staple_updated", aggregate_type="inventory_item", aggregate_id=item.id, payload={"inventory_item_id": item.id, "is_staple": item.is_staple, "restock_threshold": item.restock_threshold, "restock_target": item.restock_target}, outbox=True)
    return _inventory_read(db, user, item)


def mutate_inventory(db: Session, user: UserProfile, item_id: str, payload: InventoryMutationCreate) -> InventoryItemRead:
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")
    _ensure_compatible(item.canonical_unit, payload.unit)
    if payload.operation == "add":
        db.add(InventoryLot(user_id=user.id, inventory_item_id=item.id, quantity=payload.quantity, unit=payload.unit, purchased_at=_now(), expires_at=payload.expires_at, storage_location=item.default_storage_location, source="manual", status="active", notes=payload.reason))
    elif payload.operation == "expire":
        lots = _active_lots_for_item(db, user, item.id)
        for lot in lots:
            lot.status = "expired"
            lot.version += 1
    else:
        requested = _quantity(payload.quantity, payload.unit).amount
        if payload.operation in {"adjust", "reconcile"}:
            current = _quantity(_item_total(db, user, item), item.canonical_unit).amount
            if requested > current:
                added = _from_canonical(requested - current, payload.unit)
                db.add(InventoryLot(user_id=user.id, inventory_item_id=item.id, quantity=added, unit=payload.unit, purchased_at=_now(), expires_at=payload.expires_at, storage_location=item.default_storage_location, source=payload.operation, status="active", notes=payload.reason))
                requested = 0
            else:
                requested = current - requested
        remaining = requested
        for lot in _active_lots_for_item(db, user, item.id):
            available = _quantity(lot.quantity, lot.unit).amount
            used = min(available, remaining)
            lot.quantity = max(0, lot.quantity - _from_canonical(used, lot.unit))
            lot.status = "consumed" if lot.quantity <= 0 and payload.operation == "consume" else "discarded" if lot.quantity <= 0 and payload.operation == "discard" else "adjusted" if lot.quantity <= 0 and payload.operation in {"adjust", "reconcile"} else lot.status
            lot.version += 1
            remaining -= used
            if remaining <= 0:
                break
        if remaining > 0 and payload.operation not in {"adjust", "reconcile"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not enough compatible inventory for this mutation.")
    db.flush()
    _sync_legacy_quantity(db, user, item)
    item.version += 1
    append_event(db, user, event_type=f"inventory.{payload.operation}", aggregate_type="inventory_item", aggregate_id=item.id, payload={"inventory_item_id": item.id, "quantity": payload.quantity, "unit": payload.unit, "reason": payload.reason}, outbox=True)
    return _inventory_read(db, user, item)


def create_recipe(db: Session, user: UserProfile, payload: RecipeCreate) -> RecipeRead:
    recipe = Recipe(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        preparation_minutes=payload.preparation_minutes,
        cooking_minutes=payload.cooking_minutes,
        servings=payload.servings,
        calories_per_serving=payload.calories_per_serving,
        protein_g_per_serving=payload.protein_g_per_serving,
        carbs_g_per_serving=payload.carbs_g_per_serving,
        fat_g_per_serving=payload.fat_g_per_serving,
        protein_family=payload.protein_family,
        difficulty=payload.difficulty,
        tags=payload.tags,
        steps_json=payload.steps,
        notes=payload.notes,
    )
    db.add(recipe)
    db.flush()
    for index, ingredient in enumerate(payload.ingredients):
        identity = resolve_ingredient(db, user, ingredient.ingredient_name, default_unit=ingredient.unit, category="food", source="recipe")
        item = _find_item_for_ingredient(db, user, ingredient.ingredient_name, ingredient.inventory_item_id)
        if item is not None:
            _ensure_compatible(item.canonical_unit, ingredient.unit)
        db.add(
            RecipeIngredient(
                user_id=user.id,
                recipe_id=recipe.id,
                ingredient_id=identity.id,
                inventory_item_id=item.id if item else ingredient.inventory_item_id,
                ingredient_name=ingredient.ingredient_name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                optional=ingredient.optional,
                substitution_group=ingredient.substitution_group,
                order_index=ingredient.order_index or index,
            )
        )
    for technique_payload in payload.techniques:
        key = normalize_name(str(technique_payload.get("key") or technique_payload.get("name") or "")).replace(" ", "_")
        if not key:
            continue
        technique = db.scalar(select(CookingTechnique).where(CookingTechnique.user_id == user.id, CookingTechnique.key == key))
        if technique is None:
            technique = CookingTechnique(user_id=user.id, key=key, name=str(technique_payload.get("name") or key.replace("_", " ").title()))
            db.add(technique)
            db.flush()
        db.add(RecipeTechnique(user_id=user.id, recipe_id=recipe.id, technique_id=technique.id, required_level=float(technique_payload.get("required_level", 1)), importance=float(technique_payload.get("importance", 1))))
    db.flush()
    append_event(
        db,
        user,
        event_type="kitchen.recipe.created",
        aggregate_type="recipe",
        aggregate_id=recipe.id,
        payload={"recipe_id": recipe.id, "name": recipe.name},
        outbox=True,
    )
    return _recipe_read(db, user, recipe)


def list_recipes(db: Session, user: UserProfile) -> list[RecipeRead]:
    recipes = list(db.scalars(select(Recipe).where(Recipe.user_id == user.id, Recipe.active.is_(True)).order_by(Recipe.name.asc())).all())
    return [_recipe_read(db, user, recipe) for recipe in recipes]


def get_recipe(db: Session, user: UserProfile, recipe_id: str) -> RecipeRead:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    return _recipe_read(db, user, recipe)


def upsert_nutrition_target(db: Session, user: UserProfile, payload: NutritionTargetUpsert) -> NutritionTargetRead:
    now = payload.effective_from or _now()
    active = db.scalar(select(NutritionTarget).where(NutritionTarget.user_id == user.id, NutritionTarget.status == "active"))
    if active is not None:
        active.status = "superseded"
        active.effective_to = now
        active.version += 1
    target = NutritionTarget(
        user_id=user.id,
        calories_target=payload.calories_target,
        protein_g_target=payload.protein_g_target,
        source=payload.source,
        effective_from=now,
        status="active",
        notes=payload.notes,
    )
    db.add(target)
    db.flush()
    append_event(
        db,
        user,
        event_type="kitchen.nutrition_target.updated",
        aggregate_type="nutrition_target",
        aggregate_id=target.id,
        payload={"calories_target": target.calories_target, "protein_g_target": target.protein_g_target},
        outbox=True,
    )
    return NutritionTargetRead.model_validate(target)


def get_active_nutrition_target(db: Session, user: UserProfile) -> NutritionTargetRead | None:
    target = db.scalar(select(NutritionTarget).where(NutritionTarget.user_id == user.id, NutritionTarget.status == "active").order_by(NutritionTarget.effective_from.desc()))
    return NutritionTargetRead.model_validate(target) if target else None


def daily_nutrition_progress(db: Session, user: UserProfile, day: date | None = None) -> NutritionProgressRead:
    target = db.scalar(select(NutritionTarget).where(NutritionTarget.user_id == user.id, NutritionTarget.status == "active").order_by(NutritionTarget.effective_from.desc()))
    target_day = day or _now().date()
    start, end = _start_end_for_day(target_day)
    meals = list(db.scalars(select(MealHistory).where(MealHistory.user_id == user.id, MealHistory.consumed_at >= start, MealHistory.consumed_at < end)).all())
    calories = round(sum(meal.calories_snapshot for meal in meals), 2)
    protein = round(sum(meal.protein_g_snapshot for meal in meals), 2)
    fitness_context = fitness_nutrition_context(db, user) if target is None else None
    calorie_target = target.calories_target if target else (fitness_context.calories_target_daily + fitness_context.training_day_adjustment.get("calories", 0) if fitness_context and fitness_context.calories_target_daily is not None else None)
    protein_target = target.protein_g_target if target else (fitness_context.protein_target_g + fitness_context.training_day_adjustment.get("protein_g", 0) if fitness_context and fitness_context.protein_target_g is not None else None)
    calories_remaining = round(calorie_target - calories, 2) if calorie_target is not None else None
    protein_remaining = round(protein_target - protein, 2) if protein_target is not None else None
    return NutritionProgressRead(
        date=target_day,
        calories_target=calorie_target,
        protein_g_target=protein_target,
        calories_consumed=calories,
        protein_g_consumed=protein,
        calories_remaining=calories_remaining,
        protein_g_remaining=protein_remaining,
        calories_over_target=round(max(0, calories - calorie_target), 2) if calorie_target is not None else 0,
        protein_g_over_target=round(max(0, protein - protein_target), 2) if protein_target is not None else 0,
    )


def _available_for_ingredient(db: Session, user: UserProfile, ingredient: RecipeIngredient) -> tuple[float, InventoryItem | None, list[InventoryLot]]:
    item = _find_item_for_ingredient(db, user, ingredient.ingredient_name, ingredient.inventory_item_id)
    if item is None:
        return 0.0, None, []
    _ensure_compatible(ingredient.unit, item.canonical_unit)
    current = _now()
    lots = [
        lot for lot in _active_lots_for_item(db, user, item.id)
        if lot.expires_at is None or _aware(lot.expires_at) >= current
    ]
    total = 0.0
    for lot in lots:
        _ensure_compatible(ingredient.unit, lot.unit)
        total += _quantity(lot.quantity, lot.unit).amount
    return total, item, lots


def _required_canonical(ingredient: RecipeIngredient, serving_multiplier: float) -> float:
    return _quantity(ingredient.quantity * serving_multiplier, ingredient.unit).amount


def _consume_ingredient(db: Session, user: UserProfile, ingredient: RecipeIngredient, serving_multiplier: float) -> list[dict]:
    required = _required_canonical(ingredient, serving_multiplier)
    available, item, lots = _available_for_ingredient(db, user, ingredient)
    if item is None or available + 1e-6 < required:
        if ingredient.optional:
            return []
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Not enough {ingredient.ingredient_name} in inventory.")
    consumed: list[dict] = []
    remaining = required
    for lot in lots:
        lot_amount = _quantity(lot.quantity, lot.unit).amount
        take = min(lot_amount, remaining)
        if take <= 0:
            continue
        next_amount = lot_amount - take
        lot.quantity = round(_from_canonical(next_amount, lot.unit), 3)
        lot.version += 1
        if lot.quantity <= 0.0001:
            lot.quantity = 0
            lot.status = "depleted"
        consumed.append({"lot_id": lot.id, "ingredient_name": ingredient.ingredient_name, "quantity_canonical": round(take, 3), "unit": _quantity(1, ingredient.unit).unit})
        remaining -= take
        if remaining <= 0.0001:
            break
    _sync_legacy_quantity(db, user, item)
    item.version += 1
    return consumed


def log_manual_meal(db: Session, user: UserProfile, payload: MealManualCreate) -> MealHistoryRead:
    meal = MealHistory(
        user_id=user.id,
        recipe_id=None,
        name_snapshot=payload.name,
        consumed_at=payload.consumed_at or _now(),
        servings=payload.servings,
        calories_snapshot=payload.calories,
        protein_g_snapshot=payload.protein_g,
        carbs_g_snapshot=payload.carbs_g,
        fat_g_snapshot=payload.fat_g,
        satisfaction=payload.satisfaction,
        source="external",
        source_plan_block_id=payload.source_plan_block_id,
        notes=payload.notes,
    )
    db.add(meal)
    db.flush()
    append_event(
        db,
        user,
        event_type="kitchen.meal.completed",
        aggregate_type="meal_history",
        aggregate_id=meal.id,
        payload={"meal_id": meal.id, "source": meal.source, "calories": meal.calories_snapshot, "protein_g": meal.protein_g_snapshot},
        outbox=True,
    )
    return MealHistoryRead.model_validate(meal)


def complete_recipe_meal(db: Session, user: UserProfile, recipe_id: str, payload: MealCompleteRequest) -> MealHistoryRead:
    if payload.idempotency_key:
        existing = db.scalar(select(MealHistory).where(MealHistory.user_id == user.id, MealHistory.idempotency_key == payload.idempotency_key))
        if existing is not None:
            return MealHistoryRead.model_validate(existing)
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id or not recipe.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    serving_multiplier = payload.servings / recipe.servings
    ingredients = _recipe_ingredients(db, user, recipe.id)
    consumed: list[dict] = []
    if payload.actual_ingredients:
        for actual in payload.actual_ingredients:
            name = str(actual.get("ingredient_name") or actual.get("name") or "").strip()
            quantity = float(actual.get("quantity") or 0)
            unit = str(actual.get("unit") or "").strip()
            if not name or quantity <= 0 or not unit:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Actual ingredient usage requires name, positive quantity and unit.")
            ingredient = SimpleNamespace(inventory_item_id=None, ingredient_name=name, quantity=quantity, unit=unit, optional=False)
            consumed.extend(_consume_ingredient(db, user, ingredient, 1.0))
    else:
        for ingredient in ingredients:
            consumed.extend(_consume_ingredient(db, user, ingredient, serving_multiplier))
    meal = MealHistory(
        user_id=user.id,
        recipe_id=recipe.id,
        name_snapshot=recipe.name,
        consumed_at=payload.consumed_at or _now(),
        servings=payload.servings,
        calories_snapshot=round(recipe.calories_per_serving * payload.servings, 2),
        protein_g_snapshot=round(recipe.protein_g_per_serving * payload.servings, 2),
        carbs_g_snapshot=round(recipe.carbs_g_per_serving * payload.servings, 2) if recipe.carbs_g_per_serving is not None else None,
        fat_g_snapshot=round(recipe.fat_g_per_serving * payload.servings, 2) if recipe.fat_g_per_serving is not None else None,
        satisfaction=payload.satisfaction,
        source="recipe",
        source_plan_block_id=payload.source_plan_block_id,
        idempotency_key=payload.idempotency_key,
        notes=payload.notes,
        actual_usage_json=consumed,
    )
    db.add(meal)
    db.flush()
    append_event(
        db,
        user,
        event_type="kitchen.inventory_consumed",
        aggregate_type="recipe",
        aggregate_id=recipe.id,
        payload={"recipe_id": recipe.id, "consumed": consumed},
        outbox=True,
    )
    append_event(
        db,
        user,
        event_type="kitchen.meal_history_created",
        aggregate_type="meal_history",
        aggregate_id=meal.id,
        payload={"meal_id": meal.id, "recipe_id": recipe.id, "servings": payload.servings},
        outbox=True,
    )
    if payload.satisfaction:
        db.add(
            PreferenceEvidence(
                user_id=user.id,
                recipe_id=recipe.id,
                protein_family=recipe.protein_family,
                signal="meal_satisfaction",
                value=payload.satisfaction - 3,
                observed_at=meal.consumed_at,
                source="meal_history",
            )
        )
    return MealHistoryRead.model_validate(meal)


def _recent_meals(db: Session, user: UserProfile, days: int = 7) -> list[MealHistory]:
    since = _now() - timedelta(days=days)
    return list(db.scalars(select(MealHistory).where(MealHistory.user_id == user.id, MealHistory.consumed_at >= since).order_by(MealHistory.consumed_at.desc())).all())


def _preference_score(db: Session, user: UserProfile, recipe: Recipe) -> float:
    rows = list(
        db.scalars(
            select(PreferenceEvidence)
            .where(PreferenceEvidence.user_id == user.id)
            .where((PreferenceEvidence.recipe_id == recipe.id) | (PreferenceEvidence.protein_family == recipe.protein_family))
            .order_by(PreferenceEvidence.observed_at.desc())
            .limit(10)
        ).all()
    )
    score = sum(row.value for row in rows) * 2.0
    searchable = " ".join([recipe.name, recipe.protein_family or "", *(recipe.tags or [])]).lower()
    memories = list(db.scalars(select(MemoryItem).where(MemoryItem.user_id == user.id, MemoryItem.domain.in_(["kitchen", "general", "global"]), MemoryItem.status.in_(["active", "confirmed"]))).all())
    for memory in memories:
        key = (memory.normalized_key or "").lower()
        if key and any(token in searchable for token in key.split() if len(token) > 2):
            score += 3.0 * memory.polarity * memory.confidence
    rejected = db.scalar(select(func.count(RecommendationOutcome.id)).where(RecommendationOutcome.user_id == user.id, RecommendationOutcome.domain == "kitchen", RecommendationOutcome.source_entity_type == "recipe", RecommendationOutcome.source_entity_id == recipe.id, RecommendationOutcome.outcome == "rejected")) or 0
    selected = db.scalar(select(func.count(RecommendationOutcome.id)).where(RecommendationOutcome.user_id == user.id, RecommendationOutcome.domain == "kitchen", RecommendationOutcome.source_entity_type == "recipe", RecommendationOutcome.source_entity_id == recipe.id, RecommendationOutcome.outcome.in_(["accepted", "completed"]))) or 0
    score += min(6, selected * 1.5) - min(8, rejected * 1.25)
    return max(-12.0, min(12.0, score))


def _technique_fit(db: Session, user: UserProfile, recipe: Recipe) -> tuple[float, list[str]]:
    links = list(db.scalars(select(RecipeTechnique).where(RecipeTechnique.user_id == user.id, RecipeTechnique.recipe_id == recipe.id)).all())
    score = 0.0
    opportunities: list[str] = []
    for link in links:
        technique = db.get(CookingTechnique, link.technique_id)
        competency = db.scalar(select(CookingCompetency).where(CookingCompetency.user_id == user.id, CookingCompetency.technique_id == link.technique_id))
        current = competency.estimated_level if competency else 1.0
        gap = link.required_level - current
        if gap > 1.5:
            score -= min(8.0, gap * 3)
        elif gap > 0:
            score += min(4.0, 1.5 + gap)
            if technique: opportunities.append(technique.name)
        else:
            score += 1.0
    return round(score, 2), opportunities


def _score_recipe(db: Session, user: UserProfile, recipe: Recipe, request: RecommendationRequest, progress: NutritionProgressRead, budget) -> MealRecommendationRead:
    ingredients = _recipe_ingredients(db, user, recipe.id)
    serving_multiplier = 1.0 / recipe.servings
    required = [ingredient for ingredient in ingredients if not ingredient.optional]
    available_count = 0
    missing: list[str] = []
    expiring_used: list[str] = []
    current = _now()
    for ingredient in required:
        required_amount = _required_canonical(ingredient, serving_multiplier)
        available, _, lots = _available_for_ingredient(db, user, ingredient)
        if available + 1e-6 >= required_amount:
            available_count += 1
            if any(lot.expires_at and current <= _aware(lot.expires_at) <= current + timedelta(days=EXPIRY_SOON_DAYS) for lot in lots):
                expiring_used.append(ingredient.ingredient_name)
        else:
            missing.append(ingredient.ingredient_name)
    availability_ratio = available_count / len(required) if required else 1.0
    preference_fit = _preference_score(db, user, recipe)
    protein_remaining = progress.protein_g_remaining if progress.protein_g_remaining is not None else recipe.protein_g_per_serving
    calories_remaining = progress.calories_remaining if progress.calories_remaining is not None else recipe.calories_per_serving
    protein_fit = 20.0 * min(recipe.protein_g_per_serving / max(protein_remaining or 1, 1), 1.0) if (protein_remaining or 0) > 0 else 5.0
    if (calories_remaining or 0) <= 0:
        calorie_fit = -8.0
    elif recipe.calories_per_serving <= (calories_remaining or recipe.calories_per_serving) * 1.15:
        calorie_fit = 10.0
    else:
        calorie_fit = max(-10.0, 10.0 - ((recipe.calories_per_serving - (calories_remaining or 0)) / 100.0))
    nutrition_fit = round(protein_fit + calorie_fit, 2)
    inventory_fit = round(25.0 * availability_ratio, 2)
    craving_text = (request.craving or "").lower()
    searchable = " ".join([recipe.name, recipe.protein_family or "", " ".join(recipe.tags or [])]).lower()
    craving_context_fit = 12.0 if craving_text and any(part in searchable for part in craving_text.split()) else 0.0
    ingredient_expiry_value = min(15.0, 5.0 * len(set(expiring_used)))
    recent = _recent_meals(db, user, 7)
    recent_recipe = sum(1 for meal in recent[:6] if meal.recipe_id == recipe.id)
    recent_family = sum(1 for meal in recent[:6] if meal.recipe_id and db.get(Recipe, meal.recipe_id) and db.get(Recipe, meal.recipe_id).protein_family == recipe.protein_family)
    repeat_penalty = 15.0 * recent_recipe + 5.0 * recent_family
    variety_value = 5.0 if recent_family == 0 else 0.0
    shopping_friction = 8.0 * len(missing)
    time_minutes = recipe.preparation_minutes + recipe.cooking_minutes
    time_cost = min(12.0, floor(time_minutes / 10))
    if request.max_minutes and time_minutes > request.max_minutes:
        time_cost += 10.0
    waste_risk = 0.0
    cooking_skill_progress, technique_opportunities = _technique_fit(db, user, recipe)
    estimated_missing_cost = None
    budget_fit = 0.0
    factors = {
        "preference_fit": preference_fit,
        "nutrition_fit": nutrition_fit,
        "inventory_fit": inventory_fit,
        "craving_context_fit": craving_context_fit,
        "cooking_skill_progress": cooking_skill_progress,
        "ingredient_expiry_value": ingredient_expiry_value,
        "variety_value": variety_value,
        "repeat_penalty": -repeat_penalty,
        "shopping_friction": -shopping_friction,
        "time_cost": -time_cost,
        "waste_risk": -waste_risk,
        "budget_fit": round(budget_fit, 2),
    }
    score = round(sum(factors.values()), 2)
    availability = "available" if not missing else ("partial" if available_count else "missing")
    explanation = [
        f"{recipe.name} scores {score}.",
        f"Inventory availability is {availability_ratio:.0%}; missing: {', '.join(missing) if missing else 'none'}.",
        f"Nutrition fit uses today's remaining calories/protein ({progress.calories_remaining}/{progress.protein_g_remaining}).",
    ]
    if expiring_used:
        explanation.append(f"Uses expiring inventory: {', '.join(sorted(set(expiring_used)))}.")
    if budget.state != "unknown":
        explanation.append(f"Budget fit uses only bounded grocery context ({budget.state}); missing-item cost is unknown without canonical price data.")
    if technique_opportunities:
        explanation.append(f"Technique opportunity: {', '.join(technique_opportunities)}.")
    return MealRecommendationRead(
        recipe=_recipe_read(db, user, recipe),
        score=score,
        score_factors=factors,
        explanation=explanation,
        availability=availability,
        missing_ingredients=missing,
        expiring_ingredients_used=sorted(set(expiring_used)),
        estimated_missing_cost=estimated_missing_cost,
        budget_state=budget.state,
        technique_opportunities=technique_opportunities,
    )


def recommendations(db: Session, user: UserProfile, request: RecommendationRequest) -> list[MealRecommendationRead]:
    progress = daily_nutrition_progress(db, user)
    budget = grocery_budget_context(db, user)
    recipes = list(db.scalars(select(Recipe).where(Recipe.user_id == user.id, Recipe.active.is_(True))).all())
    scored = [_score_recipe(db, user, recipe, request, progress, budget) for recipe in recipes]
    if request.no_shopping:
        scored = [item for item in scored if item.availability == "available"]
    scored.sort(key=lambda item: (-item.score, item.recipe.preparation_minutes + item.recipe.cooking_minutes, item.recipe.name.lower()))
    selected: list[MealRecommendationRead] = []
    families: set[str] = set()
    for item in scored:
        family = item.recipe.protein_family or (item.recipe.tags[0] if item.recipe.tags else item.recipe.id)
        if family in families and any((candidate.recipe.protein_family or (candidate.recipe.tags[0] if candidate.recipe.tags else candidate.recipe.id)) not in families for candidate in scored[len(selected):]):
            continue
        selected.append(item)
        families.add(family)
        if len(selected) >= request.limit: break
    if len(selected) < min(request.limit, len(scored)):
        for item in scored:
            if item not in selected: selected.append(item)
            if len(selected) >= request.limit: break
    return selected


def recommendation_set(db: Session, user: UserProfile, request: RecommendationRequest) -> ChefRecommendationSetRead:
    options = recommendations(db, user, request)
    signature = sha256(f"{user.id}|{user.world_revision}|{request.model_dump_json()}|{_now().date()}".encode()).hexdigest()[:32]
    created = recommendation_service.create_recommendation(
        db,
        user,
        RecommendationCreate(
            domain="kitchen",
            kind="meal",
            title="Chef meal options",
            reason="Deterministic Kitchen ranking using inventory, expiry, nutrition, outcomes, competency, time, and bounded grocery budget.",
            context_snapshot={"world_revision": user.world_revision, "request": request.model_dump(mode="json")},
            options=[RecommendationOptionCreate(label=item.recipe.name, rank=index, score=item.score, payload_json={"score_factors": item.score_factors, "missing_ingredients": item.missing_ingredients, "explanation": item.explanation}, reference_type="recipe", reference_id=item.recipe.id) for index, item in enumerate(options, start=1)],
            idempotency_key=f"chef:{signature}",
        ),
    )
    option_by_recipe = {option.reference_id: option for option in created.options}
    reads: list[MealRecommendationRead] = []
    for item in options:
        option = option_by_recipe[item.recipe.id]
        reads.append(item.model_copy(update={"recommendation_id": created.id, "option_id": option.id}))
        recommendation_service.record_outcome(db, user, RecommendationOutcomeCreate(domain="kitchen", recommendation_type="meal", recommendation_summary=item.recipe.name, outcome="shown", source_entity_type="recipe", source_entity_id=item.recipe.id, recommendation_id=created.id, option_id=option.id, idempotency_key=f"shown:{option.id}"))
    return ChefRecommendationSetRead(recommendation_id=created.id, options=reads)


def _recommendation_option(db: Session, user: UserProfile, recommendation_id: str, option_id: str) -> tuple[Recommendation, RecommendationOption, Recipe]:
    recommendation = db.scalar(select(Recommendation).where(Recommendation.id == recommendation_id, Recommendation.user_id == user.id, Recommendation.domain == "kitchen"))
    option = db.scalar(select(RecommendationOption).where(RecommendationOption.id == option_id, RecommendationOption.user_id == user.id, RecommendationOption.recommendation_id == recommendation_id))
    if recommendation is None or option is None or option.reference_type != "recipe" or not option.reference_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chef recommendation option not found.")
    recipe = db.scalar(select(Recipe).where(Recipe.id == option.reference_id, Recipe.user_id == user.id, Recipe.active.is_(True)))
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommended recipe is unavailable.")
    return recommendation, option, recipe


def reject_meal(db: Session, user: UserProfile, recommendation_id: str, option_id: str, feedback: str | None = None):
    _, option, recipe = _recommendation_option(db, user, recommendation_id, option_id)
    return recommendation_service.record_outcome(db, user, RecommendationOutcomeCreate(domain="kitchen", recommendation_type="meal", recommendation_summary=recipe.name, outcome="rejected", source_entity_type="recipe", source_entity_id=recipe.id, recommendation_id=recommendation_id, option_id=option.id, feedback_text=feedback, idempotency_key=f"reject:{option.id}", metadata_json={"single_rejection_is_not_durable_preference": True}))


def _meal_plan_read(db: Session, user: UserProfile, plan: MealPlan) -> MealPlanRead:
    recipe = db.scalar(select(Recipe).where(Recipe.id == plan.recipe_id, Recipe.user_id == user.id))
    return MealPlanRead(id=plan.id, recipe_id=plan.recipe_id, recipe=_recipe_read(db, user, recipe), recommendation_id=plan.recommendation_id, recommendation_option_id=plan.recommendation_option_id, planned_for=plan.planned_for, meal_type=plan.meal_type, status=plan.status, planned_servings=plan.planned_servings, nutrition_snapshot=plan.nutrition_snapshot or {}, planned_ingredients=plan.planned_ingredients_json or [], modifications=plan.modifications_json or {}, shopping_action_id=plan.shopping_action_id, cooking_action_id=plan.cooking_action_id, meal_history_id=plan.meal_history_id, version=plan.version)


def _planned_usage(db: Session, user: UserProfile, recipe: Recipe, servings: float, *, excluded: list[str] | None = None, substitutions: dict[str, str] | None = None) -> list[dict]:
    excluded_names = {normalize_name(value) for value in (excluded or [])}
    substitution_names = {normalize_name(key): value.strip() for key, value in (substitutions or {}).items() if value.strip()}
    multiplier = servings / recipe.servings
    result: list[dict] = []
    for ingredient in _recipe_ingredients(db, user, recipe.id):
        key = normalize_name(ingredient.ingredient_name)
        if key in excluded_names:
            if not ingredient.optional and key not in substitution_names:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Required ingredient {ingredient.ingredient_name} needs a substitution before exclusion.")
            if ingredient.optional:
                continue
        result.append({
            "ingredient_name": substitution_names.get(key, ingredient.ingredient_name),
            "recipe_ingredient_name": ingredient.ingredient_name,
            "quantity": round(ingredient.quantity * multiplier, 3),
            "unit": ingredient.unit,
            "optional": ingredient.optional,
            "substituted": key in substitution_names,
        })
    return result


def _nutrition_snapshot(recipe: Recipe, servings: float, *, substitutions: dict[str, str] | None = None) -> dict:
    return {
        "calories": round(recipe.calories_per_serving * servings, 2),
        "protein_g": round(recipe.protein_g_per_serving * servings, 2),
        "carbs_g": round(recipe.carbs_g_per_serving * servings, 2) if recipe.carbs_g_per_serving is not None else None,
        "fat_g": round(recipe.fat_g_per_serving * servings, 2) if recipe.fat_g_per_serving is not None else None,
        "source": "canonical_recipe_snapshot",
        "confidence": "PARTIAL" if substitutions else "COMPLETE",
        "substitution_nutrition_unmodeled": bool(substitutions),
    }


def _missing_for_recipe(db: Session, user: UserProfile, recipe: Recipe, servings: float) -> list[tuple[RecipeIngredient, float]]:
    result: list[tuple[RecipeIngredient, float]] = []
    multiplier = servings / recipe.servings
    for ingredient in _recipe_ingredients(db, user, recipe.id):
        if ingredient.optional: continue
        required = _required_canonical(ingredient, multiplier)
        available, _, _ = _available_for_ingredient(db, user, ingredient)
        missing = max(0, required - available)
        if missing > 1e-6:
            result.append((ingredient, _from_canonical(missing, ingredient.unit)))
    return result


def _missing_for_planned_usage(db: Session, user: UserProfile, planned_usage: list[dict]) -> list[tuple[object, float]]:
    result: list[tuple[object, float]] = []
    for usage in planned_usage:
        ingredient = SimpleNamespace(
            inventory_item_id=None,
            ingredient_name=usage["ingredient_name"],
            quantity=float(usage["quantity"]),
            unit=usage["unit"],
            optional=bool(usage.get("optional", False)),
        )
        required = _quantity(ingredient.quantity, ingredient.unit).amount
        available, item, _ = _available_for_ingredient(db, user, ingredient)
        missing = max(0, required - available)
        ingredient.inventory_item_id = item.id if item else None
        if missing > 1e-6 and not ingredient.optional:
            result.append((ingredient, _from_canonical(missing, ingredient.unit)))
    return result


def select_meal(db: Session, user: UserProfile, payload: MealSelectionCreate) -> MealPlanRead:
    _, option, recipe = _recommendation_option(db, user, payload.recommendation_id, payload.option_id)
    idempotency = f"meal-select:{option.id}"
    existing = db.scalar(select(MealPlan).where(MealPlan.user_id == user.id, MealPlan.idempotency_key == idempotency))
    if existing is not None:
        return _meal_plan_read(db, user, existing)
    planned_usage = _planned_usage(db, user, recipe, payload.servings, excluded=payload.excluded_ingredients, substitutions=payload.ingredient_substitutions)
    missing = _missing_for_planned_usage(db, user, planned_usage)
    modifications = {"excluded_ingredients": payload.excluded_ingredients, "ingredient_substitutions": payload.ingredient_substitutions,
                     "shopping_requirements": [{"ingredient_name": item.ingredient_name, "quantity": quantity, "unit": item.unit} for item, quantity in missing]}
    plan = MealPlan(user_id=user.id, recipe_id=recipe.id, recommendation_id=payload.recommendation_id, recommendation_option_id=option.id, planned_for=payload.planned_for, meal_type=payload.meal_type, status="selected", planned_servings=payload.servings, nutrition_snapshot=_nutrition_snapshot(recipe, payload.servings, substitutions=payload.ingredient_substitutions), planned_ingredients_json=planned_usage, modifications_json=modifications, idempotency_key=idempotency)
    db.add(plan)
    db.flush()
    recommendation_service.record_outcome(db, user, RecommendationOutcomeCreate(domain="kitchen", recommendation_type="meal", recommendation_summary=recipe.name, outcome="accepted", source_entity_type="recipe", source_entity_id=recipe.id, recommendation_id=payload.recommendation_id, option_id=option.id, idempotency_key=f"select:{option.id}"))
    shopping_action = None
    cooking_minutes = max(10, recipe.preparation_minutes + recipe.cooking_minutes)
    shopping_deadline = payload.planned_for - timedelta(minutes=cooking_minutes + 15)
    if missing:
        need = ShoppingNeed(user_id=user.id, title=f"Shop for {recipe.name}", status="active", required_by=shopping_deadline, reason=f"Required for selected meal {recipe.name}.", source="selected_meal", forecast_window_days=1, metadata_json={"recipe_id": recipe.id, "certainty": "selected", "cost_known": False}, meal_plan_id=plan.id, estimated_total=None, currency="EUR", idempotency_key=f"meal-plan:{plan.id}:shopping")
        db.add(need)
        db.flush()
        for ingredient, quantity in missing:
            db.add(ShoppingNeedItem(user_id=user.id, shopping_need_id=need.id, inventory_item_id=ingredient.inventory_item_id, ingredient_name=ingredient.ingredient_name, quantity=quantity, unit=ingredient.unit, satisfied=False, priority_class="required", reason=f"Selected meal: {recipe.name}", source_type="meal_plan", source_id=plan.id, estimated_cost=None, purchased_quantity=0, status="needed"))
        shopping_action = create_action(db, user, ActionCreate(title="Grocery shopping", domain="kitchen", level="maintenance", description=f"Buy required ingredients for {recipe.name}.", earliest_start=_now(), deadline=shopping_deadline, estimated_minutes=30, duration_min_minutes=20, duration_max_minutes=45, location="store", context="shopping", requirement_key=f"meal-plan:{plan.id}:shopping", source_entity_type="meal_plan", source_entity_id=plan.id, generated_reason=f"Selected meal {recipe.name} has missing ingredients.", generation_version="v1.5", planning_priority=72, metadata_json={"meal_plan_id": plan.id, "shopping_need_id": need.id, "must_finish_before": payload.planned_for.isoformat(), "maintenance_value": 75, "neglect_cost": 70}))
        need.action_id = shopping_action.id
        plan.shopping_action_id = shopping_action.id
    cooking_action = create_action(db, user, ActionCreate(title=f"Cook {recipe.name}", domain="kitchen", level="maintenance", description=f"Prepare the selected {payload.meal_type}.", earliest_start=_now(), latest_start=payload.planned_for - timedelta(minutes=cooking_minutes), deadline=payload.planned_for, estimated_minutes=cooking_minutes, duration_min_minutes=max(10, cooking_minutes - 10), duration_max_minutes=cooking_minutes + 10, location="home", context="cooking", requirement_key=f"meal-plan:{plan.id}:cooking", source_entity_type="meal_plan", source_entity_id=plan.id, generated_reason=f"Meal selected for {payload.planned_for.isoformat()}.", generation_version="v1.5", planning_priority=70, metadata_json={"meal_plan_id": plan.id, "recipe_id": recipe.id, "depends_on_action_id": shopping_action.id if shopping_action else None, "trajectory_value": 35, "maintenance_value": 65, "neglect_cost": 60}))
    plan.cooking_action_id = cooking_action.id
    if shopping_action:
        shopping_action.metadata_json = {**shopping_action.metadata_json, "must_precede_action_id": cooking_action.id}
    db.flush()
    append_event(db, user, event_type="kitchen.meal_selected", aggregate_type="meal_plan", aggregate_id=plan.id, payload={"meal_plan_id": plan.id, "recipe_id": recipe.id, "shopping_action_id": plan.shopping_action_id, "cooking_action_id": plan.cooking_action_id}, outbox=True)
    append_event(db, user, event_type="kitchen.meal_plan_created", aggregate_type="meal_plan", aggregate_id=plan.id, payload={"meal_plan_id": plan.id, "planned_ingredients": len(planned_usage)}, outbox=True)
    return _meal_plan_read(db, user, plan)


def modify_meal_plan(db: Session, user: UserProfile, plan_id: str, payload: MealPlanModifyRequest) -> MealPlanRead:
    plan = db.scalar(select(MealPlan).where(MealPlan.id == plan_id, MealPlan.user_id == user.id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found.")
    if plan.status == "cooked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A completed meal plan cannot be modified.")
    recipe = db.get(Recipe, plan.recipe_id)
    current = dict(plan.modifications_json or {})
    servings = payload.servings if payload.servings is not None else plan.planned_servings
    excluded = payload.excluded_ingredients if payload.excluded_ingredients is not None else list(current.get("excluded_ingredients", []))
    substitutions = payload.ingredient_substitutions if payload.ingredient_substitutions is not None else dict(current.get("ingredient_substitutions", {}))
    plan.planned_servings = servings
    plan.planned_ingredients_json = _planned_usage(db, user, recipe, servings, excluded=excluded, substitutions=substitutions)
    missing = _missing_for_planned_usage(db, user, plan.planned_ingredients_json)
    plan.modifications_json = {"excluded_ingredients": excluded, "ingredient_substitutions": substitutions,
                               "shopping_requirements": [{"ingredient_name": item.ingredient_name, "quantity": quantity, "unit": item.unit} for item, quantity in missing]}
    plan.nutrition_snapshot = _nutrition_snapshot(recipe, servings, substitutions=substitutions)
    plan.version += 1
    append_event(db, user, event_type="kitchen.meal_plan_modified", aggregate_type="meal_plan", aggregate_id=plan.id,
                 payload={"meal_plan_id": plan.id, "servings": servings, "modification_count": len(excluded) + len(substitutions)}, outbox=True)
    return _meal_plan_read(db, user, plan)


def list_meal_plans(db: Session, user: UserProfile) -> list[MealPlanRead]:
    rows = list(db.scalars(select(MealPlan).where(MealPlan.user_id == user.id).order_by(MealPlan.planned_for.desc()).limit(30)).all())
    return [_meal_plan_read(db, user, row) for row in rows]


def start_cooking_session(db: Session, user: UserProfile, payload: CookingSessionStartRequest):
    plan = db.scalar(select(MealPlan).where(MealPlan.id == payload.meal_plan_id, MealPlan.user_id == user.id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found.")
    if plan.status == "cooked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This meal is already complete.")
    recipe = db.get(Recipe, plan.recipe_id)
    steps = list(recipe.steps_json or [])
    workspace_payload = CookingWorkspacePayload(
        meal_plan_ref=plan.id,
        recipe_ref=recipe.id,
        recipe_version=recipe.version,
        recommendation_ref=plan.recommendation_id,
        recommendation_option_ref=plan.recommendation_option_id,
        current_step=steps[0] if steps else "Prepare ingredients",
        current_step_index=0,
        servings=plan.planned_servings,
        ingredient_change_refs=tuple(
            f"{key}:{value}" for key, value in (plan.modifications_json or {}).get("ingredient_substitutions", {}).items()
        ),
    )
    row = ActiveWorkspaceService().start_workspace(
        db,
        user,
        workspace_type=WorkspaceType.cooking,
        payload=workspace_payload,
        foreground=True,
        conversation_thread_id=payload.conversation_thread_id,
        primary_entity_type="meal_plan",
        primary_entity_id=plan.id,
        current_phase="COOKING",
        current_step=workspace_payload.current_step,
        idempotency_key=f"cooking:{plan.id}",
        metadata={"recipe_id": recipe.id, "canonical_inventory_owned_by": "kitchen"},
    )
    if plan.status != "cooking":
        plan.status = "cooking"
        plan.version += 1
        append_event(db, user, event_type="kitchen.cooking_started", aggregate_type="active_workspace", aggregate_id=row.id,
                     payload={"workspace_id": row.id, "meal_plan_id": plan.id, "recipe_id": recipe.id}, outbox=True)
    return workspace_to_read(row)


def update_cooking_session(db: Session, user: UserProfile, workspace_id: str, payload: CookingSessionUpdateRequest):
    service = ActiveWorkspaceService()
    row = service.get_workspace(db, user, workspace_id)
    if row is None or row.workspace_type != WorkspaceType.cooking.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cooking session not found.")
    current = service.reconstruct_payload(row)
    recipe = db.get(Recipe, current.recipe_ref) if current.recipe_ref else None
    step_index = payload.current_step_index if payload.current_step_index is not None else current.current_step_index
    step_text = current.current_step
    previous = current.previous_step
    if step_index is not None and recipe is not None:
        steps = list(recipe.steps_json or [])
        if step_index >= len(steps) and steps:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Cooking step is outside the recipe.")
        if steps:
            previous, step_text = current.current_step, steps[step_index]
    updated = current.model_copy(update={
        "current_step_index": step_index,
        "previous_step": previous,
        "current_step": step_text,
        "timer_refs": payload.timer_refs if payload.timer_refs is not None else current.timer_refs,
        "equipment_refs": payload.equipment_refs if payload.equipment_refs is not None else current.equipment_refs,
        "ingredient_change_refs": payload.ingredient_changes if payload.ingredient_changes is not None else current.ingredient_change_refs,
        "temporary_notes": payload.temporary_notes if payload.temporary_notes is not None else current.temporary_notes,
        "step_started_at": _now() if payload.current_step_index is not None else current.step_started_at,
    })
    row = service.update_workspace(db, user, workspace_id, payload=updated, current_phase="COOKING", current_step=step_text)
    append_event(db, user, event_type="kitchen.cooking_updated", aggregate_type="active_workspace", aggregate_id=row.id,
                 payload={"workspace_id": row.id, "meal_plan_id": current.meal_plan_ref, "current_step_index": step_index}, outbox=True)
    return workspace_to_read(row)


def _feedback_structure(text: str | None) -> dict:
    lowered = (text or "").lower()
    return {"overall_positive": any(term in lowered for term in ("good", "great", "love", "tasty", "delicious")), "salt_high": any(term in lowered for term in ("too salty", "salty")), "dryness": any(term in lowered for term in ("dry", "overcooked")), "sauce_liked": "sauce" in lowered and any(term in lowered for term in ("good", "great", "love", "liked")), "preference_claim": any(term in lowered for term in ("i hate", "i love", "i always prefer", "i never"))}


def _update_competencies(db: Session, user: UserProfile, recipe: Recipe, meal: MealHistory, successful: bool) -> list[str]:
    links = list(db.scalars(select(RecipeTechnique).where(RecipeTechnique.user_id == user.id, RecipeTechnique.recipe_id == recipe.id)).all())
    updated_ids: list[str] = []
    for link in links:
        competency = db.scalar(select(CookingCompetency).where(CookingCompetency.user_id == user.id, CookingCompetency.technique_id == link.technique_id))
        if competency is None:
            competency = CookingCompetency(user_id=user.id, technique_id=link.technique_id, estimated_level=1, confidence=0, evidence_count=0, successful_repetitions=0)
            db.add(competency)
            db.flush()
        key = f"meal:{meal.id}:technique:{link.technique_id}"
        evidence = db.scalar(select(CookingCompetencyEvidence).where(CookingCompetencyEvidence.user_id == user.id, CookingCompetencyEvidence.idempotency_key == key))
        if evidence is not None: continue
        db.add(CookingCompetencyEvidence(user_id=user.id, competency_id=competency.id, meal_history_id=meal.id, source="meal_completion", successful=successful, difficulty=link.required_level, weight=link.importance, idempotency_key=key, metadata_json={}))
        competency.evidence_count += 1
        competency.successful_repetitions += int(successful)
        if successful:
            competency.estimated_level = min(5.0, competency.estimated_level + min(0.35, 0.08 + link.required_level * 0.04))
        else:
            competency.estimated_level = max(1.0, competency.estimated_level - 0.05)
        competency.confidence = min(0.95, competency.evidence_count / (competency.evidence_count + 3))
        competency.last_practiced_at = meal.consumed_at
        competency.version += 1
        updated_ids.append(competency.id)
    return updated_ids


def complete_meal_plan(db: Session, user: UserProfile, plan_id: str, payload: MealPlanCompleteRequest) -> MealPlanRead:
    plan = db.scalar(select(MealPlan).where(MealPlan.id == plan_id, MealPlan.user_id == user.id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found.")
    if plan.status == "cooked" and plan.meal_history_id:
        return _meal_plan_read(db, user, plan)
    confirmed_usage = payload.actual_ingredients or list(plan.planned_ingredients_json or [])
    meal_read = complete_recipe_meal(db, user, plan.recipe_id, MealCompleteRequest(servings=plan.planned_servings, satisfaction=payload.satisfaction, feedback=payload.feedback, actual_ingredients=confirmed_usage, idempotency_key=f"meal-plan:{plan.id}:cooked"))
    meal = db.get(MealHistory, meal_read.id)
    meal.meal_plan_id, meal.recommendation_id, meal.recommendation_option_id = plan.id, plan.recommendation_id, plan.recommendation_option_id
    plan.status, plan.meal_history_id = "cooked", meal.id
    plan.version += 1
    structured = _feedback_structure(payload.feedback)
    if payload.feedback:
        db.add(MealFeedback(user_id=user.id, meal_history_id=meal.id, raw_text=payload.feedback, structured_json=structured, interpretation_status="deterministic", idempotency_key=f"meal:{meal.id}:feedback"))
    recipe = db.get(Recipe, plan.recipe_id)
    successful = (payload.satisfaction or 3) >= 3 and not structured.get("dryness")
    competency_ids = _update_competencies(db, user, recipe, meal, successful)
    if plan.cooking_action_id:
        action = db.scalar(select(Action).where(Action.id == plan.cooking_action_id, Action.user_id == user.id))
        if action and action.status == "active": action.status, action.completed_minutes, action.version = "completed", action.estimated_minutes or 0, action.version + 1
    if plan.recommendation_id and plan.recommendation_option_id:
        metadata = {"structured_feedback": structured}
        if structured.get("preference_claim"):
            metadata["memory_candidate"] = {"memory_type": "domain_preference", "domain": "kitchen", "content": payload.feedback, "normalized_key": normalize_name(payload.feedback or ""), "polarity": -1 if "hate" in (payload.feedback or "").lower() or "never" in (payload.feedback or "").lower() else 1, "importance": 0.65, "explicit": True}
        recommendation_service.record_outcome(db, user, RecommendationOutcomeCreate(domain="kitchen", recommendation_type="meal", recommendation_summary=recipe.name, outcome="completed", source_entity_type="recipe", source_entity_id=recipe.id, recommendation_id=plan.recommendation_id, option_id=plan.recommendation_option_id, feedback_text=payload.feedback, idempotency_key=f"cooked:{plan.id}", metadata_json=metadata))
    workspace = db.scalar(select(ActiveWorkspace).where(ActiveWorkspace.user_id == user.id, ActiveWorkspace.primary_entity_type == "meal_plan", ActiveWorkspace.primary_entity_id == plan.id, ActiveWorkspace.status.in_(["ACTIVE", "PAUSED"])))
    if workspace is not None:
        ActiveWorkspaceService().complete_workspace(db, user, workspace.id)
    append_event(db, user, event_type="kitchen.cooking_completed", aggregate_type="meal_plan", aggregate_id=plan.id, payload={"meal_plan_id": plan.id, "meal_history_id": meal.id, "recipe_id": recipe.id, "workspace_id": workspace.id if workspace else None}, outbox=True)
    if competency_ids:
        append_event(db, user, event_type="kitchen.competency_updated", aggregate_type="meal_history", aggregate_id=meal.id,
                     payload={"meal_history_id": meal.id, "competency_ids": competency_ids}, outbox=True)
    return _meal_plan_read(db, user, plan)


def list_competencies(db: Session, user: UserProfile) -> list[CompetencyRead]:
    rows = list(db.scalars(select(CookingCompetency).where(CookingCompetency.user_id == user.id).order_by(CookingCompetency.estimated_level.desc())).all())
    result = []
    for row in rows:
        technique = db.get(CookingTechnique, row.technique_id)
        band = "Strong" if row.estimated_level >= 4 else "Comfortable" if row.estimated_level >= 3 else "Practicing" if row.evidence_count else "New"
        result.append(CompetencyRead(id=row.id, technique_id=row.technique_id, technique_key=technique.key, technique_name=technique.name, estimated_level=row.estimated_level, confidence=row.confidence, evidence_count=row.evidence_count, successful_repetitions=row.successful_repetitions, last_practiced_at=row.last_practiced_at, band=band, version=row.version))
    return result


def create_shopping_forecast(db: Session, user: UserProfile, payload: ShoppingForecastRequest) -> list[ShoppingNeedRead]:
    recs = recommendations(db, user, RecommendationRequest(no_shopping=False, limit=payload.limit))
    required_by = _now() + timedelta(days=payload.window_days)
    created_or_existing: list[ShoppingNeed] = []
    active_needs = list(db.scalars(select(ShoppingNeed).where(ShoppingNeed.user_id == user.id, ShoppingNeed.status == "active")).all())
    staple_need = next((need for need in active_needs if isinstance(need.metadata_json, dict) and need.metadata_json.get("kind") == "staple_restock"), None)
    staples = list(db.scalars(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.active.is_(True), InventoryItem.is_staple.is_(True))).all())
    restocks: list[tuple[InventoryItem, float]] = []
    for item in staples:
        if item.restock_threshold is None:
            continue
        current = _item_total(db, user, item)
        if current < item.restock_threshold:
            target = max(item.restock_threshold, item.restock_target or item.restock_threshold)
            restocks.append((item, round(target - current, 3)))
    if restocks:
        if staple_need is None:
            staple_need = ShoppingNeed(
                user_id=user.id,
                title="Restock kitchen staples",
                status="active",
                required_by=required_by,
                reason="Stored staple quantities are below their configured thresholds.",
                source="inventory_threshold",
                forecast_window_days=payload.window_days,
                metadata_json={"kind": "staple_restock"},
                currency="EUR",
            )
            db.add(staple_need)
            db.flush()
            active_needs.append(staple_need)
        existing_items = list(db.scalars(select(ShoppingNeedItem).where(ShoppingNeedItem.user_id == user.id, ShoppingNeedItem.shopping_need_id == staple_need.id, ShoppingNeedItem.status == "needed")).all())
        restock_ids = {item.id for item, _ in restocks}
        for inventory, gap in restocks:
            line = next((candidate for candidate in existing_items if candidate.inventory_item_id == inventory.id), None)
            reason = f"{inventory.ingredient_name} is below its {inventory.restock_threshold:g} {inventory.canonical_unit} staple threshold."
            if line is None:
                line = ShoppingNeedItem(user_id=user.id, shopping_need_id=staple_need.id, inventory_item_id=inventory.id, ingredient_name=inventory.ingredient_name, quantity=gap, unit=inventory.canonical_unit, satisfied=False, priority_class="restock", reason=reason, source_type="inventory_threshold", source_id=inventory.id, estimated_cost=3.5, purchased_quantity=0, status="needed")
                db.add(line)
            else:
                line.quantity = gap
                line.unit = inventory.canonical_unit
                line.reason = reason
                line.version += 1
        for stale in existing_items:
            if stale.inventory_item_id not in restock_ids:
                stale.satisfied = True
                stale.status = "skipped"
                stale.version += 1
        staple_need.required_by = required_by
        staple_need.forecast_window_days = payload.window_days
        staple_need.estimated_total = len(restocks) * 3.5
        staple_need.version += 1
        created_or_existing.append(staple_need)
        append_event(db, user, event_type="kitchen.shopping_need.created", aggregate_type="shopping_need", aggregate_id=staple_need.id, payload={"shopping_need_id": staple_need.id, "source": "inventory_threshold", "item_count": len(restocks)}, outbox=True)
    elif staple_need is not None:
        staple_need.status = "fulfilled"
        staple_need.version += 1
    for rec in recs:
        if not rec.missing_ingredients:
            continue
        existing = next((need for need in active_needs if isinstance(need.metadata_json, dict) and need.metadata_json.get("recipe_id") == rec.recipe.id), None)
        if existing is not None:
            created_or_existing.append(existing)
            continue
        need = ShoppingNeed(
            user_id=user.id,
            title=f"Shop for {rec.recipe.name}",
            status="active",
            required_by=required_by,
            reason=f"Missing ingredients for recommended meal {rec.recipe.name}.",
            source="forecast",
            forecast_window_days=payload.window_days,
            metadata_json={"recipe_id": rec.recipe.id, "score": rec.score},
            estimated_total=len(rec.missing_ingredients) * 3.5,
            currency="EUR",
            idempotency_key=f"forecast:{rec.recipe.id}:{required_by.date().isoformat()}",
        )
        db.add(need)
        db.flush()
        for ingredient_name in rec.missing_ingredients:
            ingredient = next((item for item in rec.recipe.ingredients if item.ingredient_name == ingredient_name), None)
            db.add(
                ShoppingNeedItem(
                    user_id=user.id,
                    shopping_need_id=need.id,
                    inventory_item_id=ingredient.inventory_item_id if ingredient else None,
                    ingredient_name=ingredient_name,
                    quantity=ingredient.quantity if ingredient else 1,
                    unit=ingredient.unit if ingredient else "count",
                    satisfied=False,
                    priority_class="optional",
                    reason=f"Optional ingredient for recommended meal {rec.recipe.name}.",
                    source_type="recommendation_forecast",
                    source_id=rec.recipe.id,
                    estimated_cost=3.5,
                    purchased_quantity=0,
                    status="needed",
                )
            )
        append_event(
            db,
            user,
            event_type="kitchen.shopping_need.created",
            aggregate_type="shopping_need",
            aggregate_id=need.id,
            payload={"shopping_need_id": need.id, "recipe_id": rec.recipe.id},
            outbox=True,
        )
        created_or_existing.append(need)
        active_needs.append(need)
    return [_shopping_need_read(db, user, need) for need in created_or_existing]


def list_shopping_needs(db: Session, user: UserProfile, active_only: bool = True) -> list[ShoppingNeedRead]:
    query = select(ShoppingNeed).where(ShoppingNeed.user_id == user.id)
    if active_only:
        query = query.where(ShoppingNeed.status == "active")
    needs = list(db.scalars(query.order_by(ShoppingNeed.required_by.asc().nulls_last(), ShoppingNeed.created_at.desc())).all())
    return [_shopping_need_read(db, user, need) for need in needs]


def create_manual_shopping_need(db: Session, user: UserProfile, payload: ManualShoppingNeedCreate) -> ShoppingNeedItemRead:
    """Add a confirmed item to the existing Kitchen shopping model."""
    need = db.scalar(select(ShoppingNeed).where(
        ShoppingNeed.user_id == user.id,
        ShoppingNeed.idempotency_key == payload.idempotency_key,
    ))
    if need is not None:
        existing = db.scalar(select(ShoppingNeedItem).where(
            ShoppingNeedItem.user_id == user.id,
            ShoppingNeedItem.shopping_need_id == need.id,
        ))
        if existing is not None:
            return ShoppingNeedItemRead.model_validate(existing)
    need = ShoppingNeed(
        user_id=user.id, title=f"Buy {payload.item_name}", status="active",
        reason="Added through Quick Capture.", source="quick_capture", forecast_window_days=1,
        metadata_json={"kind": "manual_capture"}, currency="EUR", idempotency_key=payload.idempotency_key,
    )
    db.add(need)
    db.flush()
    item = ShoppingNeedItem(
        user_id=user.id, shopping_need_id=need.id, ingredient_name=payload.item_name.strip(),
        quantity=payload.quantity, unit=payload.unit, satisfied=False,
        priority_class=payload.priority_class, reason="Explicit shopping need.",
        source_type="quick_capture", source_id=need.id, purchased_quantity=0, status="needed",
    )
    db.add(item)
    db.flush()
    append_event(
        db, user, event_type="kitchen.shopping_need.created", aggregate_type="shopping_need",
        aggregate_id=need.id,
        payload={"shopping_need_id": need.id, "shopping_item_id": item.id, "source": "quick_capture"},
        outbox=True,
    )
    return ShoppingNeedItemRead.model_validate(item)


def aggregated_shopping_list(db: Session, user: UserProfile) -> list[ShoppingAggregateRead]:
    needs = list_shopping_needs(db, user)
    grouped: dict[tuple[str, str], dict] = {}
    priority_rank = {"required": 3, "restock": 2, "optional": 1}
    for need in needs:
        for item in need.items:
            if item.satisfied or item.status in {"purchased", "skipped"}:
                continue
            key = (normalize_name(item.ingredient_name), item.unit)
            entry = grouped.setdefault(key, {"ingredient_name": item.ingredient_name, "quantity": 0.0, "unit": item.unit, "priority_class": item.priority_class, "reasons": [], "estimated_cost": 0.0, "cost_unknown": False, "source_item_ids": [], "status": "needed"})
            entry["quantity"] += item.quantity
            if item.estimated_cost is None:
                entry["cost_unknown"] = True
            else:
                entry["estimated_cost"] += item.estimated_cost
            entry["source_item_ids"].append(item.id)
            if item.reason and item.reason not in entry["reasons"]: entry["reasons"].append(item.reason)
            if priority_rank.get(item.priority_class, 0) > priority_rank.get(entry["priority_class"], 0): entry["priority_class"] = item.priority_class
    values = []
    for value in grouped.values():
        if value.pop("cost_unknown"):
            value["estimated_cost"] = None
        values.append(value)
    return [ShoppingAggregateRead(**value) for value in sorted(values, key=lambda item: (-priority_rank.get(item["priority_class"], 0), item["ingredient_name"].lower()))]


def mark_shopping_item_purchased(db: Session, user: UserProfile, item_id: str, payload: ShoppingPurchaseCreate) -> ShoppingNeedItemRead:
    item = db.scalar(select(ShoppingNeedItem).where(ShoppingNeedItem.id == item_id, ShoppingNeedItem.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping item not found.")
    if item.status == "purchased":
        return ShoppingNeedItemRead.model_validate(item)
    quantity, unit = payload.quantity or item.quantity, payload.unit or item.unit
    if payload.add_to_inventory:
        identity = resolve_ingredient(db, user, item.ingredient_name, default_unit=unit, category="food", source="shopping")
        inventory = db.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.ingredient_id == identity.id, InventoryItem.active.is_(True)))
        if inventory is None:
            inventory = InventoryItem(user_id=user.id, ingredient_id=identity.id, ingredient_name=identity.name, quantity=0, unit=unit, source="shopping", category="food", canonical_unit=unit, default_storage_location="fridge", active=True)
            db.add(inventory)
            db.flush()
        _ensure_compatible(inventory.canonical_unit, unit)
        db.add(InventoryLot(user_id=user.id, inventory_item_id=inventory.id, quantity=quantity, unit=unit, purchased_at=_now(), storage_location=inventory.default_storage_location, source="shopping_checkoff", source_reference_type="shopping_need_item", source_reference_id=item.id, confidence=1, status="active"))
        item.inventory_item_id = inventory.id
        inventory.quantity = float(inventory.quantity or 0) + quantity
        inventory.version += 1
    item.satisfied, item.status, item.purchased_quantity = True, "purchased", quantity
    item.source_type = "manual_purchase"
    item.version += 1
    append_event(db, user, event_type="shopping.item_purchased", aggregate_type="shopping_need_item", aggregate_id=item.id, payload={"shopping_item_id": item.id, "quantity": quantity, "unit": unit, "inventory_updated": payload.add_to_inventory}, outbox=True)
    return ShoppingNeedItemRead.model_validate(item)


def sync_shopping_actions(db: Session, user: UserProfile) -> list[ActionRead]:
    needs = list_shopping_needs(db, user)
    existing = list_actions(db, user, planning_pool=True, domain="kitchen")
    reads: list[ActionRead] = []
    for need in needs:
        action = next((item for item in existing if item.metadata_json.get("kitchen_shopping_need_id") == need.id), None)
        if action is None:
            item_names = ", ".join(item.ingredient_name for item in need.items[:4])
            action = create_action(
                db,
                user,
                ActionCreate(
                    title=need.title,
                    domain="kitchen",
                    level="maintenance",
                    description=f"Buy missing ingredients: {item_names}.",
                    deadline=_aware(need.required_by) if need.required_by else None,
                    estimated_minutes=45,
                    duration_min_minutes=20,
                    duration_max_minutes=60,
                    context="shopping",
                    requirement_key=f"shopping-need:{need.id}",
                    source_entity_type="shopping_need",
                    source_entity_id=need.id,
                    generated_reason=need.reason or "Kitchen shopping need.",
                    generation_version="v1.5",
                    planning_priority=70 if any(item.priority_class == "required" for item in need.items) else 45,
                    metadata_json={
                        "kitchen_shopping_need_id": need.id,
                        "source": "kitchen_shopping_forecast",
                        "cognitive_load": 20,
                        "physical_load": 20,
                        "activation_difficulty": 35,
                        "trajectory_value": 20,
                        "maintenance_value": 70,
                        "neglect_cost": 45,
                        "expected_state_effect": {"energy": -5, "mental_state": 5},
                    },
                ),
            )
            need.action_id = action.id
        reads.append(ActionRead.model_validate(action))
    return reads


def complete_kitchen_plan_block(db: Session, user: UserProfile, block, when: datetime) -> None:
    if not block.action_id:
        return
    action = db.scalar(select(Action).where(Action.id == block.action_id, Action.user_id == user.id))
    if action is None or not isinstance(action.metadata_json, dict):
        return
    meal_plan_id = action.metadata_json.get("meal_plan_id")
    if action.context == "cooking" and meal_plan_id:
        complete_meal_plan(db, user, meal_plan_id, MealPlanCompleteRequest())
    elif action.context == "shopping":
        append_event(db, user, event_type="shopping.trip_completed", aggregate_type="action", aggregate_id=action.id, payload={"action_id": action.id, "meal_plan_id": meal_plan_id, "completed_at": when.isoformat()}, outbox=True)


def status_summary(db: Session, user: UserProfile) -> KitchenStatusRead:
    inventory = list_inventory(db, user)
    needs = list_shopping_needs(db, user)
    actions = list_actions(db, user, planning_pool=True, domain="kitchen")
    recs = recommendations(db, user, RecommendationRequest(no_shopping=True, limit=1))
    return KitchenStatusRead(
        inventory_count=len(inventory),
        expiring_lots=sum(1 for item in inventory for lot in item.lots if lot.expires_at and _now() <= _aware(lot.expires_at) <= _now() + timedelta(days=EXPIRY_SOON_DAYS)),
        expired_lots=sum(1 for item in inventory for lot in item.lots if lot.expires_at and _aware(lot.expires_at) < _now()),
        nutrition=daily_nutrition_progress(db, user),
        top_recommendation=recs[0] if recs else None,
        shopping_need_count=len(needs),
        active_candidate_count=len(actions),
    )


def chef_context(db: Session, user: UserProfile) -> dict:
    status_read = status_summary(db, user)
    recs = recommendations(db, user, RecommendationRequest(no_shopping=True, limit=3))
    return {
        "status": jsonable_encoder(status_read),
        "no_shopping_recommendations": [item.model_dump(mode="json") for item in recs],
        "active_shopping_needs": [item.model_dump(mode="json") for item in list_shopping_needs(db, user)[:5]],
        "allowed_tools": ["get_kitchen_status", "get_kitchen_recommendations", "get_shopping_needs", "log_manual_meal", "complete_recipe_meal"],
        "planner_boundary": "Kitchen creates candidate Actions for shopping needs; it never writes PlanBlocks directly.",
    }
