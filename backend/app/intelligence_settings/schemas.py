from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ProactivityMode(str, Enum):
    quiet = "QUIET"
    balanced = "BALANCED"
    proactive = "PROACTIVE"


class IntelligenceSettingsUpdate(BaseModel):
    proactivity_mode: ProactivityMode | None = None
    memory_visible: bool | None = None
    patterns_visible: bool | None = None
    passive_suggestions_enabled: bool | None = None
    questions_enabled: bool | None = None
    interruptions_enabled: bool | None = None
    prospective_resurfacing_enabled: bool | None = None
    opportunity_suggestions_enabled: bool | None = None
    monthly_ai_budget_eur: float | None = Field(default=None, ge=0, le=100000)
    disabled_skills: list[str] | None = Field(default=None, max_length=100)
    expected_version: int | None = Field(default=None, ge=1)


class AgentModelPreference(BaseModel):
    provider: Literal["openai", "gemini"]
    economy_model: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")
    fast_model: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")
    reasoning_model: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")


class AgentModelSettingsUpdate(BaseModel):
    agents: dict[str, AgentModelPreference] = Field(min_length=1, max_length=25)
    expected_version: int | None = Field(default=None, ge=1)


class ProviderCredentialWrite(BaseModel):
    api_key: SecretStr = Field(min_length=20, max_length=512)


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=60)
    standing_instructions: str = Field(default="", max_length=1200)
    response_style: Literal["concise", "balanced", "detailed"] = "balanced"
    continuity_enabled: bool = True
    decision_routing_enabled: bool = False

    @field_validator("display_name", "standing_instructions")
    @classmethod
    def clean_text(cls, value: str, info) -> str:
        value = value.strip()
        if info.field_name == "display_name" and (not value or any(char.isspace() and char != " " for char in value)):
            raise ValueError("Use a nonempty single-line display name.")
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Control characters are not allowed.")
        if any(marker in value for marker in ("sk-proj-", "sk-svcacct-", "AIza", "apikey_")):
            raise ValueError("Save provider secrets in the credential controls, not agent profiles.")
        return value


class AgentProfileUpdate(AgentProfile):
    expected_version: int | None = Field(default=None, ge=1)


class ProviderCredentialWriteResult(BaseModel):
    provider: Literal["openai", "gemini", "jev"]
    configured: bool


class ProviderModelsRead(BaseModel):
    provider: Literal["openai", "gemini"]
    models: list[str]


class OpenAIChatTestRead(BaseModel):
    provider: Literal["openai"] = "openai"
    model: str
    connected: bool
    passed: bool
    response: str
    latency_ms: int = Field(ge=0)


class JevDecisionTestRead(BaseModel):
    provider: Literal["jev"] = "jev"
    model: str
    connected: bool
    passed: bool
    selected_answer: bool
    true_probability: float = Field(ge=0, le=1)
    trace_id: str | None = None
    latency_ms: int = Field(ge=0)


class EmbeddingSettingsUpdate(BaseModel):
    provider: Literal["default", "openai", "gemini"]
    model: str | None = Field(default=None, min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")
    expected_version: int | None = Field(default=None, ge=1)


class EmbeddingSettingsRead(BaseModel):
    provider: Literal["default", "openai", "gemini"]
    model: str
    effective_provider: str
    dimensions: int
    credential_configured: bool
    version: int


class EmbeddingConnectionTestRequest(BaseModel):
    provider: Literal["openai", "gemini"]
    model: str | None = Field(default=None, min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:/-]+$")


class EmbeddingConnectionTestRead(BaseModel):
    provider: Literal["openai", "gemini"]
    model: str
    dimensions: int
    connected: bool


class AgentSettingsRead(BaseModel):
    skill_name: str
    name: str
    description: str
    roles: list[str]
    provider: Literal["openai", "gemini"]
    economy_model: str
    fast_model: str
    reasoning_model: str
    memory_scopes: list[str]
    memory_domain: str
    memory_count: int
    credential_configured: bool
    profile: AgentProfile


class IntelligenceSettingsRead(BaseModel):
    schema_version: str
    proactivity_mode: ProactivityMode
    memory_visible: bool
    patterns_visible: bool
    passive_suggestions_enabled: bool
    questions_enabled: bool
    interruptions_enabled: bool
    prospective_resurfacing_enabled: bool
    opportunity_suggestions_enabled: bool
    monthly_ai_budget_eur: float | None
    disabled_skills: list[str]
    version: int


class IntelligenceControlSurface(BaseModel):
    settings: IntelligenceSettingsRead
    memory: dict[str, Any]
    patterns: dict[str, Any]
    conversations: dict[str, Any]
    skills: list[dict[str, Any]]
    providers: list[dict[str, Any]]
    agents: list[AgentSettingsRead]
    active_agent_runtime: Literal["legacy", "sdk"]
    live_agents_enabled: bool
    credential_management_available: bool
    usage: dict[str, Any]
    privacy: dict[str, Any]

