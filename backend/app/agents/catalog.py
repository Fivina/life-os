from __future__ import annotations


DEFAULT_AGENT_MODELS: dict[str, dict[str, str]] = {
    "openai": {
        "ECONOMY": "gpt-5-nano",
        "FAST": "gpt-5-mini",
        "REASONING": "gpt-5.1",
    },
    "gemini": {
        "ECONOMY": "gemini-3.5-flash-lite",
        "FAST": "gemini-3.8-flash",
        "REASONING": "gemini-3.8-flash",
    },
}


def default_model(provider: str, capability: str) -> str:
    provider_models = DEFAULT_AGENT_MODELS.get(provider, DEFAULT_AGENT_MODELS["openai"])
    return provider_models[capability]
