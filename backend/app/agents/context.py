from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai.types import AIProviderError
from app.agents.activity import AgentWorkActivity, activity_sink
from app.assistant.schemas import AssistantRole
from app.database.models import AssistantActionProposal, UserProfile
from app.skills.models import LoadedSkill


@dataclass
class AgentRunBudget:
    """One hard execution budget shared by the manager and its specialist calls."""

    tool_limit: int = 6
    turn_limit: int = 6
    tool_calls: int = 0
    model_turns: int = 0
    work_log: list[AgentWorkActivity] = field(default_factory=list)


@dataclass
class LifeOSAgentContext:
    """Local host dependencies; never serialized into model input."""

    db: Session = field(repr=False)
    user: UserProfile = field(repr=False)
    role: AssistantRole
    request_id: str
    skill: LoadedSkill = field(repr=False)
    tool_limit: int
    tool_call_count: int = 0
    proposal: AssistantActionProposal | None = field(default=None, repr=False)
    entity_references: list[dict[str, str]] = field(default_factory=list)
    host_error: tuple[str, str] | None = None
    budget: AgentRunBudget = field(default_factory=AgentRunBudget)
    parent_request_id: str | None = None

    def record_activity(self, kind: str, status: str, tool_name: str | None = None) -> None:
        if len(self.budget.work_log) >= 64:
            return
        event = AgentWorkActivity(sequence=len(self.budget.work_log) + 1, kind=kind,
                                  skill_name=self.skill.manifest.name, tool_name=tool_name, status=status)
        self.budget.work_log.append(event)
        sink = activity_sink.get()
        if sink is not None:
            sink(event)

    def consume_tool_call(self) -> None:
        if self.tool_call_count >= min(self.tool_limit, 6) or self.budget.tool_calls >= self.budget.tool_limit:
            self.fail("agent_tool_limit", "The agent reached its tool-call limit.")
        self.tool_call_count += 1
        self.budget.tool_calls += 1

    def consume_model_turn(self) -> None:
        if self.budget.model_turns >= self.budget.turn_limit:
            self.fail("agent_turn_limit", "The agent reached its shared turn limit. Please narrow the request.")
        self.budget.model_turns += 1

    def fail(self, code: str, message: str) -> None:
        self.host_error = (code, message)
        raise AIProviderError(code, message)
