from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.decision.schemas import DecisionOutputType


class ProviderRole(str, Enum):
    primary = "PRIMARY"
    fallback = "FALLBACK"
    shadow = "SHADOW"


class ProviderStatus(str, Enum):
    completed = "COMPLETED"
    failed = "FAILED"
    unsupported = "UNSUPPORTED"
    skipped = "SKIPPED"


class RoutingMode(str, Enum):
    fake = "FAKE"
    laya_only = "LAYA_ONLY"
    jev_only = "JEV_ONLY"
    auto = "AUTO"
    shadow = "SHADOW"


class RoutingReason(str, Enum):
    primary_for_task_family = "PRIMARY_FOR_TASK_FAMILY"
    provider_disabled = "PROVIDER_DISABLED"
    unsupported_question = "UNSUPPORTED_QUESTION"
    low_primary_confidence = "LOW_PRIMARY_CONFIDENCE"
    primary_error = "PRIMARY_ERROR"
    shadow_only = "SHADOW_ONLY"
    high_cardinality = "HIGH_CARDINALITY"
    benchmark_profile = "BENCHMARK_PROFILE"
    manual_test_override = "MANUAL_TEST_OVERRIDE"
    legacy_provider_setting = "LEGACY_PROVIDER_SETTING"


class DisagreementType(str, Enum):
    same_answer = "SAME_ANSWER"
    different_answer = "DIFFERENT_ANSWER"
    confidence_gap = "CONFIDENCE_GAP"
    primary_uncertain_secondary_confident = "PRIMARY_UNCERTAIN_SECONDARY_CONFIDENT"
    primary_confident_secondary_uncertain = "PRIMARY_CONFIDENT_SECONDARY_UNCERTAIN"
    provider_error = "PROVIDER_ERROR"
    unsupported_by_provider = "UNSUPPORTED_BY_PROVIDER"


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    provider_version: str
    model_version: str | None = None
    enabled: bool
    available: bool
    supported_output_types: tuple[DecisionOutputType, ...]
    supported_families: tuple[str, ...] = ()
    max_choices: int = Field(default=16, ge=2)
    max_questions_per_request: int = Field(default=1, ge=1)
    max_context_bytes: int = Field(default=16_384, ge=1024)
    supported_languages: tuple[str, ...] = ("en",)
    external: bool = False
    metadata: dict = Field(default_factory=dict)


class ProviderSupport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    supported: bool
    reason_code: str


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    enabled: bool
    available: bool
    loaded: bool
    provider_version: str
    model_version: str | None = None
    last_error: str | None = None
    last_success_at: datetime | None = None
    runtime_metadata: dict = Field(default_factory=dict)


class ProviderRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_provider: str
    fallback_provider: str | None = None
    shadow_provider: str | None = None
    reason_code: RoutingReason
    policy_version: str
    minimum_confidence: float | None = Field(default=None, ge=0, le=1)


class ProviderCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model_version: str | None = None
    role: ProviderRole
    routing_reason: str
    status: ProviderStatus
    latency_ms: int = Field(ge=0)
    input_units: int = Field(default=0, ge=0)
    output_units: int = Field(default=0, ge=0)
    estimated_cost_eur: float | None = Field(default=None, ge=0)
    request_id: str | None = None
    error_code: str | None = None
    metadata: dict = Field(default_factory=dict)
