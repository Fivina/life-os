from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.commitments.schemas import ensure_aware


KitchenUnit = Literal["g", "kg", "ml", "l", "count", "serving"]


class MealType(str, Enum):
    breakfast = "BREAKFAST"
    lunch = "LUNCH"
    dinner = "DINNER"
    snack = "SNACK"


class InventoryPreference(str, Enum):
    use_what_i_have = "USE_WHAT_I_HAVE"
    minimal_shopping = "MINIMAL_SHOPPING"
    shopping_allowed = "SHOPPING_ALLOWED"


class HeavinessPreference(str, Enum):
    light = "LIGHT"
    light_to_medium = "LIGHT_TO_MEDIUM"
    medium = "MEDIUM"
    hearty = "HEARTY"


class NoveltyPreference(str, Enum):
    familiar = "FAMILIAR"
    balanced = "BALANCED"
    novel = "NOVEL"


class ExpiryPriority(str, Enum):
    normal = "NORMAL"
    prefer_expiring = "PREFER_EXPIRING"


class SkillPreference(str, Enum):
    easy = "EASY"
    comfortable = "COMFORTABLE"
    learning = "LEARNING"
    challenging = "CHALLENGING"


class MealIntent(BaseModel):
    """Versioned interpretation of a meal request, never a recipe or canonical mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["meal-intent-v1"] = "meal-intent-v1"
    meal_type: MealType | None = None
    cuisine_preferences: tuple[str, ...] = Field(default=(), max_length=8)
    styles: tuple[str, ...] = Field(default=(), max_length=8)
    protein_preferences: tuple[str, ...] = Field(default=(), max_length=8)
    ingredient_preferences: tuple[str, ...] = Field(default=(), max_length=16)
    ingredient_exclusions: tuple[str, ...] = Field(default=(), max_length=16)
    dietary_constraints: tuple[str, ...] = Field(default=(), max_length=12)
    max_total_minutes: int | None = Field(default=None, ge=5, le=360)
    max_active_minutes: int | None = Field(default=None, ge=1, le=240)
    servings: float = Field(default=1, gt=0, le=20)
    desired_calorie_min: float | None = Field(default=None, ge=0, le=5000)
    desired_calorie_max: float | None = Field(default=None, ge=0, le=5000)
    desired_protein_min_g: float | None = Field(default=None, ge=0, le=500)
    protein_priority: Literal["NORMAL", "HIGH"] = "NORMAL"
    satiety_preference: Literal["LIGHT", "BALANCED", "SATIATING"] | None = None
    heaviness_preference: HeavinessPreference | None = None
    novelty_preference: NoveltyPreference = NoveltyPreference.balanced
    inventory_preference: InventoryPreference = InventoryPreference.shopping_allowed
    expiry_priority: ExpiryPriority = ExpiryPriority.normal
    unavailable_equipment: tuple[str, ...] = Field(default=(), max_length=12)
    skill_preference: SkillPreference | None = None
    context: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    free_text_source: str = Field(min_length=1, max_length=1200)
    confidence: float = Field(default=0.5, ge=0, le=1)
    ambiguities: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator(
        "cuisine_preferences", "styles", "protein_preferences", "ingredient_preferences",
        "ingredient_exclusions", "dietary_constraints", "unavailable_equipment",
    )
    @classmethod
    def normalize_terms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("Meal intent terms may not exceed 80 characters.")
        return cleaned

    @field_validator("context")
    @classmethod
    def bounded_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 12 or len(str(value)) > 1200:
            raise ValueError("Meal intent context exceeds its bounded contract.")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "MealIntent":
        if self.desired_calorie_min is not None and self.desired_calorie_max is not None and self.desired_calorie_min > self.desired_calorie_max:
            raise ValueError("desired_calorie_min cannot exceed desired_calorie_max")
        if self.max_active_minutes is not None and self.max_total_minutes is not None and self.max_active_minutes > self.max_total_minutes:
            raise ValueError("max_active_minutes cannot exceed max_total_minutes")
        return self


class ChefIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str = Field(min_length=1, max_length=1200)
    meal_type: MealType | None = None
    servings: float | None = Field(default=None, gt=0, le=20)
    max_total_minutes: int | None = Field(default=None, ge=5, le=360)
    inventory_preference: InventoryPreference | None = None
    unavailable_equipment: tuple[str, ...] = Field(default=(), max_length=12)
    limit: int = Field(default=5, ge=3, le=5)
    conversation_thread_id: str | None = Field(default=None, max_length=160)


class IngredientRequirementRead(BaseModel):
    ingredient_name: str
    required_quantity: float
    available_quantity: float
    missing_quantity: float
    unit: str
    expiring_soon: bool = False


class ChefMealOptionRead(BaseModel):
    recommendation_id: str | None = None
    option_id: str | None = None
    recipe: "RecipeRead"
    score: float
    score_factors: dict[str, float]
    reason_codes: list[str]
    why_it_fits: str
    total_minutes: int
    active_minutes: int
    nutrition: dict[str, float | str | None]
    nutrition_confidence: Literal["COMPLETE", "PARTIAL", "UNKNOWN"]
    inventory_status: Literal["FULLY_IN_STOCK", "MOSTLY_IN_STOCK", "SHOPPING_REQUIRED", "INFEASIBLE"]
    ingredient_requirements: list[IngredientRequirementRead]
    missing_ingredients: list[str]
    expiring_ingredients_used: list[str]
    estimated_grocery_delta: float | None = None
    grocery_currency: str | None = None
    budget_status: str = "UNKNOWN"
    technique_opportunities: list[str] = Field(default_factory=list)


class ChefIntentRecommendationRead(BaseModel):
    intent: MealIntent
    interpretation_mode: Literal["AI", "DETERMINISTIC_FALLBACK", "EXPLICIT"]
    interpretation_warning: str | None = None
    recommendation_id: str | None = None
    options: list[ChefMealOptionRead]
    response_text: str


def _normalize_unit(value: str) -> str:
    unit = value.strip().lower()
    aliases = {
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
    return aliases.get(unit, unit)


class InventoryLotCreate(BaseModel):
    quantity: float = Field(gt=0)
    unit: str = "count"
    purchased_at: datetime | None = None
    expires_at: datetime | None = None
    expires_on: date | None = None
    storage_location: str | None = None
    source: str = "manual"
    notes: str | None = None

    @field_validator("unit")
    @classmethod
    def unit_is_known(cls, value: str) -> str:
        unit = _normalize_unit(value)
        if unit not in {"g", "kg", "ml", "l", "count", "serving"}:
            raise ValueError("Unit must be one of g, kg, ml, l, count, serving.")
        return unit

    @field_validator("purchased_at", "expires_at")
    @classmethod
    def datetimes_are_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class InventoryItemCreate(BaseModel):
    ingredient_name: str | None = Field(default=None, min_length=1, max_length=180)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = None
    canonical_unit: str = "count"
    default_storage_location: str | None = None
    is_staple: bool | None = None
    restock_threshold: float | None = Field(default=None, ge=0)
    restock_target: float | None = Field(default=None, ge=0)
    quantity: float = Field(default=1, ge=0)
    unit: str = "count"
    expires_on: date | None = None
    expires_at: datetime | None = None
    source: str = "manual"
    notes: str | None = None

    @field_validator("canonical_unit", "unit")
    @classmethod
    def unit_is_known(cls, value: str) -> str:
        unit = _normalize_unit(value)
        if unit not in {"g", "kg", "ml", "l", "count", "serving"}:
            raise ValueError("Unit must be one of g, kg, ml, l, count, serving.")
        return unit

    @field_validator("expires_at")
    @classmethod
    def datetime_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class InventoryLotRead(BaseModel):
    id: str
    inventory_item_id: str
    quantity: float
    unit: str
    purchased_at: datetime | None
    expires_at: datetime | None
    storage_location: str | None
    source: str
    source_reference_type: str | None = None
    source_reference_id: str | None = None
    confidence: float | None = None
    status: str
    version: int

    model_config = {"from_attributes": True}


class InventoryItemRead(BaseModel):
    id: str
    ingredient_name: str
    quantity: float
    unit: str
    expires_on: date | None
    source: str
    category: str | None = None
    canonical_unit: str = "count"
    default_storage_location: str | None = None
    is_staple: bool = False
    restock_threshold: float | None = None
    restock_target: float | None = None
    active: bool = True
    notes: str | None = None
    total_quantity: float = 0
    expiry_status: str = "no_expiry"
    lots: list[InventoryLotRead] = Field(default_factory=list)
    version: int

    model_config = {"from_attributes": True}


class InventoryMutationCreate(BaseModel):
    operation: Literal["add", "consume", "adjust", "discard", "expire", "reconcile"]
    quantity: float = Field(gt=0)
    unit: str
    reason: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None

    @field_validator("unit")
    @classmethod
    def unit_is_known(cls, value: str) -> str:
        return _normalize_unit(value)


class InventoryStapleUpdate(BaseModel):
    is_staple: bool
    restock_threshold: float | None = Field(default=None, ge=0)
    restock_target: float | None = Field(default=None, ge=0)


class RecipeIngredientCreate(BaseModel):
    inventory_item_id: str | None = None
    ingredient_name: str = Field(min_length=1, max_length=180)
    quantity: float = Field(gt=0)
    unit: str = "count"
    optional: bool = False
    substitution_group: str | None = None
    order_index: int = 0

    @field_validator("unit")
    @classmethod
    def unit_is_known(cls, value: str) -> str:
        unit = _normalize_unit(value)
        if unit not in {"g", "kg", "ml", "l", "count", "serving"}:
            raise ValueError("Unit must be one of g, kg, ml, l, count, serving.")
        return unit


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    preparation_minutes: int = Field(default=10, ge=0)
    cooking_minutes: int = Field(default=10, ge=0)
    servings: float = Field(default=1, gt=0)
    calories_per_serving: float = Field(default=0, ge=0)
    protein_g_per_serving: float = Field(default=0, ge=0)
    carbs_g_per_serving: float | None = Field(default=None, ge=0)
    fat_g_per_serving: float | None = Field(default=None, ge=0)
    protein_family: str | None = None
    difficulty: str = "easy"
    tags: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    techniques: list[dict] = Field(default_factory=list)
    ingredients: list[RecipeIngredientCreate] = Field(default_factory=list)
    notes: str | None = None


class RecipeIngredientRead(BaseModel):
    id: str
    recipe_id: str
    inventory_item_id: str | None
    ingredient_name: str
    quantity: float
    unit: str
    optional: bool
    substitution_group: str | None
    order_index: int
    version: int

    model_config = {"from_attributes": True}


class RecipeRead(BaseModel):
    id: str
    name: str
    description: str | None
    preparation_minutes: int
    cooking_minutes: int
    servings: float
    calories_per_serving: float
    protein_g_per_serving: float
    carbs_g_per_serving: float | None
    fat_g_per_serving: float | None
    protein_family: str | None
    difficulty: str
    tags: list[str]
    steps: list[str] = Field(default_factory=list)
    techniques: list[dict] = Field(default_factory=list)
    active: bool
    notes: str | None
    ingredients: list[RecipeIngredientRead] = Field(default_factory=list)
    version: int

    model_config = {"from_attributes": True}


class NutritionTargetUpsert(BaseModel):
    calories_target: float = Field(gt=0)
    protein_g_target: float = Field(gt=0)
    source: str = "manual"
    effective_from: datetime | None = None
    notes: str | None = None

    @field_validator("effective_from")
    @classmethod
    def datetime_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class NutritionTargetRead(BaseModel):
    id: str
    calories_target: float
    protein_g_target: float
    source: str
    effective_from: datetime
    effective_to: datetime | None
    status: str
    notes: str | None
    version: int

    model_config = {"from_attributes": True}


class NutritionProgressRead(BaseModel):
    date: date
    calories_target: float | None
    protein_g_target: float | None
    calories_consumed: float
    protein_g_consumed: float
    calories_remaining: float | None
    protein_g_remaining: float | None
    calories_over_target: float
    protein_g_over_target: float


class MealManualCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    consumed_at: datetime | None = None
    servings: float = Field(default=1, gt=0)
    calories: float = Field(default=0, ge=0)
    protein_g: float = Field(default=0, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    source_plan_block_id: str | None = None
    notes: str | None = None

    @field_validator("consumed_at")
    @classmethod
    def datetime_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class MealCompleteRequest(BaseModel):
    servings: float = Field(default=1, gt=0)
    consumed_at: datetime | None = None
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    source_plan_block_id: str | None = None
    notes: str | None = None
    feedback: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=160)
    actual_ingredients: list[dict] = Field(default_factory=list)

    @field_validator("consumed_at")
    @classmethod
    def datetime_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)


class MealHistoryRead(BaseModel):
    id: str
    recipe_id: str | None
    name_snapshot: str
    consumed_at: datetime
    servings: float
    calories_snapshot: float
    protein_g_snapshot: float
    carbs_g_snapshot: float | None
    fat_g_snapshot: float | None
    satisfaction: int | None
    source: str
    source_plan_block_id: str | None
    notes: str | None
    actual_usage: list[dict] = Field(default_factory=list, validation_alias="actual_usage_json")
    version: int

    model_config = {"from_attributes": True}


class RecommendationRequest(BaseModel):
    no_shopping: bool = False
    craving: str | None = None
    max_minutes: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=20)


class MealRecommendationRead(BaseModel):
    recommendation_id: str | None = None
    option_id: str | None = None
    recipe: RecipeRead
    score: float
    score_factors: dict[str, float]
    explanation: list[str]
    availability: str
    missing_ingredients: list[str]
    expiring_ingredients_used: list[str]
    estimated_missing_cost: float | None = None
    budget_state: str = "unknown"
    technique_opportunities: list[str] = Field(default_factory=list)


class ShoppingForecastRequest(BaseModel):
    window_days: int = Field(default=3, ge=3, le=7)
    limit: int = Field(default=5, ge=1, le=20)


class ShoppingNeedItemRead(BaseModel):
    id: str
    shopping_need_id: str
    inventory_item_id: str | None
    ingredient_name: str
    quantity: float
    unit: str
    satisfied: bool
    priority_class: str = "optional"
    reason: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    estimated_cost: float | None = None
    purchased_quantity: float = 0
    status: str = "needed"
    version: int

    model_config = {"from_attributes": True}


class ShoppingNeedRead(BaseModel):
    id: str
    title: str
    status: str
    required_by: datetime | None
    reason: str | None
    source: str
    forecast_window_days: int
    metadata_json: dict
    meal_plan_id: str | None = None
    action_id: str | None = None
    estimated_total: float | None = None
    currency: str = "EUR"
    items: list[ShoppingNeedItemRead] = Field(default_factory=list)
    version: int

    model_config = {"from_attributes": True}


class ManualShoppingNeedCreate(BaseModel):
    item_name: str = Field(min_length=1, max_length=180)
    quantity: float = Field(default=1, gt=0)
    unit: str = Field(default="count", min_length=1, max_length=40)
    priority_class: str = Field(default="optional", min_length=1, max_length=40)
    idempotency_key: str = Field(min_length=1, max_length=160)


class ShoppingPurchaseCreate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    add_to_inventory: bool = True


class ShoppingAggregateRead(BaseModel):
    ingredient_name: str
    quantity: float
    unit: str
    priority_class: str
    reasons: list[str]
    estimated_cost: float | None
    source_item_ids: list[str]
    status: str


class KitchenStatusRead(BaseModel):
    inventory_count: int
    expiring_lots: int
    expired_lots: int
    nutrition: NutritionProgressRead
    top_recommendation: MealRecommendationRead | None
    shopping_need_count: int
    active_candidate_count: int


class ChefRecommendationSetRead(BaseModel):
    recommendation_id: str
    options: list[MealRecommendationRead]


class MealSelectionCreate(BaseModel):
    recommendation_id: str
    option_id: str
    planned_for: datetime
    meal_type: str = "dinner"
    servings: float = Field(default=1, gt=0)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=20)
    ingredient_substitutions: dict[str, str] = Field(default_factory=dict)

    @field_validator("planned_for")
    @classmethod
    def planned_datetime_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class MealChoiceOutcomeRequest(BaseModel):
    feedback: str | None = Field(default=None, max_length=2000)


class MealPlanRead(BaseModel):
    id: str
    recipe_id: str
    recipe: RecipeRead
    recommendation_id: str | None
    recommendation_option_id: str | None
    planned_for: datetime
    meal_type: str
    status: str
    planned_servings: float
    nutrition_snapshot: dict
    planned_ingredients: list[dict] = Field(default_factory=list)
    modifications: dict = Field(default_factory=dict)
    shopping_action_id: str | None
    cooking_action_id: str | None
    meal_history_id: str | None
    version: int


class MealPlanCompleteRequest(BaseModel):
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=2000)
    actual_ingredients: list[dict] = Field(default_factory=list)


class MealPlanModifyRequest(BaseModel):
    servings: float | None = Field(default=None, gt=0, le=20)
    excluded_ingredients: list[str] | None = Field(default=None, max_length=20)
    ingredient_substitutions: dict[str, str] | None = None


class CookingSessionStartRequest(BaseModel):
    meal_plan_id: str
    conversation_thread_id: str | None = Field(default=None, max_length=160)


class CookingSessionUpdateRequest(BaseModel):
    current_step_index: int | None = Field(default=None, ge=0, le=500)
    timer_refs: tuple[str, ...] | None = Field(default=None, max_length=8)
    equipment_refs: tuple[str, ...] | None = Field(default=None, max_length=16)
    ingredient_changes: tuple[str, ...] | None = Field(default=None, max_length=24)
    temporary_notes: str | None = Field(default=None, max_length=1200)


class CompetencyRead(BaseModel):
    id: str
    technique_id: str
    technique_key: str
    technique_name: str
    estimated_level: float
    confidence: float
    evidence_count: int
    successful_repetitions: int
    last_practiced_at: datetime | None
    band: str
    version: int
