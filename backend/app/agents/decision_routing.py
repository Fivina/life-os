from __future__ import annotations

import re

from app.decision.context import DecisionContextBuilder
from app.decision.gateway import DecisionGateway
from app.decision.questions import AGENT_SPECIALIST_ADVICE_V1
from app.decision.schemas import CognitiveEvent


class AgentDecisionRouter:
    """One optional bounded Jev hint, never delegation or execution authority."""

    signals = {
        "chef": r"\b(cook|cooking|meal|food|kitchen|dinner)\b",
        "learning-coach": r"\b(study|studying|exam|learning|course)\b",
        "fitness-coach": r"\b(workout|training|fitness|exercise|gym)\b",
        "home-manager": r"\b(chore|chores|housework|cleaning|household)\b",
        "finance": r"\b(budget|finance|money|spending|cost)\b",
    }

    def __init__(self, settings):
        self.settings = settings

    def candidates(self, message: str, allowed: list[str]) -> list[str]:
        if not re.search(r"\b(prioriti\w*|choose|trade.?off|balance|decide)\b", message, re.I):
            return []
        matches = [name for name, pattern in self.signals.items()
                   if name in allowed and re.search(pattern, message, re.I)]
        return matches if len(matches) > 1 else []

    def advise(self, context, request, allowed: list[str], *, gateway=None) -> dict:
        candidates = self.candidates(request.message, allowed)
        fallback = {"recommended_agent": "self-core", "reason_code": "HOST_FALLBACK", "authority": "advice_only"}
        if not candidates:
            return fallback
        context.record_activity("routing", "started", "jev")
        try:
            settings = self.settings.model_copy(update={
                "decision_infra_enabled": True, "decision_routing_mode": "JEV_ONLY",
                "decision_shadow_enabled": False, "jev_timeout_seconds": min(self.settings.jev_timeout_seconds, 1.5),
                "jev_max_retries": 0,
            })
            event = CognitiveEvent(event_type="agent.routing.requested", source="explicit_user_request",
                                   correlation_id=context.request_id, world_revision=context.user.world_revision)
            decision_context = DecisionContextBuilder().build(
                event=event, question=AGENT_SPECIALIST_ADVICE_V1,
                facts={"request": request.message[:800], "available_agents": ["self-core", *candidates]},
                metadata={"selection_only": True, "explicit_user_request": True},
            )
            with context.db.begin_nested():
                result = (gateway or DecisionGateway(settings)).evaluate(
                    context.db, context.user, event=event, question=AGENT_SPECIALIST_ADVICE_V1,
                    context=decision_context, skill_name="self-core", skill_version=context.skill.manifest.version,
                ).result
            if result.selected_answer not in ["self-core", *candidates] or result.confidence is None or result.confidence < 0.72:
                context.record_activity("routing", "failed", "jev")
                return fallback
            context.record_activity("routing", "completed", "jev")
            return {"recommended_agent": result.selected_answer, "reason_code": "BOUNDED_ROUTING_HINT",
                    "authority": "advice_only"}
        except Exception:
            context.record_activity("routing", "failed", "jev")
            return fallback
