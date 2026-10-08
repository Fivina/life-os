from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
import json
import math
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_json_value(value: Any) -> Any:
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("Value must be finite JSON data.") from exc
    if len(encoded.encode("utf-8")) > 8_192:
        raise ValueError("Individual structured values must not exceed 8192 bytes.")
    return value


def _validate_schema_value(value: Any, schema: dict[str, Any], path: str = "answer") -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} is not in the declared enum.")
    expected_type = schema.get("type")
    type_matches = {
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
    }
    if expected_type in type_matches and not type_matches[expected_type](value):
        raise ValueError(f"{path} does not match declared type {expected_type}.")
    if expected_type == "object":
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        missing = set(required) - set(value)
        if missing:
            raise ValueError(f"{path} is missing required fields: {sorted(missing)}")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError(f"{path} contains undeclared fields.")
        for key, item in value.items():
            if key in properties:
                _validate_schema_value(item, properties[key], f"{path}.{key}")
    if expected_type == "array" and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema_value(item, schema["items"], f"{path}[{index}]")


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionOutputType(str, Enum):
    categorical = "categorical"
    boolean = "boolean"
    scalar = "scalar"
    structured = "structured"


class EntityReference(FrozenContract):
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=80)


class ProvenanceReference(FrozenContract):
    source_type: str = Field(min_length=1, max_length=80)
    source_id: str | None = Field(default=None, max_length=160)
    observed_at: datetime | None = None


class CognitiveEvent(FrozenContract):
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=80)
    occurred_at: datetime = Field(default_factory=_utcnow)
    domains: tuple[str, ...] = Field(default=(), max_length=8)
    entity_refs: tuple[EntityReference, ...] = Field(default=(), max_length=16)
    source_event_id: str | None = Field(default=None, max_length=36)
    conversation_thread_id: str | None = Field(default=None, max_length=36)
    message_id: str | None = Field(default=None, max_length=36)
    user_input_ref: str | None = Field(default=None, max_length=160)
    workspace_ref: str | None = Field(default=None, max_length=160)
    workspace_snapshot_ref: str | None = Field(default=None, max_length=160)
    world_revision: int | None = Field(default=None, ge=0)
    correlation_id: str | None = Field(default=None, max_length=160)
    causation_id: str | None = Field(default=None, max_length=160)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _validate_input = field_validator("input_payload", "metadata")(_ensure_json_value)


class DecisionQuestion(FrozenContract):
    question_id: str = Field(min_length=3, max_length=160)
    question_version: int = Field(ge=1)
    family: str = Field(min_length=1, max_length=80)
    output_type: DecisionOutputType
    allowed_choices: tuple[str, ...] = Field(default=(), max_length=255)
    score_rubric: tuple[str, ...] = Field(default=(), max_length=10)
    description: str = Field(min_length=1, max_length=600)
    response_schema: dict[str, Any] | None = None

    _validate_response_schema = field_validator("response_schema")(_ensure_json_value)

    @field_validator("question_id", "family")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("Decision identifiers must be lowercase dotted identifiers.")
        return value

    @model_validator(mode="after")
    def validate_output_contract(self) -> "DecisionQuestion":
        if len(set(self.allowed_choices)) != len(self.allowed_choices):
            raise ValueError("Decision choices must be unique.")
        if self.output_type == DecisionOutputType.categorical and len(self.allowed_choices) < 2:
            raise ValueError("Categorical questions require at least two allowed choices.")
        if self.output_type != DecisionOutputType.categorical and self.allowed_choices:
            raise ValueError("Allowed choices are only valid for categorical questions.")
        if self.output_type == DecisionOutputType.scalar and not 2 <= len(self.score_rubric) <= 10:
            raise ValueError("Scalar questions require an ordered score rubric with 2-10 labels.")
        if self.output_type != DecisionOutputType.scalar and self.score_rubric:
            raise ValueError("A score rubric is only valid for scalar questions.")
        if self.output_type == DecisionOutputType.structured and not self.response_schema:
            raise ValueError("Structured questions require a response schema.")
        if self.output_type != DecisionOutputType.structured and self.response_schema is not None:
            raise ValueError("A response schema is only valid for structured questions.")
        return self

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)


class ContextFact(FrozenContract):
    key: str = Field(min_length=1, max_length=120)
    value: Any
    provenance: tuple[ProvenanceReference, ...] = Field(min_length=1, max_length=4)

    _validate_value = field_validator("value")(_ensure_json_value)


