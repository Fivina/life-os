from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    kind: Literal["api", "public", "import"] = "api"
    capabilities: tuple[str, ...] = ()
    attribution: str | None = None


PROVIDERS = {
    item.id: item for item in (
        ProviderDefinition("api-football", "API-Football", capabilities=("fixtures",)),
        ProviderDefinition("usda", "USDA FoodData Central", capabilities=("nutrition",)),
        ProviderDefinition("tmdb", "TMDB", capabilities=("movie_metadata",), attribution="This product uses the TMDB API but is not endorsed or certified by TMDB."),
        ProviderDefinition("plaid", "Plaid", capabilities=("credential_test",)),
        ProviderDefinition("openai", "OpenAI", capabilities=("chat", "images")),
        ProviderDefinition("open-food-facts", "Open Food Facts", "public", ("nutrition",)),
        ProviderDefinition("wger", "wger", "public", ("exercise_catalog",)),
        ProviderDefinition("letterboxd", "Letterboxd", "import", ("file_import",)),
    )
}
SECRET_PROVIDERS = frozenset(p.id for p in PROVIDERS.values() if p.kind == "api")


def provider_definition(provider: str, *, require_secret: bool = False) -> ProviderDefinition:
    definition = PROVIDERS.get(provider)
    if definition is None:
        raise HTTPException(404, "Unsupported integration provider.")
    if require_secret and definition.kind != "api":
        raise HTTPException(409, "This integration does not use managed credentials.")
    return definition
