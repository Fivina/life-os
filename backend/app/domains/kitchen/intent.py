from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest
from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import UserProfile
from app.domains.kitchen.schemas import ChefIntentRequest, ExpiryPriority, HeavinessPreference, InventoryPreference, MealIntent, NoveltyPreference


logger = get_logger(__name__)
INTERPRETER_VERSION = "meal-intent-interpreter-v1"


@dataclass(frozen=True)
class MealIntentInterpretation:
    intent: MealIntent
    mode: str
    warning: str | None = None
    provider: str | None = None
    model: str | None = None


def deterministic_fallback(text: str) -> MealIntent:
    """Preserve only obvious constraints when generative interpretation is unavailable."""
    lowered = " ".join(text.lower().split())
    minute_match = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?)\b", lowered)
    cuisines = tuple(name for name in ("turkish", "italian", "greek", "mexican", "indian", "japanese") if name in lowered)
    styles: list[str] = []
    if any(term in lowered for term in ("mother food", "home style", "home-style", "homestyle")):
        styles.append("home_style")
    if any(term in lowered for term in ("comforting", "comfort food")):
        styles.append("comfort_food")
    if "quick" in lowered:
        styles.append("quick")
    proteins: list[str] = []
    for name in ("chicken", "beef", "lamb", "fish", "turkey", "meat", "tofu", "beans"):
        if name in lowered:
            proteins.append(name)
    inventory = InventoryPreference.shopping_allowed
    if any(term in lowered for term in ("use what i have", "no shopping", "without shopping")):
        inventory = InventoryPreference.use_what_i_have
    elif "minimal shopping" in lowered:
        inventory = InventoryPreference.minimal_shopping
    high_protein = "high protein" in lowered or "protein-rich" in lowered
    heaviness = None
    if any(term in lowered for term in ("not too heavy", "light but", "something light")):
        heaviness = HeavinessPreference.light_to_medium
    elif "hearty" in lowered:
        heaviness = HeavinessPreference.hearty
    exclusions = tuple(match.group(1).strip() for match in re.finditer(r"\bwithout\s+([a-z][a-z -]{1,40})(?:,|\.|$|\band\b)", lowered))
    return MealIntent(
        cuisine_preferences=cuisines,
        styles=tuple(styles),
        protein_preferences=tuple(proteins),
        ingredient_exclusions=exclusions,
        max_total_minutes=int(minute_match.group(1)) if minute_match and 5 <= int(minute_match.group(1)) <= 360 else None,
        protein_priority="HIGH" if high_protein else "NORMAL",
        heaviness_preference=heaviness,
        novelty_preference=NoveltyPreference.balanced,
        inventory_preference=inventory,
        expiry_priority=ExpiryPriority.prefer_expiring if "use expiring" in lowered else ExpiryPriority.normal,
        free_text_source=text,
        confidence=0.72 if any((minute_match, cuisines, styles, proteins, high_protein, heaviness)) else 0.35,
        ambiguities=() if any((minute_match, cuisines, styles, proteins, high_protein, heaviness)) else ("meal_preferences_unspecified",),
    )


def _apply_explicit(intent: MealIntent, request: ChefIntentRequest) -> MealIntent:
    updates = {"free_text_source": request.request}
    for field in ("meal_type", "servings", "max_total_minutes", "inventory_preference"):
        value = getattr(request, field)
        if value is not None:
            updates[field] = value
    if request.unavailable_equipment:
        updates["unavailable_equipment"] = request.unavailable_equipment
    return intent.model_copy(update=updates)


def interpret_meal_intent(
    db: Session,
    user: UserProfile,
    request: ChefIntentRequest,
    settings: Settings,
    *,
    gateway: AIGateway | None = None,
) -> MealIntentInterpretation:
    fallback = _apply_explicit(deterministic_fallback(request.request), request)
    if not settings.chef_intent_enabled or not settings.chef_intent_generative_enabled or not settings.ai_enabled:
        return MealIntentInterpretation(fallback, "DETERMINISTIC_FALLBACK", "Generative interpretation is disabled.")
    ai_request = AIRequest(
        system_instruction=(
            "Interpret only the supplied meal request into the MealIntent JSON schema. "
            "Do not propose recipes, calculate nutrition, inspect inventory, infer medical restrictions, "
            "or add constraints not present in the request. Return JSON only."
        ),
        messages=[AIMessage(role="user", content=request.request)],
        response_schema=MealIntent.model_json_schema(),
        temperature=0.1,
        cache_key=INTERPRETER_VERSION,
        metadata={
            "mode": "meal_intent",
            "interpreter_version": INTERPRETER_VERSION,
            "fake_response": fallback.model_dump(mode="json"),
        },
    )
    try:
        response = (gateway or AIGateway(settings)).complete(
            db,
            user,
            request_id=str(uuid4()),
            assistant_role="CHEF_INTENT_INTERPRETER",
            skill_name="meal-intent",
            skill_version="1",
            capability=AICapability.fast,
            request=ai_request,
            conversation_thread_id=request.conversation_thread_id,
            optional=False,
        )
        raw = json.loads(response.text or "")
        raw["free_text_source"] = request.request
        intent = _apply_explicit(MealIntent.model_validate(raw), request)
        return MealIntentInterpretation(intent, "AI", provider=response.provider, model=response.model)
    except (AIProviderError, ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("meal_intent_fallback", extra={"user_id": user.id, "error_type": type(exc).__name__})
        return MealIntentInterpretation(fallback, "DETERMINISTIC_FALLBACK", "The structured interpretation failed validation; obvious constraints were preserved.")
