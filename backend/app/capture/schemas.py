from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CaptureDomain(str, Enum):
    learning = "LEARNING"
    finance = "FINANCE"
    kitchen = "KITCHEN"
    home = "HOME"
    calendar = "CALENDAR"
    life = "LIFE"
    unknown = "UNKNOWN"


class CaptureIntentType(str, Enum):
    update_exam_date = "UPDATE_EXAM_DATE"
    create_transaction = "CREATE_TRANSACTION"
    create_shopping_need = "CREATE_SHOPPING_NEED"
    create_commitment = "CREATE_COMMITMENT"
    unknown = "UNKNOWN"


class ConsequenceLevel(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


class CapturePolicyOutcome(str, Enum):
    apply = "APPLY"
    request_confirmation = "REQUEST_CONFIRMATION"
    send_to_review = "SEND_TO_REVIEW"
    reject_invalid = "REJECT_INVALID"
    noop_duplicate = "NOOP_DUPLICATE"


class CaptureStatus(str, Enum):
    proposed = "PROPOSED"
    pending_review = "PENDING_REVIEW"
    applied = "APPLIED"
    rejected = "REJECTED"
    invalid = "INVALID"
    duplicate = "DUPLICATE"
    superseded = "SUPERSEDED"


class CapturedIntent(BaseModel):
    interpreted_domain: CaptureDomain
    intent_type: CaptureIntentType
    target_entity_type: str | None = None
    target_entity_id: str | None = None
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)
    ambiguity_flags: list[str] = Field(default_factory=list, max_length=12)
    consequence_level: ConsequenceLevel
    confirmation_required: bool = False
    reason_codes: list[str] = Field(default_factory=list, max_length=12)
    interpreter_provider: str = "deterministic"
    interpreter_model: str | None = None


class QuickCaptureCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_thread_id: str | None = None
    source_message_id: str | None = None
    workspace_id: str | None = None
    now: datetime | None = None
    timezone: str = Field(default="Europe/Berlin", min_length=1, max_length=80)


class QuickCaptureApply(BaseModel):
    edited_payload: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=1)


class QuickCaptureRead(BaseModel):
    id: str
    schema_version: str
    raw_text: str
    status: CaptureStatus
    interpreted_domain: CaptureDomain
    intent_type: CaptureIntentType
    target_entity_type: str | None
    target_entity_id: str | None
    structured_payload: dict[str, Any]
    confidence: float
    ambiguity_flags: list[str]
    consequence_level: ConsequenceLevel
    confirmation_required: bool
    review_required: bool
    policy_outcome: CapturePolicyOutcome
    reason_codes: list[str]
    interpreter_provider: str
    interpreter_model: str | None
    review_item_id: str | None
    canonical_entity_type: str | None
    canonical_entity_id: str | None
    expected_world_revision: int
    created_at: datetime
    applied_at: datetime | None
    version: int

