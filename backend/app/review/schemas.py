from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewType(str, Enum):
    quick_capture = "QUICK_CAPTURE"
    receipt_item = "RECEIPT_ITEM"
    memory_candidate = "MEMORY_CANDIDATE"
    finance_classification = "FINANCE_CLASSIFICATION"
    canonical_correction = "CANONICAL_CORRECTION"
    other_uncertainty = "OTHER_EXISTING_UNCERTAINTY"


class ReviewStatus(str, Enum):
    pending = "PENDING"
    resolved = "RESOLVED"
    dismissed = "DISMISSED"
    expired = "EXPIRED"
    superseded = "SUPERSEDED"


class ReviewAction(str, Enum):
    accept = "ACCEPT"
    edit_and_accept = "EDIT_AND_ACCEPT"
    reject = "REJECT"
    dismiss = "DISMISS"


class ReviewCreate(BaseModel):
    review_type: ReviewType
    priority: int = Field(default=50, ge=0, le=100)
    source: str = Field(min_length=1, max_length=60)
    source_ref: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=1000)
    candidate_values: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)
    ambiguity_reasons: list[str] = Field(default_factory=list, max_length=12)
    affected_domain: str = Field(min_length=1, max_length=60)
    target_entity_type: str | None = Field(default=None, max_length=80)
    target_entity_id: str | None = None
    expires_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=120)
    expected_world_revision: int | None = Field(default=None, ge=0)
    expected_target_version: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewResolve(BaseModel):
    action: ReviewAction
    edited_values: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=1)


class ReviewItemRead(BaseModel):
    id: str
    review_type: ReviewType
    status: ReviewStatus
    priority: int
    source: str
    source_ref: str
    summary: str
    question: str
    candidate_values: dict[str, Any]
    evidence: dict[str, Any]
    confidence: float
    ambiguity_reasons: list[str]
    affected_domain: str
    target_entity_type: str | None
    target_entity_id: str | None
    resolution: dict[str, Any]
    expires_at: datetime | None
    correlation_id: str | None
    expected_world_revision: int | None
    expected_target_version: int | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    version: int


class ReviewResolutionRead(BaseModel):
    item: ReviewItemRead
    canonical_entity_type: str | None = None
    canonical_entity_id: str | None = None
    world_revision: int

