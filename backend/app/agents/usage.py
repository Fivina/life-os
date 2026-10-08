from __future__ import annotations

from agents import RunHooks
from agents.usage import Usage

from app.agents.context import LifeOSAgentContext
from app.ai.types import AIUsageMetadata


class AgentUsageHooks(RunHooks[LifeOSAgentContext]):
    """Retain counters after each model response, including before a later failed turn."""

    def __init__(self):
        self.usage = Usage()

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        context.context.consume_model_turn()
        context.context.record_activity("model", "started")

    async def on_llm_end(self, context, agent, response) -> None:
        self.usage.add(response.usage)
        context.context.record_activity("model", "completed")

    def metadata(self) -> AIUsageMetadata:
        return AIUsageMetadata(
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
            cached_tokens=self.usage.input_tokens_details.cached_tokens,
            total_tokens=self.usage.total_tokens,
        )
