from __future__ import annotations

from agents import Agent, FunctionTool, Model, ModelSettings

from app.agents.context import LifeOSAgentContext
from app.agents.tools import ToolAdapter, stop_at_proposal
from app.assistant.context_builder import ContextBundle
from app.assistant.schemas import AssistantRole
from app.skills.registry import SkillRegistry


class AgentFactory:
    def __init__(self, skills: SkillRegistry, tools: ToolAdapter):
        self.skills = skills
        self.tools = tools

    def build(
        self, role: AssistantRole, bundle: ContextBundle, model: Model,
        *, agent_tools: list[FunctionTool] | None = None,
    ) -> Agent[LifeOSAgentContext]:
        skill = self.skills.for_role(role)
        return Agent(
            name=skill.manifest.name,
            instructions=bundle.system_instruction(),
            model=model,
            tools=[*self.tools.build(skill, role), *(agent_tools or [])],
            model_settings=ModelSettings(parallel_tool_calls=False, store=False),
            tool_use_behavior=stop_at_proposal,
        )
