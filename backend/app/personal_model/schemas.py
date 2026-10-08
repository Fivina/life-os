from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FEATURE_SCHEMA_VERSION = "personal-features-v1"
EXTRACTION_VERSION = "personal-extractor-v1"

ModelType = Literal["capacity", "completion", "activation", "preference", "routine", "state_transition"]
ModelStatus = Literal["CANDIDATE", "ACTIVE", "REJECTED", "RETIRED"]
PatternStatus = Literal["ACTIVE", "DOWNWEIGHTED", "INVALIDATED"]


class TrainingExampleRead(BaseModel):
    id: str
    feature_schema_version: str
    extraction_version: str
    decision_at: datetime
    plan_id: str | None
    plan_block_id: str | None
    source_action_id: str | None
    domain: str | None
    label_source: str
    feature_json: dict[str, Any]
    label_json: dict[str, Any]
    provenance_json: dict[str, Any]
    status: str
    version: int

    model_config = {"from_attributes": True}


class PersonalModelVersionRead(BaseModel):
    id: str
    model_type: str
    model_stage: str
    version: int
    feature_schema_version: str
    status: str
    parameters: dict[str, Any]
    evidence_start: datetime | None
    evidence_end: datetime | None
    evidence_n: int
    effective_evidence_n: float
    confidence: float
    metrics: dict[str, Any]
    baseline_metrics: dict[str, Any]
    promotion_reason: str | None
    promoted_at: datetime | None
    supersedes_model_version_id: str | None
    refresh_run_id: str | None

    model_config = {"from_attributes": True}


class PatternEvidenceRead(BaseModel):
    id: str
    pattern_type: str
    scope: dict[str, Any]
    claim: str
    evidence_n: int
    weighted_support: float
    confidence: float
    first_observed: datetime | None
    last_observed: datetime | None
    last_updated: datetime
    status: str
    correction_metadata: dict[str, Any]
    source_model_version_id: str | None
    version: int

    model_config = {"from_attributes": True}


class PatternCorrectionRequest(BaseModel):
    reason: str = Field(default="user_says_wrong", max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class PersonalModelRefreshRead(BaseModel):
    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    feature_schema_version: str
    extraction_version: str
    evidence_n: int
    metrics_json: dict[str, Any]
    error: str | None
    version: int

    model_config = {"from_attributes": True}


class PersonalModelSnapshotRead(BaseModel):
    status: str
    feature_schema_version: str
    model_revision: int
    active_model_ids: dict[str, str]
    model_versions: dict[str, int]
    parameters: dict[str, Any]
    confidence: dict[str, float]
    evidence_counts: dict[str, int]
    fallback_reasons: dict[str, str]


class PersonalModelSummaryRead(BaseModel):
    feature_schema_version: str
    extraction_version: str
    status: str
    evidence_n: int
    active_model_count: int
    candidate_model_count: int
    rejected_model_count: int
    pattern_count: int
    corrected_pattern_count: int
    fallback_rate: float
    latest_refresh: PersonalModelRefreshRead | None
    snapshot: PersonalModelSnapshotRead
    metrics: dict[str, Any]


class PersonalModelInfluence(BaseModel):
    factor: str
    contribution: float
    notes: str
    model_id: str | None = None
    confidence: float = 0
