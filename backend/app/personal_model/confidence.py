from __future__ import annotations

from math import exp, log

MIN_EVIDENCE = {
    "capacity": 20,
    "completion": 12,
    "activation": 12,
    "preference": 8,
    "routine": 8,
    "state_transition": 20,
}

PROMOTION_CONFIDENCE = {
    "capacity": 0.75,
    "completion": 0.65,
    "activation": 0.65,
    "preference": 0.6,
    "routine": 0.6,
    "state_transition": 0.75,
}

CAPABILITY_MODELS = {"capacity", "state_transition"}


def recency_weight(age_days: float, half_life_days: float = 30.0) -> float:
    if age_days <= 0:
        return 1.0
    return exp(-log(2) * age_days / half_life_days)


def confidence_score(model_type: str, evidence_n: int, effective_evidence_n: float, improvement: float, consistency: float) -> float:
    threshold = MIN_EVIDENCE[model_type]
    evidence_component = min(1.0, effective_evidence_n / threshold)
    improvement_component = max(0.0, min(1.0, improvement))
    consistency_component = max(0.0, min(1.0, consistency))
    if model_type in CAPABILITY_MODELS:
        score = 0.6 * evidence_component + 0.25 * consistency_component + 0.15 * improvement_component
    else:
        score = 0.55 * evidence_component + 0.25 * consistency_component + 0.20 * improvement_component
    if evidence_n < threshold:
        score = min(score, 0.49)
    return round(max(0.0, min(0.99, score)), 4)


def influence_allowed(model_type: str, confidence: float, evidence_n: int) -> bool:
    return evidence_n >= MIN_EVIDENCE[model_type] and confidence >= PROMOTION_CONFIDENCE[model_type]
