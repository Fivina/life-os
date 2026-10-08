from __future__ import annotations

import re
from dataclasses import dataclass


CANONICAL_PATTERNS = (
    re.compile(r"\b(?:i have|there (?:is|are)|my (?:fridge|inventory) has)\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:my )?(?:weight|bank balance|account balance)\s+(?:is|was)\b", re.IGNORECASE),
    re.compile(r"\b(?:exam|appointment|lecture|meeting)\s+(?:is|starts|ends)\s+(?:on|at)\b", re.IGNORECASE),
    re.compile(r"\b(?:today|tomorrow)(?:'s)?\s+(?:plan|calendar|schedule)\b", re.IGNORECASE),
    re.compile(r"\b(?:remaining|left)\s+\d+(?:\.\d+)?\s*(?:hours?|minutes?|kg|kilograms?)\b", re.IGNORECASE),
)

TRANSIENT_PATTERNS = (
    re.compile(r"\b(?:today|right now|at the moment)\b.*\b(?:tired|hungry|stressed|sad|happy|busy|free)\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+(?:tired|hungry|stressed|sad|happy|busy)\b", re.IGNORECASE),
)

SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:diagnos(?:is|ed)|depression|anxiety disorder|bipolar|adhd|autis(?:m|tic))\b", re.IGNORECASE),
    re.compile(r"\b(?:political ideology|sexual orientation|religious identity|ethnicity)\b", re.IGNORECASE),
)

TRIVIAL_PATTERNS = (
    re.compile(r"^(?:thanks?|thank you|ok(?:ay)?|hello|hi|bye)[.! ]*$", re.IGNORECASE),
    re.compile(r"^(?:open|show|go to)\s+\w+[.! ]*$", re.IGNORECASE),
)

IDENTITY_PATTERNS = (
    re.compile(r"^(?:actually\s+)?(?:i|we)\s+(?:really\s+)?(?:don't like|do not like|dislike|hate|like|love|prefer)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:actually\s+)?(?:i|please)\s+(?:always|never)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:remember(?: that)?\s+)(.+)$", re.IGNORECASE),
)


@dataclass(frozen=True)
class MemoryPolicyDecision:
    allowed: bool
    reason: str | None = None


def semantic_identity(content: str) -> str:
    value = re.sub(r"\s+", " ", content.strip()).strip(" .,:;!?")
    for pattern in IDENTITY_PATTERNS:
        match = pattern.match(value)
        if match:
            value = match.group(1).strip(" .,:;!?")
            break
    value = re.sub(r"\b(?:anymore|now)\b$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"[^a-z0-9\s-]", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()[:255]


def validate_semantic_memory(content: str, *, explicit: bool) -> MemoryPolicyDecision:
    normalized = re.sub(r"\s+", " ", content.strip())
    if any(pattern.search(normalized) for pattern in TRIVIAL_PATTERNS):
        return MemoryPolicyDecision(False, "trivial_interaction")
    if any(pattern.search(normalized) for pattern in TRANSIENT_PATTERNS):
        return MemoryPolicyDecision(False, "transient_state")
    if any(pattern.search(normalized) for pattern in CANONICAL_PATTERNS):
        return MemoryPolicyDecision(False, "canonical_state")
    if not explicit and any(pattern.search(normalized) for pattern in SENSITIVE_PATTERNS):
        return MemoryPolicyDecision(False, "sensitive_inference")
    return MemoryPolicyDecision(True)
