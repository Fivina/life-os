from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FeedbackSessionStatus(str, Enum):
    active = "ACTIVE"
    completed = "COMPLETED"
    cancelled = "CANCELLED"
    expired = "EXPIRED"


class FeedbackDimension(str, Enum):
    timing = "TIMING"
    content_usefulness = "CONTENT_USEFULNESS"
    context_selection = "CONTEXT_SELECTION"
    frequency = "FREQUENCY"
    tone = "TONE"
    priority = "PRIORITY"
    question_usefulness = "QUESTION_USEFULNESS"
    plan_realism = "PLAN_REALISM"
    memory_correctness = "MEMORY_CORRECTNESS"
    action_correctness = "ACTION_CORRECTNESS"
    factual_accuracy = "FACTUAL_ACCURACY"
    ui_state_mismatch = "UI_STATE_MISMATCH"
    voice_transcription = "VOICE_TRANSCRIPTION"
    latency = "LATENCY"


class FeedbackScope(str, Enum):
    exact_case = "EXACT_CASE"
    situation_type = "SITUATION_TYPE"
    workspace = "WORKSPACE"
    context_combination = "CONTEXT_COMBINATION"
    general_preference = "GENERAL_PREFERENCE"
    permanent_explicit_rule = "PERMANENT_EXPLICIT_RULE"


class FeedbackConfidence(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


class FeedbackLabelSource(str, Enum):
    explicit_log_feedback = "EXPLICIT_LOG_FEEDBACK"
    explicit_correction = "EXPLICIT_CORRECTION"
    proposal_outcome = "PROPOSAL_OUTCOME"
    downstream_outcome = "DOWNSTREAM_OUTCOME"
    repeated_behavior = "REPEATED_BEHAVIOR"
    model_disagreement = "MODEL_DISAGREEMENT"
    generated_counterexample = "GENERATED_COUNTEREXAMPLE"


class FeedbackLabelStrength(str, Enum):
    strong = "STRONG"
    medium = "MEDIUM"
    weak = "WEAK"


class ReservedFeedbackCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    matched: bool
    canonical_command: str | None = None
    inline_explanation: str | None = Field(default=None, max_length=1000)


class FeedbackQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str = Field(min_length=3, max_length=160)
    question_version: int = Field(ge=1)
    dimension: FeedbackDimension
    prompt: str = Field(min_length=1, max_length=300)
    low_label: str = Field(default="Completely wrong", max_length=120)
    high_label: str = Field(default="Exactly right", max_length=120)


class FeedbackClarification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str = "feedback.clarify.content_or_timing"
    question_version: int = 1
    prompt: str = "Was the decision itself wrong, or was the timing/context the main problem?"


class FeedbackResponseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=3, max_length=160)
    question_version: int = Field(ge=1)
    score: int | None = Field(default=None, ge=0, le=5)
    is_skipped: bool = False
    feedback_scope: FeedbackScope = FeedbackScope.exact_case
    feedback_confidence: FeedbackConfidence = FeedbackConfidence.medium
    explanation: str | None = Field(default=None, max_length=1000)
    explicit_scope_statement: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_score_or_skip(self) -> "FeedbackResponseInput":
        if self.is_skipped == (self.score is not None):
            raise ValueError("Provide either a 0-5 score or Skip, never both or neither.")
        return self


class FeedbackStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1, max_length=1200)
    parent_conversation_id: str | None = Field(default=None, max_length=36)
    attention_item_id: str | None = Field(default=None, max_length=36)


class FeedbackClarificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1000)


class FeedbackResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question_id: str
    question_version: int
    dimension: FeedbackDimension
    score: int | None
    is_skipped: bool
    feedback_scope: FeedbackScope
    feedback_confidence: FeedbackConfidence
    explanation: str | None
    created_at: datetime


class FeedbackSessionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_code: str
    session_id: str | None = None
    status: FeedbackSessionStatus | None = None
    parent_conversation_id: str | None = None
    parent_workspace_id: str | None = None
    target_cognitive_trace_id: str | None = None
    current_question_index: int = 0
    questions_planned_count: int = 0
    questions_answered_count: int = 0
    clarification: FeedbackClarification | None = None
    next_question: FeedbackQuestion | None = None
    resume_state: dict = Field(default_factory=dict)


class QualityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    days: int | None = Field(default=None, ge=1, le=3650)
    provider: str | None = Field(default=None, max_length=80)
    model_version: str | None = Field(default=None, max_length=160)
    policy_version: str | None = Field(default=None, max_length=80)
    decision_family: str | None = Field(default=None, max_length=80)


class QualityDimensionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: FeedbackDimension
    response_count: int
    numeric_sample_count: int
    skipped_count: int
    average_score: float | None
    score_distribution: dict[str, int]
    skip_rate: float
    low_score_rate: float | None
    high_score_rate: float | None
    low_sample_warning: bool


class IntelligenceQualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_days: int | None
    session_count: int
    completed_session_count: int
    completion_rate: float
    clarification_rate: float
    average_questions_answered: float
    response_count: int
    numeric_response_count: int
    skipped_response_count: int
    dimensions: tuple[QualityDimensionSummary, ...]
    scope_distribution: dict[str, int]
    workspace_distribution: dict[str, int]
    decision_family_distribution: dict[str, int]
    provider_distribution: dict[str, int]
    model_distribution: dict[str, int]
    policy_distribution: dict[str, int]
    routing_policy_distribution: dict[str, int]
    attention_action_distribution: dict[str, int]
