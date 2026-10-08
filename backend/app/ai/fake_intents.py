from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.ai.types import AIProviderError
from app.assistant.schemas import (
    AssistantDomain,
    AssistantIntent,
    AssistantIntentType,
    AssistantRole,
    ModelTier,
)


@dataclass(frozen=True)
class ProviderResult:
    intent: AssistantIntent
    provider: str
    model: str


def _next_weekday(now: datetime, weekday: int) -> datetime:
    days = (weekday - now.weekday()) % 7
    if days == 0:
        days = 7
    return now + timedelta(days=days)


def _aware_local(now: datetime | None, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


class DeterministicAssistantFake:
    provider_name = "fake"

    def complete_structured(
        self,
        *,
        role: AssistantRole,
        context: dict,
        user_message: str,
        now: datetime | None,
        timezone: str,
        model: str,
    ) -> ProviderResult:
        text = user_message.strip()
        lowered = text.lower()
        current = _aware_local(now, timezone)

        if re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening)[!.?,\s]*", lowered):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.discussion,
                    domain=AssistantDomain.general,
                    user_facing_summary=(
                        "Hi! I’m here. Ask about your plan, learning, fitness, meals, or capture something for review."
                    ),
                    model_tier=ModelTier.no_ai,
                ),
                self.provider_name,
                model,
            )
        if (
            re.search(r"\b(?:which|what|who|do you see|can you see|available|list)\b", lowered)
            and re.search(r"\b(?:agents?|specialists?|assistants?)\b", lowered)
        ):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.discussion,
                    domain=AssistantDomain.general,
                    user_facing_summary=(
                        "This chat can use Self Core, Fitness, Learning, Home, Chef, and Finance. "
                        "Choose a specialist with the role buttons above the conversation."
                    ),
                    model_tier=ModelTier.no_ai,
                ),
                self.provider_name,
                model,
            )

        if "malformed" in lowered:
            raise AIProviderError("malformed_structured_output", "Fake provider emitted malformed structured output.")
        if "provider failure" in lowered or "break provider" in lowered:
            raise AIProviderError("provider_unavailable", "Fake provider failure fixture.", retryable=True)
        if "run sql" in lowered or "delete all my plans" in lowered or "execute sql" in lowered:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.general,
                    tool_name="execute_sql",
                    arguments={"statement": text},
                    user_facing_summary="That tool is not available.",
                    confidence=1,
                ),
                self.provider_name,
                model,
            )
        if "maybe" in lowered or "considering" in lowered or "what if" in lowered:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.discussion,
                    domain=AssistantDomain.general,
                    user_facing_summary="This sounds like discussion rather than an instruction to change Life OS.",
                    model_tier=ModelTier.no_ai,
                ),
                self.provider_name,
                model,
            )
        state_match = re.search(r"energy\s*(\d{1,3}).*mental(?: state)?\s*(\d{1,3})", lowered)
        if state_match:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.state,
                    tool_name="report_state",
                    arguments={"energy": int(state_match.group(1)), "mental_state": int(state_match.group(2))},
                    user_facing_summary=f"Report Energy {state_match.group(1)} and Mental State {state_match.group(2)}.",
                    confidence=0.98,
                    model_tier=ModelTier.standard,
                ),
                self.provider_name,
                model,
            )
        if "feel" in lowered and ("worse" in lowered or "bad" in lowered or "tired" in lowered):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.clarification_required,
                    domain=AssistantDomain.state,
                    user_facing_summary="What are your Energy and Mental State from 0-100?",
                    confidence=0.95,
                ),
                self.provider_name,
                model,
            )
        commitment_match = re.search(r"(?:meeting|meet)\s+(.+?)\s+at\s+(.+?)\s+tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s+for\s+(\d+(?:\.\d+)?)h", lowered)
        if commitment_match:
            hour = int(commitment_match.group(3))
            minute = int(commitment_match.group(4) or 0)
            duration_hours = float(commitment_match.group(5))
            day = current.date() + timedelta(days=1)
            starts_at = datetime.combine(day, time(hour, minute), tzinfo=current.tzinfo)
            ends_at = starts_at + timedelta(hours=duration_hours)
            title_subject = commitment_match.group(1).strip()
            title = f"Meeting {title_subject}".title()
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.planning,
                    tool_name="create_commitment",
                    arguments={
                        "title": title,
                        "level": "hard",
                        "commitment_type": "hard",
                        "starts_at": starts_at.isoformat(),
                        "ends_at": ends_at.isoformat(),
                        "timezone": timezone,
                        "location": commitment_match.group(2).strip().title(),
                    },
                    requires_confirmation=True,
                    user_facing_summary=f"Create commitment: {title}, tomorrow {hour:02d}:{minute:02d}-{ends_at.strftime('%H:%M')}.",
                    confidence=0.94,
                ),
                self.provider_name,
                model,
            )
        intention_match = re.search(r"(?:need to|i need to|add)\s+(.+?)\s+for\s+(\d+)\s+minutes?\s+before\s+friday", lowered)
        if intention_match:
            deadline = datetime.combine(_next_weekday(current, 4).date(), time(23, 59), tzinfo=current.tzinfo)
            title = intention_match.group(1).strip().capitalize()
            domain = "learning" if any(word in title.lower() for word in ["study", "macro", "exam"]) else "personal"
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.learning if domain == "learning" else AssistantDomain.general,
                    tool_name="add_intention",
                    arguments={
                        "title": title,
                        "domain": domain,
                        "level": "goal_critical" if domain == "learning" else "maintenance",
                        "estimated_minutes": int(intention_match.group(2)),
                        "duration_min_minutes": min(25, int(intention_match.group(2))),
                        "deadline": deadline.isoformat(),
                        "context": "study" if domain == "learning" else None,
                    },
                    user_facing_summary=f"Add intention: {title} for {intention_match.group(2)} minutes before Friday.",
                    confidence=0.92,
                ),
                self.provider_name,
                model,
            )
        study_match = re.search(r"studied\s+(.+?)\s+for\s+(\d+)\s+minutes?.*quality\s+([1-5])", lowered)
        if study_match:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.learning,
                    tool_name="log_study_session",
                    arguments={
                        "exam_hint": study_match.group(1).strip(),
                        "duration_minutes": int(study_match.group(2)),
                        "quality_rating": int(study_match.group(3)),
                    },
                    requires_confirmation=True,
                    user_facing_summary=f"Log study: {study_match.group(2)} minutes, quality {study_match.group(3)}.",
                    confidence=0.9,
                ),
                self.provider_name,
                model,
            )
        if "workout" in lowered and ("next" in lowered or "what" in lowered):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.query,
                    domain=AssistantDomain.fitness,
                    tool_name="get_fitness_status",
                    arguments={},
                    user_facing_summary="Get the next workout from Fitness.",
                    confidence=0.95,
                ),
                self.provider_name,
                model,
            )
        if any(word in lowered for word in ["eat", "dinner", "lunch", "breakfast", "meal", "chef", "kitchen"]):
            no_shopping = any(phrase in lowered for phrase in ["no shopping", "don't want to shop", "dont want to shop", "without shopping", "use what i have"])
            craving = None
            craving_match = re.search(r"(?:craving|want)\s+([a-zA-Z ]+)", lowered)
            if craving_match:
                craving = craving_match.group(1).strip()
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.query,
                    domain=AssistantDomain.kitchen,
                    tool_name="get_kitchen_recommendations",
                    arguments={"no_shopping": no_shopping, "craving": craving, "limit": 5},
                    user_facing_summary="Get deterministic Kitchen meal recommendations.",
                    confidence=0.92,
                ),
                self.provider_name,
                model,
            )
        if "personal model" in lowered or "personal learning" in lowered or "personalization" in lowered:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.query,
                    domain=AssistantDomain.general,
                    tool_name="get_personal_model_summary",
                    arguments={},
                    user_facing_summary="Read Personal Learning diagnostics.",
                    confidence=0.92,
                ),
                self.provider_name,
                model,
            )
        if ("how am i doing" in lowered or "how prepared" in lowered) and ("macro" in lowered or "exam" in lowered):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.query,
                    domain=AssistantDomain.learning,
                    tool_name="get_learning_status",
                    arguments={"exam_hint": "macro"},
                    user_facing_summary="Summarize the Learning trajectory.",
                    confidence=0.95,
                ),
                self.provider_name,
                model,
            )
        if "why" in lowered and ("scheduled" in lowered or "plan" in lowered or "macro" in lowered):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.explain,
                    domain=AssistantDomain.planning,
                    tool_name="get_plan_block_explanation",
                    arguments={"query": text},
                    user_facing_summary="Explain a scheduled PlanBlock using stored decision factors.",
                    confidence=0.88,
                    model_tier=ModelTier.standard,
                ),
                self.provider_name,
                model,
            )
        if "replan" in lowered:
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.command,
                    domain=AssistantDomain.planning,
                    tool_name="request_replan",
                    arguments={"reason": "ASSISTANT_REQUESTED"},
                    user_facing_summary="Request a remaining-day replan through the control loop.",
                    confidence=0.9,
                ),
                self.provider_name,
                model,
            )
        if any(phrase in lowered for phrase in ("today", "what's on", "what is on", "daily summary", "day summary")):
            return ProviderResult(
                AssistantIntent(
                    type=AssistantIntentType.query,
                    domain=AssistantDomain.general,
                    tool_name="get_today_summary",
                    arguments={},
                    user_facing_summary="Summarize today's current Life OS context.",
                    confidence=0.8,
                ),
                self.provider_name,
                model,
            )
        return ProviderResult(
            AssistantIntent(
                type=AssistantIntentType.discussion,
                domain=AssistantDomain.general,
                user_facing_summary=(
                    "I’m on the deterministic test provider, so I can only handle a limited set of "
                    "Life OS requests. Enable a live agent in Settings for open-ended chat."
                ),
                confidence=0.35,
                model_tier=ModelTier.no_ai,
            ),
            self.provider_name,
            model,
        )

