from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AttentionAction(str, Enum):
    silent = "SILENT"
    act_silently = "ACT_SILENTLY"
    show_passively = "SHOW_PASSIVELY"
    mention_when_natural = "MENTION_WHEN_NATURAL"
    ask = "ASK"
    propose = "PROPOSE"
    interrupt = "INTERRUPT"
    escalate_to_gemini = "ESCALATE_TO_GEMINI"


class AttentionItemStatus(str, Enum):
    pending = "PENDING"
    eligible = "ELIGIBLE"
    surfaced = "SURFACED"
    resolved = "RESOLVED"
    dismissed = "DISMISSED"
    expired = "EXPIRED"


class AttentionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_action: AttentionAction
    reason_code: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=255)
    priority: int = Field(default=50, ge=0, le=100)
    urgency: float = Field(default=0, ge=0, le=1)
    evidence_quality: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=0, ge=0, le=1)
    reversible: bool = True
    requires_canonical_mutation: bool = False
    supported_in_version: bool = True
    active_task_interruption_cost: float = Field(default=0, ge=0, le=1)
    host_authorized_actions: tuple[AttentionAction, ...] = ()
    not_before: datetime | None = None
    expires_at: datetime | None = None
    source_event_id: str | None = Field(default=None, max_length=160)
    source_trace_id: str | None = Field(default=None, max_length=36)
    workspace_id: str | None = Field(default=None, max_length=36)
    open_thread_id: str | None = Field(default=None, max_length=36)
    prospective_thread_id: str | None = Field(default=None, max_length=36)
    question_ref: str | None = Field(default=None, max_length=180)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 32:
            raise ValueError("Attention payloads are limited to 32 fields.")
        return value


class AttentionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: AttentionAction
    reason_code: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=255)
    priority: int = Field(ge=0, le=100)
    urgency: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_quality: float = Field(ge=0, le=1)
    not_before: datetime | None = None
    expires_at: datetime | None = None
    source_event_id: str | None = None
    source_trace_id: str | None = None
    workspace_id: str | None = None
    open_thread_id: str | None = None
    prospective_thread_id: str | None = None
    question_ref: str | None = None
    policy_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CuriosityAction(str, Enum):
    ask_now = "ASK_NOW"
    defer = "DEFER"
    skip = "SKIP"


class CuriosityInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    importance: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    decision_impact: float = Field(ge=0, le=1)
    naturalness: float = Field(ge=0, le=1)
    interruption_cost: float = Field(ge=0, le=1)
    annoyance: float = Field(ge=0, le=1)
    inferability_elsewhere: float = Field(ge=0, le=1)
    explicit_self_report_available: bool = False


class CuriosityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: CuriosityAction
    score: float
    reason_code: str
    policy_version: str
