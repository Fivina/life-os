from contextvars import ContextVar
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentWorkActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    kind: Literal["model", "tool", "delegation", "routing"]
    skill_name: str = Field(max_length=80)
    tool_name: str | None = Field(default=None, max_length=120)
    status: Literal["started", "completed", "failed", "awaiting_confirmation"]


activity_sink: ContextVar[Callable[[AgentWorkActivity], None] | None] = ContextVar("agent_activity_sink", default=None)
