from __future__ import annotations

import hashlib
from typing import Mapping

from app.core.config import Settings
from app.decision.errors import DecisionProviderUnavailable
from app.decision.provider_schemas import ProviderRoute, RoutingMode, RoutingReason
from app.decision.providers.base import DecisionProvider
from app.decision.schemas import DecisionContext, DecisionQuestion


class DecisionRoutingPolicy:
    """Deterministic host policy for operational, fallback, and shadow providers."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def route(
        self,
        *,
        question: DecisionQuestion,
        context: DecisionContext,
        providers: Mapping[str, DecisionProvider],
    ) -> ProviderRoute:
        override = context.metadata.get("decision_provider_override")
        if override and self.settings.app_env.lower() != "production":
            provider_id = self._resolve_provider_id(str(override), providers)
            self._require_supported(provider_id, providers, question, context)
            return self._route(provider_id, question, reason=RoutingReason.manual_test_override)

        mode = RoutingMode(self.settings.decision_routing_mode.upper())
        if mode == RoutingMode.fake:
            legacy = self.settings.decision_provider
            provider_id = self._resolve_provider_id(legacy, providers)
            reason = RoutingReason.legacy_provider_setting if legacy != "fake" else RoutingReason.primary_for_task_family
            self._require_supported(provider_id, providers, question, context)
            return self._route(provider_id, question, reason=reason)
        if mode == RoutingMode.laya_only:
            self._require_supported("laya_local", providers, question, context)
            return self._route("laya_local", question)
        if mode == RoutingMode.jev_only:
            self._require_supported("jev", providers, question, context)
            return self._route("jev", question)

        primary, fallback, reason = self._auto_route(question, context, providers)
        shadow = self._shadow_provider(
            primary=primary,
            question=question,
            context=context,
            providers=providers,
        ) if mode == RoutingMode.shadow or self.settings.decision_shadow_enabled else None
        return ProviderRoute(
            primary_provider=primary,
            fallback_provider=fallback,
            shadow_provider=shadow,
            reason_code=reason,
            policy_version=self.settings.decision_routing_policy_version,
            minimum_confidence=self._confidence_threshold(question.family),
        )

    def should_sample_shadow(self, *, event_id: str, question: DecisionQuestion) -> bool:
        if self.settings.decision_shadow_sample_rate <= 0:
            return False
        if self.settings.shadow_family_set and question.family not in self.settings.shadow_family_set:
            return False
        digest = hashlib.sha256(
            f"{self.settings.decision_routing_policy_version}:{event_id}:{question.question_id}:{question.question_version}".encode()
        ).digest()
        sample = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
        return sample < self.settings.decision_shadow_sample_rate

    def _auto_route(
        self,
        question: DecisionQuestion,
        context: DecisionContext,
        providers: Mapping[str, DecisionProvider],
    ) -> tuple[str, str | None, RoutingReason]:
        laya_ok = self._supported("laya_local", providers, question, context)
        jev_ok = self._supported("jev", providers, question, context)
        high_cardinality = len(question.allowed_choices) > self.settings.laya_max_choices
        if jev_ok:
            return "jev", "laya_local" if laya_ok else None, (
                RoutingReason.high_cardinality if high_cardinality else RoutingReason.primary_for_task_family
            )
        if laya_ok:
            return "laya_local", None, RoutingReason.primary_for_task_family
        raise DecisionProviderUnavailable("No configured decision provider supports this question and context.")

    def _shadow_provider(
        self,
        *,
        primary: str,
        question: DecisionQuestion,
        context: DecisionContext,
        providers: Mapping[str, DecisionProvider],
    ) -> str | None:
        configured = self._resolve_provider_id(self.settings.decision_shadow_provider, providers, required=False)
        if not configured or configured == primary:
            return None
        return configured if self._supported(configured, providers, question, context) else None

    def _route(
        self,
        provider_id: str,
        question: DecisionQuestion,
        *,
        reason: RoutingReason = RoutingReason.primary_for_task_family,
    ) -> ProviderRoute:
        return ProviderRoute(
            primary_provider=provider_id,
            reason_code=reason,
            policy_version=self.settings.decision_routing_policy_version,
            minimum_confidence=self._confidence_threshold(question.family),
        )

    def _confidence_threshold(self, family: str) -> float:
        thresholds = self.settings.decision_confidence_thresholds
        return thresholds.get(family, thresholds.get("default", 0.72))

    @staticmethod
    def _resolve_provider_id(
        requested: str,
        providers: Mapping[str, DecisionProvider],
        *,
        required: bool = True,
    ) -> str | None:
        aliases = {"laya": "laya_local", "laya_local": "laya_local", "jev": "jev", "fake": "fake"}
        provider_id = aliases.get(requested, requested)
        if provider_id not in providers:
            if required:
                raise DecisionProviderUnavailable(f"Decision provider {requested} is not configured.")
            return None
        return provider_id

    @staticmethod
    def _supported(
        provider_id: str,
        providers: Mapping[str, DecisionProvider],
        question: DecisionQuestion,
        context: DecisionContext,
    ) -> bool:
        provider = providers.get(provider_id)
        return bool(provider and provider.supports(question=question, context=context).supported)

    def _require_supported(
        self,
        provider_id: str,
        providers: Mapping[str, DecisionProvider],
        question: DecisionQuestion,
        context: DecisionContext,
    ) -> None:
        if not self._supported(provider_id, providers, question, context):
            raise DecisionProviderUnavailable(f"Decision provider {provider_id} cannot serve this question and context.")
