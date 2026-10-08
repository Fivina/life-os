from __future__ import annotations

from app.ai.fake_intents import DeterministicAssistantFake
from app.assistant.schemas import AssistantIntentType


def interpret(message: str):
    return DeterministicAssistantFake().complete_structured(
        role="GENERAL_ASSISTANT",
        context={},
        user_message=message,
        now=None,
        timezone="UTC",
        model="fake-test",
    ).intent


def test_greeting_does_not_trigger_a_life_os_summary():
    intent = interpret("hi")

    assert intent.type == AssistantIntentType.discussion
    assert "Hi!" in (intent.user_facing_summary or "")
    assert intent.tool_name is None


def test_agent_capability_question_gets_a_direct_answer():
    intent = interpret("which agents do you see")

    assert intent.type == AssistantIntentType.discussion
    assert "Self Core" in (intent.user_facing_summary or "")
    assert intent.tool_name is None


def test_unmatched_prompt_is_not_misrepresented_as_a_summary_request():
    intent = interpret("How does this system learn from my corrections?")

    assert intent.type == AssistantIntentType.discussion
    assert "deterministic test provider" in (intent.user_facing_summary or "")
    assert intent.tool_name is None


def test_explicit_today_question_keeps_the_summary_tool():
    intent = interpret("What is on today?")

    assert intent.type == AssistantIntentType.query
    assert intent.tool_name == "get_today_summary"
