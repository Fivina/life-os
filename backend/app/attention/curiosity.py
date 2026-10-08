from __future__ import annotations

from app.attention.schemas import CuriosityAction, CuriosityDecision, CuriosityInputs


class CuriosityPolicy:
    """Bounded interaction-value baseline using only explicit operational inputs."""

    policy_version = "curiosity-policy-v1"
    ask_threshold = 0.28
    defer_threshold = 0.08
    ask_max_interruption_cost = 0.45

    def evaluate(self, inputs: CuriosityInputs) -> CuriosityDecision:
        benefit = inputs.importance * inputs.uncertainty * inputs.decision_impact * inputs.naturalness
        cost = (
            0.35 * inputs.interruption_cost
            + 0.25 * inputs.annoyance
            + 0.40 * inputs.inferability_elsewhere
        )
        score = round(benefit - cost, 6)
        if inputs.importance < 0.25:
            action, reason = CuriosityAction.skip, "low_importance"
        elif inputs.inferability_elsewhere >= 0.80:
            action, reason = CuriosityAction.skip, "inferable_elsewhere"
        elif score >= self.ask_threshold and inputs.interruption_cost <= self.ask_max_interruption_cost:
            action, reason = CuriosityAction.ask_now, "interaction_value_high"
        elif benefit >= self.ask_threshold and inputs.interruption_cost > self.ask_max_interruption_cost:
            action, reason = CuriosityAction.defer, "interruption_cost_high"
        elif score >= self.defer_threshold:
            action, reason = CuriosityAction.defer, "interaction_value_deferred"
        else:
            action, reason = CuriosityAction.skip, "interaction_value_low"
        return CuriosityDecision(action=action, score=score, reason_code=reason, policy_version=self.policy_version)
