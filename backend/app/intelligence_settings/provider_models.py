from __future__ import annotations

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.models import UserProfile
from app.intelligence_settings.provider_credentials import ProviderSecretStore


MODEL_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/models",
}


class ProviderModelCatalog:
    def __init__(self, secret_store: ProviderSecretStore | None = None):
        self.secret_store = secret_store or ProviderSecretStore()

    def list_models(self, db: Session, user: UserProfile, provider: str) -> list[str]:
        endpoint = MODEL_ENDPOINTS.get(provider)
        if endpoint is None:
            raise HTTPException(status_code=404, detail="Unsupported provider.")
        api_key = self.secret_store.get(db, user, provider)
        try:
            response = httpx.get(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=httpx.Timeout(8.0, connect=3.0),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(status_code=502, detail=f"Could not load {provider.title()} models.") from None

        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail=f"Could not load {provider.title()} models.")
        entries = payload.get("data") or payload.get("models") or []
        if not isinstance(entries, list):
            raise HTTPException(status_code=502, detail=f"Could not load {provider.title()} models.")
        names = set()
        for entry in entries:
            model = entry.get("id") or entry.get("name") if isinstance(entry, dict) else None
            if not isinstance(model, str):
                continue
            model = model.removeprefix("models/")
            if provider == "openai" and not model.startswith(("gpt-", "o1", "o3", "o4")):
                continue
            if provider == "gemini" and "gemini" not in model.lower():
                continue
            if any(kind in model.lower() for kind in ("embedding", "image", "audio", "transcribe", "whisper", "tts")):
                continue
            if model and len(model) <= 160:
                names.add(model)
        return sorted(names)[:250]
