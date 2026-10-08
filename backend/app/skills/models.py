from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.ai.types import AICapability, CAPABILITY_RANK


class SkillManifest(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=500)
    enabled: bool = True
    assistant_roles: list[str] = Field(default_factory=list)
    default_capability: AICapability = AICapability.fast
    max_capability: AICapability = AICapability.reasoning
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_agents: list[str] = Field(default_factory=list, max_length=5)
    read_scopes: list[str] = Field(default_factory=list)
    write_scopes: list[str] = Field(default_factory=list)
    memory_scopes: list[str] = Field(default_factory=list)
    max_tool_calls: int = Field(default=1, ge=0, le=8)
    max_iterations: int = Field(default=1, ge=1, le=6)
    confirmation_policy: Literal["registry", "always"] = "registry"
    cost_class: Literal["low", "medium", "high"] = "low"
    output_contract: str = "assistant_intent_v1"

    @model_validator(mode="after")
    def validate_capabilities(self) -> "SkillManifest":
        if CAPABILITY_RANK[self.default_capability] > CAPABILITY_RANK[self.max_capability]:
            raise ValueError("default_capability cannot exceed max_capability")
        if len(self.allowed_tools) != len(set(self.allowed_tools)):
            raise ValueError("allowed_tools must not contain duplicates")
        if len(self.allowed_agents) != len(set(self.allowed_agents)):
            raise ValueError("allowed_agents must not contain duplicates")
        if self.allowed_agents and (self.name != "self-core" or self.assistant_roles != ["GENERAL_ASSISTANT"]):
            raise ValueError("Only Self Core may delegate to specialist agents")
        return self


class LoadedSkill(BaseModel):
    manifest: SkillManifest
    instructions: str
    source_directory: str
