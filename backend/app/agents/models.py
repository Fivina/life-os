from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.routing import CapabilityRouter
from app.ai.types import AICapability, AIProviderError, CAPABILITY_RANK
from app.ai.usage import AIUsageService
from app.assistant.schemas import ModelTier
from app.agents.catalog import DEFAULT_AGENT_MODELS
from app.core.config import Settings
from app.database.models import UserIntelligenceSettings, UserProfile
from app.decision.context import DecisionContextBuilder
from app.decision.gateway import DecisionGateway
from app.decision.questions import COGNITION_AGENT_TIER_V1
from app.decision.schemas import CognitiveEvent, DecisionContext
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.skills.models import LoadedSkill


@dataclass(frozen=True)
class AgentModelSelection:
    provider: str
    model: str
    capability: AICapability


class AgentModelResolver:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.capabilities = CapabilityRouter(settings)
        self.usage = AIUsageService(settings)

    def resolve(
        self, skill: LoadedSkill, preferred_tier: ModelTier, *, db: Session, user: UserProfile,
        capability: AICapability | None = None, optional: bool = False,
        test_model_name: str | None = None,
    ) -> AgentModelSelection:
        requested = capability or (
            AICapability.reasoning if preferred_tier == ModelTier.strong else skill.manifest.default_capability
        )
        if CAPABILITY_RANK[requested] > CAPABILITY_RANK[skill.manifest.max_capability]:
            raise AIProviderError("skill_capability_rejected", "This skill cannot use the requested capability.")
        budget = self.usage.budget_state(db, user.id)
        effective = self.capabilities.effective_capability(requested, budget=budget, optional=optional)
        if CAPABILITY_RANK[effective] > CAPABILITY_RANK[skill.manifest.max_capability]:
            raise AIProviderError("skill_capability_rejected", "The budget-selected capability is not allowed for this skill.")
        if test_model_name is not None:
            return AgentModelSelection("fake", test_model_name, effective)
        preferences = self._preferences(db, user)
        preference = preferences.get(skill.manifest.name) or {}
        secret_store = ProviderSecretStore()
        provider = preference.get("provider")
        if provider not in {"openai", "gemini"}:
            provider = self.settings.agent_provider
            if not secret_store.configured(db, user, provider):
                provider = next(
                    (candidate for candidate in ("openai", "gemini") if secret_store.configured(db, user, candidate)),
                    provider,
                )
        if not secret_store.configured(db, user, provider):
            provider_name = {"openai": "OpenAI", "gemini": "Google Gemini"}[provider]
            raise AIProviderError(
                "agent_credential_missing",
                f"Add a {provider_name} API key in Settings before using this agent.",
            )
        tier = {
            AICapability.economy: "economy_model",
            AICapability.fast: "fast_model",
            AICapability.reasoning: "reasoning_model",
        }.get(effective)
        if tier is None:
            raise AIProviderError("agent_capability_unsupported", "This provider route supports text agent capabilities only.")
        model = preference.get(tier) or DEFAULT_AGENT_MODELS[provider][effective.name.upper()]
        if not isinstance(model, str) or not model.strip():
            raise AIProviderError("agent_model_missing", "Choose a model for this agent in Settings.")
        return AgentModelSelection(provider, model.strip(), effective)

    @staticmethod
    def _preferences(db: Session, user: UserProfile) -> dict:
        row = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        return ((row.metadata_json or {}).get("agent_model_preferences") or {}) if row else {}

    def resolve_optional(
        self, db: Session, user: UserProfile, skill: LoadedSkill, *, event: CognitiveEvent,
        facts: Mapping[str, Any], gateway: DecisionGateway | None = None,
        decision_context: DecisionContext | None = None,
        test_model_name: str | None = None,
    ) -> AgentModelSelection | None:
        """Optional host-triggered cognition fails closed and never applies to a user request."""
        if not self.settings.decision_infra_enabled:
            return None
        try:
            context = decision_context or DecisionContextBuilder().build(
                event=event,
                question=COGNITION_AGENT_TIER_V1,
                facts=facts,
                metadata={"selection_only": True, "explicit_user_request": False},
            )
            execution = (gateway or DecisionGateway(self.settings)).evaluate(
                db, user, event=event, question=COGNITION_AGENT_TIER_V1, context=context,
                skill_name=skill.manifest.name, skill_version=skill.manifest.version,
            )
            result = execution.result
            threshold = self.settings.decision_confidence_thresholds.get("cognition", 0.72)
            if result.confidence is None or result.confidence < threshold:
                return None
            if result.selected_answer == "NO_AGENT":
                return None
            capability = AICapability(result.selected_answer)
            return self.resolve(
                skill, ModelTier.standard, db=db, user=user, capability=capability,
                optional=True, test_model_name=test_model_name,
            )
        except Exception:
            return None
