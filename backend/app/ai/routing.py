from __future__ import annotations

from dataclasses import dataclass

from app.ai.types import AICapability, AIProviderError
from app.core.config import Settings


@dataclass(frozen=True)
class AIModelRoute:
    provider: str
    model: str
    capability: AICapability
    temperature: float


@dataclass(frozen=True)
class AIBudgetState:
    monthly_spend_eur: float
    budget_eur: float
    warning: bool
    economy_only: bool
    optional_suppressed: bool


class CapabilityRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def effective_capability(
        capability: AICapability, *, budget: AIBudgetState | None = None, optional: bool = False,
    ) -> AICapability:
        if budget and budget.optional_suppressed and optional:
            raise AIProviderError("budget_restricted", "The optional AI request was skipped because the monthly budget threshold was reached.")
        if budget and budget.economy_only and capability in {AICapability.fast, AICapability.reasoning}:
            return AICapability.economy
        return capability

    def resolve(self, capability: AICapability, *, budget: AIBudgetState | None = None, optional: bool = False) -> AIModelRoute:
        effective = self.effective_capability(capability, budget=budget, optional=optional)
        model = {
            AICapability.economy: self.settings.ai_model_economy,
            AICapability.fast: self.settings.ai_model_fast,
            AICapability.reasoning: self.settings.ai_model_reasoning,
            AICapability.embedding: self.settings.ai_model_embedding,
            AICapability.vision: self.settings.ai_model_vision,
            AICapability.image: self.settings.ai_model_image,
        }.get(effective)
        if not model:
            raise AIProviderError("capability_unavailable", f"AI capability {effective.value} is not configured.")
        temperature = 0.15 if effective == AICapability.reasoning else 0.25
        return AIModelRoute(provider=self.settings.ai_provider.lower(), model=model, capability=effective, temperature=temperature)
