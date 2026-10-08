from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal[
    "preference",
    "personal_fact",
    "routine_preference",
    "constraint_preference",
    "interaction_preference",
    "domain_preference",
]
MemoryStatus = Literal["candidate", "active", "uncertain", "contradicted", "archived", "forgotten"]


class MemoryCandidate(BaseModel):
    memory_type: MemoryType = "preference"
    domain: str = Field(default="general", min_length=1, max_length=60)
    content: str = Field(min_length=2, max_length=1200)
    normalized_key: str = Field(min_length=1, max_length=255)
    polarity: int = Field(default=0, ge=-1, le=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    explicit: bool = False


class MemoryExtraction(BaseModel):
    candidates: list[MemoryCandidate] = Field(default_factory=list, max_length=5)


class MemoryCreate(BaseModel):
    content: str = Field(min_length=2, max_length=1200)
    memory_type: MemoryType = "preference"
    domain: str = Field(default="general", min_length=1, max_length=60)
    polarity: int = Field(default=0, ge=-1, le=1)
    importance: float = Field(default=0.65, ge=0, le=1)
    pinned: bool = False


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=2, max_length=1200)
    memory_type: MemoryType | None = None
    domain: str | None = Field(default=None, min_length=1, max_length=60)
    polarity: int | None = Field(default=None, ge=-1, le=1)
    importance: float | None = Field(default=None, ge=0, le=1)
    expected_version: int | None = Field(default=None, ge=1)


class MemoryEvidenceRead(BaseModel):
    id: str
    source_type: str
    source_id: str | None
    evidence_kind: str
    direction: str
    weight: float
    observed_at: datetime
    excerpt: str | None
    metadata_json: dict[str, Any]

    model_config = {"from_attributes": True}


class MemoryRead(BaseModel):
    id: str
    memory_type: str
    domain: str
    content: str
    normalized_key: str
    polarity: int
    confidence: float
    effective_confidence: float
    importance: float
    status: str
    pinned: bool
    user_confirmed: bool
    source_kind: str
    first_observed_at: datetime
    last_observed_at: datetime
    last_confirmed_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    supersedes_memory_id: str | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimension: int | None
    embedding_version: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    evidence_count: int = 0


class MemoryDetail(MemoryRead):
    evidence: list[MemoryEvidenceRead] = Field(default_factory=list)


class MemorySearchResult(BaseModel):
    memory: MemoryRead
    score: float
    components: dict[str, float]


class EpisodeRead(BaseModel):
    id: str
    domain: str | None
    title: str
    summary: str
    start_at: datetime
    end_at: datetime
    importance: float
    confidence: float
    status: str
    related_entities_json: list[Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class EpisodeSearchResult(BaseModel):
    episode: EpisodeRead
    score: float


class RecommendationOptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=220)
    rank: int = Field(ge=1)
    score: float | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    reference_type: str | None = Field(default=None, max_length=80)
    reference_id: str | None = Field(default=None, max_length=36)


class RecommendationCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=60)
    kind: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=220)
    reason: str | None = Field(default=None, max_length=2000)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    options: list[RecommendationOptionCreate] = Field(default_factory=list, max_length=20)
    idempotency_key: str | None = Field(default=None, max_length=120)


class RecommendationOptionRead(BaseModel):
    id: str
    label: str
    rank: int
    score: float | None
    payload_json: dict[str, Any]
    reference_type: str | None
    reference_id: str | None

    model_config = {"from_attributes": True}


class RecommendationRead(BaseModel):
    id: str
    domain: str
    kind: str
    title: str
    reason: str | None
    context_snapshot: dict[str, Any]
    status: str
    created_at: datetime
    options: list[RecommendationOptionRead] = Field(default_factory=list)


class RecommendationOutcomeCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=60)
    recommendation_type: str = Field(min_length=1, max_length=80)
    recommendation_summary: str = Field(min_length=2, max_length=1200)
    outcome: Literal["shown", "opened", "accepted", "rejected", "modified", "completed", "abandoned"]
    accepted: bool | None = None
    source_entity_type: str | None = Field(default=None, max_length=80)
    source_entity_id: str | None = Field(default=None, max_length=36)
    recommendation_id: str | None = Field(default=None, max_length=36)
    option_id: str | None = Field(default=None, max_length=36)
    feedback_text: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RecommendationOutcomeRead(BaseModel):
    id: str
    domain: str
    recommendation_type: str
    recommendation_summary: str
    outcome: str
    accepted: bool | None
    observed_at: datetime
    source_entity_type: str | None
    source_entity_id: str | None
    recommendation_id: str | None
    option_id: str | None
    feedback_text: str | None
    metadata_json: dict[str, Any]

    model_config = {"from_attributes": True}


class ConsolidationRead(BaseModel):
    id: str
    period_start: datetime
    period_end: datetime
    status: str
    source_event_count: int
    episode_count: int
    memory_count: int
    error: str | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class MemoryProcessingJobRead(BaseModel):
    id: str
    job_type: str
    source_type: str
    source_id: str
    status: str
    attempts: int
    available_at: datetime
    processed_at: datetime | None
    last_error: str | None

    model_config = {"from_attributes": True}


class MemoryDiagnosticsRead(BaseModel):
    active_memories: int
    candidate_memories: int
    contradicted_memories: int
    forgotten_memories: int
    evidence_records: int
    episodes: int
    pending_jobs: int
    failed_jobs: int
    retrieval_count: int
    average_retrieval_ms: float
    degraded_retrievals: int
    embedding_calls: int
    curator_calls: int
    estimated_ai_cost: float


class LearningBridgeRead(BaseModel):
    id: str
    period_start: datetime
    period_end: datetime
    status: str
    memory_change_count: int
    pattern_change_count: int
    recommendation_outcome_count: int
    snapshot_json: dict[str, Any]

    model_config = {"from_attributes": True}
