from __future__ import annotations

from enum import Enum
import hashlib

from app.decision.errors import DecisionProviderError, DecisionProviderTimeout, UnsupportedDecisionQuestion
from app.decision.provider_schemas import ProviderCapabilities, ProviderHealth, ProviderSupport
from app.decision.schemas import DecisionContext, DecisionOutputType, DecisionProviderResult, DecisionQuestion


class FakeDecisionScenario(str, Enum):
    normal = "normal"
    low_confidence = "low_confidence"
    invalid_response = "invalid_response"
    unsupported = "unsupported"
    timeout = "timeout"
    error = "error"


class FakeDecisionProvider:
    """Deterministic architecture fixture, not a production intelligence provider."""

    name = "fake"
    provider_version = "1"
    model_version = "fake-decision-checkpoint-v1"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            enabled=True,
            available=True,
            supported_output_types=tuple(DecisionOutputType),
            max_choices=16,
            supported_languages=("*",),
            metadata={"fixture_only": True},
        )

    def supports(self, *, question: DecisionQuestion, context: DecisionContext) -> ProviderSupport:
        del context
        if question.output_type == DecisionOutputType.categorical and len(question.allowed_choices) > 16:
            return ProviderSupport(supported=False, reason_code="CHOICE_LIMIT")
        return ProviderSupport(supported=True, reason_code="SUPPORTED")

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.name,
            enabled=True,
            available=True,
            loaded=True,
            provider_version=self.provider_version,
            model_version=self.model_version,
            runtime_metadata={"fixture_only": True},
        )

    def evaluate(self, *, question: DecisionQuestion, context: DecisionContext) -> DecisionProviderResult:
        scenario = FakeDecisionScenario(context.metadata.get("fake_scenario", FakeDecisionScenario.normal.value))
        if scenario == FakeDecisionScenario.unsupported:
            raise UnsupportedDecisionQuestion(f"Fake provider does not support {question.question_id}.")
        if scenario == FakeDecisionScenario.timeout:
            raise DecisionProviderTimeout("Fake provider timeout fixture.", retryable=True)
        if scenario == FakeDecisionScenario.error:
            raise DecisionProviderError("Fake provider error fixture.", retryable=True)
        if scenario == FakeDecisionScenario.invalid_response:
            return DecisionProviderResult.model_construct(
                question_id=question.question_id,
                question_version=question.question_version,
                selected_answer="__invalid_choice__",
                probabilities={"invalid": 1.2},
                provider=self.name,
                provider_version=self.provider_version,
                model_version=self.model_version,
                confidence=1.2,
                metadata={"simulation": scenario.value},
            )

        forced_answer = context.metadata.get("fake_selected_answer")
        if forced_answer is not None:
            if question.output_type != DecisionOutputType.categorical or forced_answer not in question.allowed_choices:
                raise DecisionProviderError("Forced fake answer does not match the question contract.")
            remainder = (1 - 0.82) / (len(question.allowed_choices) - 1)
            return DecisionProviderResult(
                question_id=question.question_id,
                question_version=question.question_version,
                selected_answer=forced_answer,
                probabilities={choice: 0.82 if choice == forced_answer else remainder for choice in question.allowed_choices},
                provider=self.name,
                provider_version=self.provider_version,
                model_version=self.model_version,
                confidence=0.82,
                metadata={"simulation": scenario.value, "forced_fixture": True},
            )

        stable_context = context.model_dump_json(exclude={"built_at"})
        seed = hashlib.sha256(
            (question.canonical_json() + stable_context).encode("utf-8")
        ).digest()
        low_confidence = scenario == FakeDecisionScenario.low_confidence
        if question.output_type == DecisionOutputType.categorical:
            selected_index = int.from_bytes(seed[:4], "big") % len(question.allowed_choices)
            selected = question.allowed_choices[selected_index]
            if low_confidence:
                probabilities = {choice: 1 / len(question.allowed_choices) for choice in question.allowed_choices}
            else:
                winning = 0.82
                remainder = (1 - winning) / (len(question.allowed_choices) - 1)
                probabilities = {
                    choice: winning if index == selected_index else remainder
                    for index, choice in enumerate(question.allowed_choices)
                }
        elif question.output_type == DecisionOutputType.boolean:
            selected = bool(seed[0] % 2)
            confidence_value = 0.51 if low_confidence else 0.82
            probabilities = {
                "true": confidence_value if selected else 1 - confidence_value,
                "false": 1 - confidence_value if selected else confidence_value,
            }
        elif question.output_type == DecisionOutputType.scalar:
            selected = round(int.from_bytes(seed[:2], "big") / 65535, 6)
            probabilities = None
        elif question.output_type == DecisionOutputType.structured:
            selected = self._structured_fixture(question.response_schema or {}, seed)
            probabilities = None
        else:  # pragma: no cover - enum exhaustiveness
            raise UnsupportedDecisionQuestion(f"Unsupported output type {question.output_type}.")

        return DecisionProviderResult(
            question_id=question.question_id,
            question_version=question.question_version,
            selected_answer=selected,
            probabilities=probabilities,
            provider=self.name,
            provider_version=self.provider_version,
            model_version=self.model_version,
            confidence=0.51 if low_confidence else 0.82,
            metadata={"simulation": scenario.value},
        )

    def evaluate_batch(
        self,
        *,
        questions: tuple[DecisionQuestion, ...],
        contexts: tuple[DecisionContext, ...],
    ) -> dict[str, DecisionProviderResult]:
        if len(questions) != len(contexts):
            raise ValueError("Questions and contexts must have equal length.")
        return {
            question.question_id: self.evaluate(question=question, context=context)
            for question, context in zip(questions, contexts, strict=True)
        }

    @classmethod
    def _structured_fixture(cls, schema: dict, seed: bytes) -> dict:
        properties = schema.get("properties") or {}
        result: dict = {}
        for index, key in enumerate(schema.get("required") or properties.keys()):
            definition = properties.get(key) or {}
            if definition.get("enum"):
                result[key] = definition["enum"][0]
            elif definition.get("type") == "boolean":
                result[key] = bool(seed[index % len(seed)] % 2)
            elif definition.get("type") == "integer":
                result[key] = int(seed[index % len(seed)])
            elif definition.get("type") == "number":
                result[key] = round(seed[index % len(seed)] / 255, 6)
            elif definition.get("type") == "array":
                result[key] = []
            elif definition.get("type") == "object":
                result[key] = cls._structured_fixture(definition, seed[index:] or seed)
            else:
                result[key] = f"fixture-{seed.hex()[index:index + 8]}"
        return result
