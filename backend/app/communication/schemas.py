from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.attention.schemas import AttentionAction


INTENT_VERSION = 1
RESPONSE_POLICY_VERSION = "response-policy-v1"


class SpeakingPolicy(BaseModel):
    """Versioned presentation rules; facts and action authority remain outside this policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["response-policy-v1"] = RESPONSE_POLICY_VERSION
    warm: bool = True
    concise: bool = True
    natural: bool = True
    avoid_repetition: bool = True
    avoid_fake_friendliness: bool = True
    avoid_alarmism: bool = True
    serious_importance_threshold: int = Field(default=85, ge=0, le=100)


class SpeechAct(str, Enum):
    acknowledge = "ACKNOWLEDGE"
    confirm = "CONFIRM"
    inform = "INFORM"
    status = "STATUS"
    ask = "ASK"
    mention = "MENTION"
    propose = "PROPOSE"
    warn = "WARN"
    error = "ERROR"
    degraded = "DEGRADED"


class ResponseTone(str, Enum):
    warm = "WARM"
    calm = "CALM"
    neutral = "NEUTRAL"
    serious = "SERIOUS"


class ResponseVerbosity(str, Enum):
    brief = "BRIEF"
    concise = "CONCISE"
    normal = "NORMAL"


class ResponseMode(str, Enum):
    deterministic = "DETERMINISTIC"
    generative = "GENERATIVE"
    deterministic_fallback = "DETERMINISTIC_FALLBACK"


class ResponseModePreference(str, Enum):
    auto = "AUTO"
    deterministic = "DETERMINISTIC"
    generative = "GENERATIVE"


class StructuredFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=120)
    value: str | int | float | bool | None
    unit: str | None = Field(default=None, max_length=40)
    source_ref: str | None = Field(default=None, max_length=180)


class StructuredClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=500)
    source_refs: tuple[str, ...] = Field(default=(), max_length=8)


class CommunicativeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    version: Literal[1] = INTENT_VERSION
    purpose: SpeechAct
    attention_action: AttentionAction
    reason_code: str = Field(min_length=1, max_length=160)
    importance: int = Field(default=50, ge=0, le=100)
    urgency: float = Field(default=0.0, ge=0, le=1)
    facts: tuple[StructuredFact, ...] = Field(default=(), max_length=24)
    claims: tuple[StructuredClaim, ...] = Field(default=(), max_length=12)
    current_state_refs: tuple[str, ...] = Field(default=(), max_length=24)
    workspace_ref: str | None = Field(default=None, max_length=180)
    conversation_ref: str | None = Field(default=None, max_length=180)
    cognitive_trace_ref: str | None = Field(default=None, max_length=180)
    plan_proposal_ref: str | None = Field(default=None, max_length=180)
    user_response_required: bool = False
    question: str | None = Field(default=None, max_length=600)
    recommended_next_action: str | None = Field(default=None, max_length=500)
    must_include: tuple[str, ...] = Field(default=(), max_length=8)
    must_not_claim: tuple[str, ...] = Field(default=(), max_length=12)
    tone: ResponseTone = ResponseTone.warm
    verbosity: ResponseVerbosity = ResponseVerbosity.concise
    response_mode_preference: ResponseModePreference = ResponseModePreference.auto
    fallback_template_key: str = Field(default="generic", min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def bounded_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 24 or len(str(value)) > 4000:
            raise ValueError("Communicative intent metadata is too large.")
        return value


class ComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: CommunicativeIntent
    persist_message: bool = True
    recent_context: tuple[str, ...] = Field(default=(), max_length=6)

    @field_validator("recent_context")
    @classmethod
    def bounded_context(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if sum(len(item) for item in value) > 2400:
            raise ValueError("Recent wording context is too large.")
        return value


class ComposedResponse(BaseModel):
    intent_id: str
    intent_version: int
    policy_version: str = RESPONSE_POLICY_VERSION
    response_id: str
    text: str
    mode: ResponseMode
    conversation_id: str | None = None
    message_id: str | None = None
    cognitive_trace_ref: str | None = None
    plan_proposal_ref: str | None = None
    provider: str | None = None
    model: str | None = None
    capability: str | None = None
    fallback_used: bool = False
    streamed: bool = False
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_eur: float | None = Field(default=None, ge=0)
    world_revision: int | None = None
    created_at: datetime


class ResponseStreamEventType(str, Enum):
    start = "START"
    text_delta = "TEXT_DELTA"
    complete = "COMPLETE"
    error = "ERROR"


class ResponseStreamEvent(BaseModel):
    event_type: ResponseStreamEventType
    response_id: str
    conversation_id: str | None = None
    message_id: str | None = None
    sequence: int = Field(ge=0)
    text_delta: str | None = None
    final_response: ComposedResponse | None = None
    error_code: str | None = None
    world_revision: int | None = None
