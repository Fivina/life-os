from __future__ import annotations

from app.decision.schemas import DecisionOutputType, DecisionQuestion


ATTENTION_ACTION_CHOICES = (
    "SILENT",
    "ACT_SILENTLY",
    "SHOW_PASSIVELY",
    "MENTION_WHEN_NATURAL",
    "ASK",
    "PROPOSE",
    "INTERRUPT",
    "ESCALATE_TO_GEMINI",
)


ATTENTION_ACTION_V1 = DecisionQuestion(
    question_id="attention.action",
    question_version=1,
    family="attention",
    output_type=DecisionOutputType.categorical,
    allowed_choices=ATTENTION_ACTION_CHOICES,
    description="Choose a bounded attention intent for an explicit candidate; the host policy retains authority.",
)

COGNITION_AGENT_TIER_V1 = DecisionQuestion(
    question_id="cognition.agent_tier",
    question_version=1,
    family="cognition",
    output_type=DecisionOutputType.categorical,
    allowed_choices=("NO_AGENT", "ECONOMY", "FAST", "REASONING"),
    description="Select whether bounded optional cognition merits an agent run and its host-owned capability tier.",
)


MEMORY_CONTEXT_RELEVANT_V1 = DecisionQuestion(
    question_id="memory.context_relevant",
    question_version=1,
    family="memory",
    output_type=DecisionOutputType.categorical,
    allowed_choices=("relevant", "irrelevant"),
    description="Classify whether a bounded memory candidate is relevant to an explicit current context.",
)

AGENT_SPECIALIST_ADVICE_V1 = DecisionQuestion(
    question_id="cognition.specialist_advice", question_version=1, family="cognition",
    output_type=DecisionOutputType.categorical,
    allowed_choices=("self-core", "chef", "learning-coach", "fitness-coach", "home-manager", "finance"),
    description="Choose the most relevant available specialist or self-core for an ambiguous cross-domain request. "
                "Only available_agents may be selected. This is advisory, not permission to delegate or mutate.",
)

SYSTEM_TEST_BOOLEAN_V1 = DecisionQuestion(
    question_id="system.fixture_boolean",
    question_version=1,
    family="system",
    output_type=DecisionOutputType.boolean,
    description="Exercise the boolean decision contract without product behavior.",
)

STRATEGY_INTERVENTION_NEEDED_V1 = DecisionQuestion(
    question_id="strategy.intervention_needed",
    question_version=1,
    family="strategy",
    output_type=DecisionOutputType.categorical,
    allowed_choices=("SUPPORT_HOST_POLICY", "OBSERVE", "ASK_FOR_TRADEOFF"),
    description="Judge whether structured strategic evidence deserves attention; host policy retains all authority.",
)

OPPORTUNITY_RELEVANCE_V1 = DecisionQuestion(
    question_id="opportunity.relevance",
    question_version=1,
    family="context_relevance",
    output_type=DecisionOutputType.categorical,
    allowed_choices=("RELEVANT", "UNCERTAIN", "IRRELEVANT"),
    description="Judge an ambiguous, pre-filtered opportunity. The host retains filtering, attention, and mutation authority.",
)


class DecisionQuestionRegistry:
    def __init__(self, questions: tuple[DecisionQuestion, ...] = ()):
        self._questions: dict[tuple[str, int], DecisionQuestion] = {}
        for question in questions:
            self.register(question)

    def register(self, question: DecisionQuestion) -> None:
        key = (question.question_id, question.question_version)
        existing = self._questions.get(key)
        if existing is not None and existing.canonical_json() != question.canonical_json():
            raise ValueError(f"Question semantics changed without a version change: {question.question_id} v{question.question_version}")
        self._questions[key] = question

    def get(self, question_id: str, question_version: int) -> DecisionQuestion:
        try:
            return self._questions[(question_id, question_version)]
        except KeyError as exc:
            raise KeyError(f"Unknown decision question {question_id} v{question_version}") from exc


DEFAULT_QUESTION_REGISTRY = DecisionQuestionRegistry(
    (ATTENTION_ACTION_V1, COGNITION_AGENT_TIER_V1, MEMORY_CONTEXT_RELEVANT_V1, SYSTEM_TEST_BOOLEAN_V1,
     STRATEGY_INTERVENTION_NEEDED_V1, OPPORTUNITY_RELEVANCE_V1, AGENT_SPECIALIST_ADVICE_V1)
)
