from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field
from app.agents.activity import AgentWorkActivity


AssistantRole = Literal["GENERAL_ASSISTANT", "FITNESS_COACH", "LEARNING_COACH", "HOME_MANAGER", "CHEF", "FINANCE_ADVISOR"]


class AssistantIntentType(str, Enum):
    query = "QUERY"
    explain = "EXPLAIN"
    command = "COMMAND"
    discussion = "DISCUSSION"
    clarification_required = "CLARIFICATION_REQUIRED"


class AssistantDomain(str, Enum):
    general = "general"
    state = "state"
    planning = "planning"
    fitness = "fitness"
    learning = "learning"
    kitchen = "kitchen"
    home = "home"
    goals = "goals"
    finance = "finance"


class AssistantResponseType(str, Enum):
    information = "INFORMATION"
    proposal = "PROPOSAL"
    clarification = "CLARIFICATION"
    mutation_result = "MUTATION_RESULT"
    no_action = "NO_ACTION"
    error = "ERROR"
    feedback = "FEEDBACK"


class ModelTier(str, Enum):
    no_ai = "NO_AI"
    standard = "STANDARD"
    strong = "STRONG"


class AssistantMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    role: AssistantRole = "GENERAL_ASSISTANT"
    thread_id: str | None = None
    now: datetime | None = None
    timezone: str = "Europe/Berlin"
    recent_messages: list[dict[str, str]] = Field(default_factory=list, max_length=8)


class AssistantIntent(BaseModel):
    type: AssistantIntentType
    domain: AssistantDomain = AssistantDomain.general
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    user_facing_summary: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    model_tier: ModelTier = ModelTier.standard


class AssistantActionProposalRead(BaseModel):
    id: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    consequence_category: str
    expected_world_revision: int | None
    status: str
    expires_at: datetime
    confirmation_required: bool
    version: int
    thread_id: str | None = None


class AssistantMutationResult(BaseModel):
    tool_name: str
    entity_type: str | None = None
    entity_id: str | None = None
    world_revision: int | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class AssistantExplanation(BaseModel):
    title: str | None = None
    factors: list[dict[str, Any]] = Field(default_factory=list)
    summary: str


class AssistantResponse(BaseModel):
    message: str
    work_log: list[AgentWorkActivity] = Field(default_factory=list, max_length=64)
    role_used: AssistantRole
    response_type: AssistantResponseType
    proposed_action: AssistantActionProposalRead | None = None
    mutation_result: AssistantMutationResult | None = None
    explanation: AssistantExplanation | None = None
    entity_references: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str
    provider: str | None = None
    model: str | None = None
    model_tier: ModelTier = ModelTier.no_ai
    capability: str | None = None
    skill_name: str | None = None
    skill_version: str | None = None
    thread_id: str | None = None
    assistant_message_id: str | None = None
    cognitive_trace_ref: str | None = None
    orchestration_route: str | None = None
    error_code: str | None = None
    feedback_session_id: str | None = None
    feedback_status: str | None = None
    feedback_question: dict[str, Any] | None = None
