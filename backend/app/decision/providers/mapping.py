from __future__ import annotations

import json
from typing import Any

from app.decision.errors import UnsupportedDecisionQuestion
from app.decision.schemas import DecisionContext, DecisionOutputType, DecisionQuestion


def bounded_state(context: DecisionContext, *, max_bytes: int) -> dict[str, Any]:
    state = {
        "facts": {fact.key: fact.value for fact in context.facts},
        "workspace_ref": context.workspace_ref,
        "entity_refs": [ref.model_dump(mode="json") for ref in context.entity_refs],
        "context_refs": {
            "memory": list(context.memory_refs),
            "patterns": list(context.pattern_refs),
            "recent_interventions": list(context.recent_intervention_refs),
        },
    }
    encoded = json.dumps(state, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > max_bytes:
        raise UnsupportedDecisionQuestion("Decision context exceeds the provider's declared input limit.")
    return state


def typed_question(question: DecisionQuestion) -> dict[str, Any]:
    if question.output_type == DecisionOutputType.categorical:
        return {
            "type": "choice",
            "instructions": question.description,
            "criteria": {choice: choice.replace("_", " ") for choice in question.allowed_choices},
        }
    if question.output_type == DecisionOutputType.boolean:
        return {
            "type": "noul",
            "instructions": question.description,
            "criteria": {"true": "yes", "false": "no"},
        }
    if question.output_type == DecisionOutputType.scalar:
        return {
            "type": "score",
            "instructions": question.description,
            "criteria": list(question.score_rubric),
        }
    raise UnsupportedDecisionQuestion(
        f"Provider mapping does not support {question.output_type.value} without an explicit rubric."
    )


def normalize_answer(answer: dict[str, Any], question: DecisionQuestion) -> tuple[Any, dict[str, float] | None, float | None]:
    answer_type = answer.get("type")
    if question.output_type == DecisionOutputType.categorical:
        if answer_type != "choice":
            raise ValueError("Expected a choice answer.")
        return answer.get("choice"), answer.get("probabilities"), answer.get("confidence")
    if question.output_type == DecisionOutputType.boolean:
        if answer_type != "noul":
            raise ValueError("Expected a noul answer.")
        probability = float(answer["noul"])
        return probability >= 0.5, {"true": probability, "false": 1 - probability}, max(probability, 1 - probability)
    if question.output_type == DecisionOutputType.scalar:
        if answer_type != "score":
            raise ValueError("Expected a score answer.")
        return answer.get("score"), answer.get("probabilities"), answer.get("confidence")
    raise UnsupportedDecisionQuestion(f"Unsupported provider answer for {question.output_type.value}.")
