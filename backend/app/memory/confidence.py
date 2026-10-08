from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Iterable


SOURCE_RELIABILITY = {
    "user_statement": 0.82,
    "user_correction": 1.0,
    "user_confirmation": 1.0,
    "api": 1.0,
    "conversation": 0.72,
    "episode": 0.62,
    "inference": 0.42,
}

HALF_LIFE_DAYS = {
    "preference": 365,
    "personal_fact": 730,
    "routine_preference": 180,
    "constraint_preference": 540,
    "interaction_preference": 365,
    "domain_preference": 365,
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def evidence_confidence(evidence: Iterable, *, pinned: bool = False, user_confirmed: bool = False) -> float:
    if pinned:
        return 1.0
    support_miss = 1.0
    contradiction_miss = 1.0
    for item in evidence:
        reliability = SOURCE_RELIABILITY.get(item.evidence_kind, SOURCE_RELIABILITY.get(item.source_type, 0.55))
        signal = clamp(float(item.weight) * reliability)
        if item.direction == "contradicts":
            contradiction_miss *= 1.0 - signal
        else:
            support_miss *= 1.0 - signal
    support = 1.0 - support_miss
    contradiction = 1.0 - contradiction_miss
    confidence = clamp(0.25 + 0.75 * support - 0.65 * contradiction, 0.05, 0.99)
    if user_confirmed:
        confidence = max(confidence, 0.92)
    return round(confidence, 4)


def effective_confidence(memory, *, now: datetime | None = None) -> float:
    if memory.pinned:
        return 1.0
    if memory.status in {"forgotten", "archived", "contradicted"}:
        return 0.0
    current = now or datetime.now(UTC)
    observed = memory.last_confirmed_at or memory.last_observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    age_days = max(0.0, (current - observed).total_seconds() / 86400)
    half_life = HALF_LIFE_DAYS.get(memory.memory_type, 365)
    floor = 0.72 if memory.user_confirmed else 0.35
    decay = math.pow(0.5, age_days / half_life)
    return round(clamp(max(memory.confidence * decay, memory.confidence * floor)), 4)


def status_for(confidence: float, *, user_confirmed: bool = False, contradictory: bool = False) -> str:
    if contradictory:
        return "uncertain"
    if user_confirmed or confidence >= 0.58:
        return "active"
    if confidence >= 0.35:
        return "candidate"
    return "uncertain"

