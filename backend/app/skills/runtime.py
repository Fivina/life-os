from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest, CAPABILITY_RANK
from app.assistant.context_builder import ContextBuilderV1, ContextBundle
from app.assistant.schemas import (
    AssistantDomain,
    AssistantIntent,
    AssistantIntentType,
    AssistantMessageRequest,
    ModelTier,
)
from app.assistant.tools import AssistantToolError, ToolRegistry
from app.database.models import ConversationThread, UserProfile
from app.skills.models import LoadedSkill
from app.skills.registry import SkillRegistry


@dataclass(frozen=True)
class SkillRuntimeResult:
    intent: AssistantIntent
    provider: str
    model: str
    capability: AICapability
    skill: LoadedSkill
    context: ContextBundle


class SkillRuntime:
    def __init__(
        self,
        skills: SkillRegistry,
        tools: ToolRegistry,
        context: ContextBuilderV1,
        gateway: AIGateway,
    ) -> None:
        self.skills = skills
        self.tools = tools
        self.context = context
        self.gateway = gateway

    def interpret(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        request: AssistantMessageRequest,
        thread: ConversationThread,
        preferred_tier: ModelTier,
    ) -> SkillRuntimeResult:
        skill = self.skills.for_role(request.role)
        capability = self._capability(skill, preferred_tier)
        context = self.context.build(
            db,
            user,
            role=request.role,
            skill=skill,
            thread=thread,
            user_request=request.message,
            now=request.now,
            timezone=request.timezone,
            client_recent_messages=request.recent_messages,
            request_id=request_id,
        )
        response = self.gateway.complete(
            db,
            user,
            request_id=request_id,
            assistant_role=request.role,
            skill_name=skill.manifest.name,
            skill_version=skill.manifest.version,
            capability=capability,
            conversation_thread_id=thread.id,
            request=AIRequest(
                system_instruction=context.system_instruction(),
                messages=context.messages,
                tools=context.tools,
                response_schema=AssistantIntent.model_json_schema(),
                cache_key=context.cache_key,
                metadata={
                    "assistant_role": request.role,
                    "context": context.dynamic_context.get("canonical", {}),
                    "now": request.now.isoformat() if request.now else None,
                    "timezone": request.timezone,
                },
            ),
        )
        intent = self._intent_from_response(response.text, response.tool_calls, skill)
        self._enforce_intent(skill, request.role, intent)
        return SkillRuntimeResult(
            intent=intent,
            provider=response.provider,
            model=response.model,
            capability=capability,
            skill=skill,
            context=context,
        )

    def _capability(self, skill: LoadedSkill, tier: ModelTier) -> AICapability:
        requested = AICapability.reasoning if tier == ModelTier.strong else skill.manifest.default_capability
        if CAPABILITY_RANK[requested] > CAPABILITY_RANK[skill.manifest.max_capability]:
            raise AIProviderError("skill_capability_rejected", "This skill is not allowed to use the requested AI capability.")
        return requested

    def finalize_tool_result(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        request: AssistantMessageRequest,
        runtime_result: SkillRuntimeResult,
        tool_name: str,
        tool_result: dict,
        tool_message: str,
    ) -> str:
        if runtime_result.skill.manifest.max_iterations < 2:
            return tool_message
        payload = json.dumps(
            {"tool": tool_name, "canonical_result": tool_result},
            ensure_ascii=True,
            separators=(",", ":"),
            default=str,
        )
        response = self.gateway.complete(
            db,
            user,
            request_id=request_id,
            assistant_role=request.role,
            skill_name=runtime_result.skill.manifest.name,
            skill_version=runtime_result.skill.manifest.version,
            capability=runtime_result.capability,
            conversation_thread_id=runtime_result.context.dynamic_context["conversation"]["thread_id"],
            request=AIRequest(
                system_instruction=(
                    runtime_result.context.system_instruction()
                    + "\n\n# Finalization\nAnswer the user's request using only the supplied canonical tool result. "
                    "Do not request another tool and do not claim any additional facts."
                ),
                messages=[
                    *runtime_result.context.messages,
                    AIMessage(role="user", content=f"Canonical tool result:\n{payload}"),
                ],
                cache_key=runtime_result.context.cache_key,
                metadata={
                    "mode": "finalize_tool_result",
                    "tool_result_message": tool_message,
                    "assistant_role": request.role,
                    "timezone": request.timezone,
                },
            ),
        )
        if response.tool_calls or not response.text:
            raise AIProviderError("invalid_final_response", "The AI provider did not return a safe final response.")
        return response.text

    def _intent_from_response(self, text: str | None, calls, skill: LoadedSkill) -> AssistantIntent:
        if len(calls) > min(1, skill.manifest.max_tool_calls):
            raise AIProviderError("tool_limit_exceeded", "The AI response exceeded the skill tool-call limit.")
        if calls:
            call = calls[0]
            try:
                tool = self.tools.get(call.name)
            except AssistantToolError as exc:
                raise AIProviderError(exc.code, exc.message) from exc
            domain = {
                "fitness-coach": AssistantDomain.fitness,
                "learning-coach": AssistantDomain.learning,
                "chef": AssistantDomain.kitchen,
            }.get(skill.manifest.name, AssistantDomain.general)
            return AssistantIntent(
                type=AssistantIntentType.query if tool.kind == "READ_ONLY" else AssistantIntentType.command,
                domain=domain,
                tool_name=call.name,
                arguments=call.arguments,
                requires_confirmation=tool.confirmation_policy == "always" or skill.manifest.confirmation_policy == "always",
                user_facing_summary=f"Run {call.name}.",
            )
        if not text:
            raise AIProviderError("malformed_structured_output", "The AI provider returned no usable structured output.")
        try:
            return AssistantIntent.model_validate_json(text)
        except ValidationError as exc:
            raise AIProviderError("malformed_structured_output", "The AI provider returned invalid structured output.") from exc

    def _enforce_intent(self, skill: LoadedSkill, role: str, intent: AssistantIntent) -> None:
        if intent.type in {AssistantIntentType.discussion, AssistantIntentType.clarification_required}:
            if intent.tool_name:
                raise AIProviderError("unexpected_tool", "Discussion and clarification intents cannot invoke tools.")
            return
        try:
            tool = self.tools.get(intent.tool_name)
        except AssistantToolError as exc:
            raise AIProviderError(exc.code, exc.message) from exc
        if tool.name not in skill.manifest.allowed_tools:
            raise AIProviderError("unauthorized_tool", "The active skill is not allowed to use that tool.")
        try:
            self.tools.authorize(tool, role)
        except AssistantToolError as exc:
            raise AIProviderError(exc.code, exc.message) from exc
