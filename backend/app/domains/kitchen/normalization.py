from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Ingredient, IngredientAlias, UserProfile

COMMON_ALIASES = {
    "chk brst": "chicken breast",
    "chicken breasts": "chicken breast",
    "boneless chicken breasts": "chicken breast",
    "bio nat jog": "natural yogurt",
    "tomatoes": "tomato",
    "onions": "onion",
    "eggs": "egg",
}


def normalize_name(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|mg|l|ml|cl|pack|pcs?)\b", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return COMMON_ALIASES.get(text, text)


def resolve_ingredient(
    db: Session,
    user: UserProfile,
    raw_name: str,
    *,
    merchant: str | None = None,
    default_unit: str | None = None,
    category: str | None = None,
    source: str = "deterministic",
) -> Ingredient:
    normalized = normalize_name(raw_name)
    merchant_key = merchant.strip().lower() if merchant else None
    alias = db.scalar(
        select(IngredientAlias).where(
            IngredientAlias.user_id == user.id,
            IngredientAlias.normalized_alias == normalized,
            (func.lower(IngredientAlias.merchant) == merchant_key) if merchant_key else IngredientAlias.merchant.is_(None),
        )
    )
    if alias is not None:
        ingredient = db.get(Ingredient, alias.ingredient_id)
        if ingredient is not None:
            return ingredient
    ingredient = db.scalar(select(Ingredient).where(Ingredient.user_id == user.id, Ingredient.normalized_name == normalized))
    if ingredient is None:
        ingredient = Ingredient(user_id=user.id, name=raw_name.strip(), normalized_name=normalized, default_unit=default_unit, category=category)
        db.add(ingredient)
        db.flush()
    if normalize_name(raw_name) != ingredient.normalized_name or merchant:
        existing = db.scalar(select(IngredientAlias).where(IngredientAlias.user_id == user.id, IngredientAlias.normalized_alias == normalize_name(raw_name), IngredientAlias.merchant == merchant))
        if existing is None:
            db.add(IngredientAlias(user_id=user.id, ingredient_id=ingredient.id, alias=raw_name, normalized_alias=normalize_name(raw_name), merchant=merchant, source=source))
            db.flush()
    return ingredient
