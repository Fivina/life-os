from __future__ import annotations

import json

from agents import FunctionTool, RunContextWrapper
from agents.agent import ToolsToFinalOutputResult
from fastapi import HTTPException
from pydantic import ValidationError

from app.agents.context import LifeOSAgentContext
from app.ai.types import AIProviderError
from app.assistant.proposals import create_action_proposal
from app.assistant.tools import AssistantToolError, ToolRegistry
from app.skills.models import LoadedSkill


PROPOSAL_MESSAGE = "Review this proposed action before I change Life OS."


class ToolAdapter:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def build(self, skill: LoadedSkill, role: str) -> list[FunctionTool]:
        tools = []
        for name in skill.manifest.allowed_tools:
            tool = self.registry.get(name)
            self.registry.authorize(tool, role)

            async def invoke(context, arguments: str, tool_name=name):
                context.context.record_activity("tool", "started", tool_name)
                try:
                    result = self.invoke(context.context, tool_name, arguments)
                    context.context.record_activity("tool", "awaiting_confirmation" if context.context.proposal else "completed", tool_name)
                    return result
                except AIProviderError as exc:
                    context.context.record_activity("tool", "failed", tool_name)
                    # SDK privacy boundaries may strip custom exception attributes.
                    context.context.host_error = (exc.code, exc.message)
                    raise
                except Exception:
                    context.context.record_activity("tool", "failed", tool_name)
                    raise

            tools.append(FunctionTool(
                name=name,
                description=f"{tool.description} Kind: {tool.kind}. Mutations require host confirmation.",
                params_json_schema=tool.args_schema.model_json_schema(),
                on_invoke_tool=invoke,
                # Preserve optional/default arguments and typed maps in existing domain schemas.
                strict_json_schema=False,
            ))
        return tools

    def invoke(self, context: LifeOSAgentContext, name: str, raw_arguments: str) -> str:
        if name not in context.skill.manifest.allowed_tools:
            raise AIProviderError("unauthorized_tool", "The active skill is not allowed to use that tool.")
        if context.proposal is not None:
            return json.dumps({"status": "awaiting_confirmation", "proposal_id": context.proposal.id})
        context.consume_tool_call()
        try:
            tool = self.registry.get(name)
            self.registry.authorize(tool, context.role)
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise ValueError("Expected an object")
            args = tool.validate_args(arguments)
        except (AssistantToolError, ValidationError, ValueError, TypeError) as exc:
            code = exc.code if isinstance(exc, AssistantToolError) else "invalid_tool_arguments"
            raise AIProviderError(code, "The agent tool request failed host validation.") from None
        # SDK agents require confirmation for every mutation, including conditional ones.
        if tool.kind == "MUTATION":
            context.proposal = create_action_proposal(
                context.db, context.user, role=context.role, tool=tool, args=args,
            )
            return json.dumps({"status": "pending_confirmation", "proposal_id": context.proposal.id,
                               "executed": False})
        try:
            result = self.registry.execute(context.db, context.user, tool, args)
        except (AssistantToolError, HTTPException):
            raise AIProviderError("agent_tool_failed", "The requested information could not be read.") from None
        if result.entity_type and result.entity_id:
            ref = {"type": result.entity_type, "id": result.entity_id}
            if ref not in context.entity_references:
                context.entity_references.append(ref)
        return json.dumps({"message": result.message, "result": result.result}, default=str, ensure_ascii=True)


def stop_at_proposal(context: RunContextWrapper[LifeOSAgentContext], results) -> ToolsToFinalOutputResult:
    return ToolsToFinalOutputResult(
        is_final_output=context.context.proposal is not None,
        final_output=PROPOSAL_MESSAGE if context.context.proposal is not None else None,
    )