class DecisionContext(FrozenContract):
    event_id: str = Field(min_length=1, max_length=160)
    question_id: str = Field(min_length=3, max_length=160)
    question_version: int = Field(ge=1)
    built_at: datetime = Field(default_factory=_utcnow)
    workspace_ref: str | None = Field(default=None, max_length=160)
    facts: tuple[ContextFact, ...] = Field(default=(), max_length=24)
    entity_refs: tuple[EntityReference, ...] = Field(default=(), max_length=16)
    memory_refs: tuple[str, ...] = Field(default=(), max_length=8)
    pattern_refs: tuple[str, ...] = Field(default=(), max_length=8)
    recent_intervention_refs: tuple[str, ...] = Field(default=(), max_length=5)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _validate_metadata = field_validator("metadata")(_ensure_json_value)

    @model_validator(mode="after")
    def validate_unique_facts(self) -> "DecisionContext":
        keys = [fact.key for fact in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("Decision context fact keys must be unique.")
        return self


class DecisionProviderResult(FrozenContract):
    question_id: str = Field(min_length=3, max_length=160)
    question_version: int = Field(ge=1)
    selected_answer: str | bool | int | float | dict[str, Any]
    probabilities: dict[str, float] | None = None
    provider: str = Field(min_length=1, max_length=80)
    provider_version: str = Field(min_length=1, max_length=80)
    model_version: str | None = Field(default=None, max_length=160)
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _validate_answer = field_validator("selected_answer", "metadata")(_ensure_json_value)

    @field_validator("probabilities")
    @classmethod
    def validate_probabilities(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is None:
            return value
        if not value or len(value) > 255:
            raise ValueError("Probability distributions must contain 1-255 choices.")
        if any(not math.isfinite(probability) or probability < 0 or probability > 1 for probability in value.values()):
            raise ValueError("Probabilities must be finite values between 0 and 1.")
        if abs(sum(value.values()) - 1.0) > 0.001:
            raise ValueError("Probability distributions must sum to 1.")
        return value

    def validate_for(self, question: DecisionQuestion) -> None:
        if (self.question_id, self.question_version) != (question.question_id, question.question_version):
            raise ValueError("Provider result targets a different question identity or version.")
        if question.output_type == DecisionOutputType.categorical:
            if not isinstance(self.selected_answer, str) or self.selected_answer not in question.allowed_choices:
                raise ValueError("Selected answer is not an allowed categorical choice.")
            if self.probabilities is not None and set(self.probabilities) != set(question.allowed_choices):
                raise ValueError("Categorical probabilities must cover exactly the allowed choices.")
        elif question.output_type == DecisionOutputType.boolean:
            if not isinstance(self.selected_answer, bool):
                raise ValueError("Boolean questions require a boolean answer.")
            if self.probabilities is not None and set(self.probabilities) != {"true", "false"}:
                raise ValueError("Boolean probabilities must use true and false keys.")
        elif question.output_type == DecisionOutputType.scalar:
            if isinstance(self.selected_answer, bool) or not isinstance(self.selected_answer, (int, float)):
                raise ValueError("Scalar questions require a numeric answer.")
            if not 0 <= self.selected_answer <= len(question.score_rubric) - 1:
                raise ValueError("Scalar answer is outside the declared score rubric.")
            if self.probabilities is not None and set(self.probabilities) != {
                str(index) for index in range(len(question.score_rubric))
            }:
                raise ValueError("Scalar probabilities must cover every score-rubric index.")
        elif question.output_type == DecisionOutputType.structured:
            if not isinstance(self.selected_answer, dict):
                raise ValueError("Structured questions require an object answer.")
            _validate_schema_value(self.selected_answer, question.response_schema or {})


class DecisionResult(DecisionProviderResult):
    latency_ms: int = Field(ge=0)
    host_policy_version: str = Field(min_length=1, max_length=80)


class DecisionExecution(FrozenContract):
    result: DecisionResult
    trace_id: str | None = None
    trace_status: Literal["persisted", "disabled", "failed"]


class DecisionQuestionRequest(FrozenContract):
    question: DecisionQuestion
    candidate_ref: EntityReference | None = None
    requested_fact_keys: tuple[str, ...] = Field(default=(), max_length=24)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _validate_metadata = field_validator("metadata")(_ensure_json_value)
