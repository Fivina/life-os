from __future__ import annotations

import json
import re

from app.ai.types import AIMessage, AIRequest
from app.attention.schemas import AttentionAction
from app.communication.schemas import (
    CommunicativeIntent,
    ResponseMode,
    ResponseModePreference,
    SpeakingPolicy,
    SpeechAct,
)


SYSTEM_PREFIX = """You render a Life OS CommunicativeIntent into final user-facing text.
Preserve every supplied fact and authority boundary. Do not invent dates, quantities, prices,
probabilities, commitments, diagnoses, or actions. Do not execute tools or imply that a proposed
change has already happened. Use warm, natural, concise language without fake friendliness,
alarmism, internal scores, or hidden reasoning. Return only the final wording."""


class ResponseComposer:
    """Pure language renderer. It has no database, tool, planner, or domain mutation access."""

    max_dynamic_chars = 6000

    def __init__(self, policy: SpeakingPolicy | None = None) -> None:
        self.policy = policy or SpeakingPolicy()

    @property
    def policy_version(self) -> str:
        return self.policy.version

    def select_mode(self, intent: CommunicativeIntent, *, generative_enabled: bool) -> ResponseMode:
        if intent.response_mode_preference == ResponseModePreference.deterministic:
            return ResponseMode.deterministic
        if not generative_enabled:
            return ResponseMode.deterministic
        if intent.response_mode_preference == ResponseModePreference.generative:
            return ResponseMode.generative
        if intent.purpose in {SpeechAct.propose, SpeechAct.warn} or len(intent.facts) + len(intent.claims) >= 3:
            return ResponseMode.generative
        return ResponseMode.deterministic

    def deterministic_text(self, intent: CommunicativeIntent) -> str:
        facts = {item.key: item.value for item in intent.facts}
        key = intent.fallback_template_key
        if key == "inventory_empty" and facts.get("item"):
            return f"{str(facts['item']).strip().capitalize()} are now empty."
        if key == "timer_remaining" and facts.get("remaining_minutes") is not None:
            return f"The timer has {facts['remaining_minutes']} minutes left."
        if key == "proposal_rejected":
            return "Proposal rejected. Nothing changed in your current plan."
        if key == "workspace_resumed":
            return "Workspace resumed."
        if key == "feedback_logged":
            return "Feedback logged."
        if key == "saved":
            return "Saved."
        if key == "chef_option" and facts.get("meal"):
            meal = str(facts["meal"])
            minutes = facts.get("time")
            inventory = str(facts.get("inventory") or "UNKNOWN").replace("_", " ").lower()
            protein = facts.get("protein")
            missing = facts.get("missing_count")
            parts = [f"{meal} takes {minutes} minutes" if minutes is not None else meal, f"inventory is {inventory}"]
            if protein is not None:
                parts.append(f"it provides {protein} g protein")
            if missing:
                parts.append(f"{missing} ingredient{'s are' if missing != 1 else ' is'} missing")
            return "; ".join(parts) + "."
        if key == "morning_briefing":
            parts = [str(value).strip() for value in facts.values() if value not in (None, "")]
            return ("Good morning. " + ". ".join(parts) + ".") if parts else "Good morning. Your day has no scheduled blocks yet."
        if key in {"self_core_next", "self_core_gym", "self_core_workspace", "self_core_proposal", "self_core_cross_domain"}:
            return str(facts.get("answer") or "I couldn't resolve that from the current structured state.")
        if key == "notebook_idea_saved":
            return "Saved as an implementation idea. Nothing was added to your roadmap or plan."
        if key == "plan_unchanged":
            return "Nothing changed in your current plan."
        if key == "plan_proposal" or intent.purpose == SpeechAct.propose:
            subject = facts.get("exam_title") or facts.get("subject") or "Your plan"
            state = facts.get("trajectory_state") or facts.get("state") or "needs attention"
            return f"{subject} {state}. I prepared a recovery proposal. Review it before applying any changes."
        if intent.question:
            return intent.question
        if intent.must_include:
            return " ".join(item.strip() for item in intent.must_include if item.strip())
        if intent.claims:
            return " ".join(item.text.strip() for item in intent.claims)
        if intent.purpose == SpeechAct.confirm:
            return "Done."
        if intent.purpose == SpeechAct.error:
            return "I couldn't complete that."
        return "Life OS has an update."

    def build_request(self, intent: CommunicativeIntent, recent_context: tuple[str, ...] = ()) -> AIRequest:
        payload = {
            "speaking_policy": self.policy.model_dump(mode="json"),
            "intent": intent.model_dump(mode="json", exclude={"metadata"}),
            "recent_wording_context": list(recent_context[-6:]),
        }
        dynamic = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        if len(dynamic) > self.max_dynamic_chars:
            raise ValueError("Response composition context exceeds the bounded limit.")
        return AIRequest(
            system_instruction=SYSTEM_PREFIX,
            messages=[AIMessage(role="user", content=dynamic)],
            tools=[],
            temperature=0.35,
            cache_key=self.policy_version,
            metadata={
                "mode": "response_composition",
                "intent_id": intent.intent_id,
                "policy_version": self.policy_version,
                "fake_response": self.deterministic_text(intent),
            },
        )

    def validate_generated(self, intent: CommunicativeIntent, text: str | None, *, tool_call_count: int = 0) -> str:
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned or len(cleaned) > 2000 or tool_call_count:
            raise ValueError("Generated response is empty, oversized, or attempted a tool call.")
        allowed_material = json.dumps(
            {
                "facts": [item.model_dump(mode="json") for item in intent.facts],
                "must_include": intent.must_include,
                "question": intent.question,
            },
            ensure_ascii=True,
        )
        allowed_numbers = set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?", allowed_material))
        generated_numbers = set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?", cleaned))
        if not generated_numbers.issubset(allowed_numbers):
            raise ValueError("Generated response introduced an unsupported numeric claim.")
        return cleaned

    @staticmethod
    def should_speak(intent: CommunicativeIntent) -> bool:
        return intent.attention_action not in {AttentionAction.silent, AttentionAction.act_silently}
