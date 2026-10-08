from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator, Protocol
from uuid import uuid4

from agents import FunctionTool, Model, Runner, RunConfig, RunContextWrapper
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
from agents.models.openai_responses import OpenAIResponsesModel
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.run_config import ToolExecutionConfig
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import AgentRunBudget, LifeOSAgentContext
from app.agents.factory import AgentFactory
from app.agents.models import AgentModelResolver
from app.agents.profiles import agent_profile
from app.agents.decision_routing import AgentDecisionRouter
from app.agents.tools import PROPOSAL_MESSAGE, ToolAdapter
from app.agents.usage import AgentUsageHooks
from app.ai.types import AIProviderError
from app.ai.usage import AIUsageService
from app.assistant.context_builder import ContextBuilderV2, ContextBundle
from app.assistant.proposals import proposal_read
from app.assistant.schemas import AssistantMessageRequest, AssistantResponse, AssistantResponseType, ModelTier
from app.assistant.tools import ToolRegistry
from app.core.config import Settings
from app.database.models import ConversationThread, UserProfile, UserIntelligenceSettings
from app.intelligence_settings.service import IntelligenceSettingsService
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.skills.registry import SkillRegistry


class AgentRuntime(Protocol):
    def run(
        self, db: Session, user: UserProfile, *, request_id: str, request: AssistantMessageRequest,
        thread: ConversationThread, preferred_tier: ModelTier,
    ) -> AssistantResponse: ...


class SpecialistTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=1, max_length=2000)


class AgentsSDKRuntime:
    def __init__(
        self, settings: Settings, skills: SkillRegistry, tools: ToolRegistry,
        context_builder: ContextBuilderV2, *, model: Model | None = None,
    ):
        self.settings = settings
        self.skills = skills
        self.context_builder = context_builder
        self.resolver = AgentModelResolver(settings)
        self.factory = AgentFactory(skills, ToolAdapter(tools))
        self.usage = AIUsageService(settings)
        # Explicit dependency injection only; never silently replace a production model with a fake.
        self.model = model
        self.models: dict[str, Model] = {}
        self.intelligence_settings = IntelligenceSettingsService(settings)
        self.provider_secrets = ProviderSecretStore()

    def run(
        self, db: Session, user: UserProfile, *, request_id: str, request: AssistantMessageRequest,
        thread: ConversationThread, preferred_tier: ModelTier,
    ) -> AssistantResponse:
        skill = self.skills.for_role(request.role)
        context = LifeOSAgentContext(
            db, user, request.role, request_id, skill, min(6, skill.manifest.max_tool_calls),
            budget=AgentRunBudget(tool_limit=min(6, skill.manifest.max_tool_calls),
                                  turn_limit=self._max_turns(skill)),
        )
        hooks = AgentUsageHooks()
        started = perf_counter()
        selection = None
        error_code = None
        message = "The agent could not complete this request. Please try again."
        try:
            if not self.settings.ai_enabled:
                raise AIProviderError("ai_disabled", "AI is disabled.")
            selection = self.resolver.resolve(
                skill, preferred_tier, db=db, user=user,
                test_model_name=self._test_model_name(skill.manifest.name),
            )
            bundle = self.context_builder.build(
                db, user, role=request.role, skill=skill, thread=thread, user_request=request.message,
                now=request.now, timezone=request.timezone, client_recent_messages=request.recent_messages,
                request_id=request_id, runtime="sdk",
            )
            profile_row = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
            profile = agent_profile(profile_row.metadata_json if profile_row else None, skill.manifest.name)
            if (request.role == "GENERAL_ASSISTANT" and profile.decision_routing_enabled
                    and self.settings.jev_enabled and self._test_model(skill.manifest.name) is None):
                allowed = [name for name in skill.manifest.allowed_agents
                           if self.skills.get(name, require_enabled=False).manifest.enabled
                           and self.intelligence_settings.skill_enabled(db, user, name)]
                router = AgentDecisionRouter(self.settings)
                if router.candidates(request.message, allowed) and not self.usage.budget_state(db, user.id).optional_suppressed:
                    try:
                        with db.begin_nested():
                            if self.provider_secrets.configured(db, user, "jev"):
                                bundle.dynamic_context["routing_hint"] = router.advise(context, request, allowed)
                    except Exception:
                        # Optional routing must not take the conversational provider down with it.
                        pass
            message = asyncio.run(self._run(context, bundle, selection, hooks, request, thread))
        except AIProviderError as exc:
            error_code, message = exc.code, exc.message
        except MaxTurnsExceeded:
            error_code, message = "agent_turn_limit", "The agent reached its turn limit. Please narrow the request."
        except ModelBehaviorError:
            error_code, message = "agent_invalid_output", "The agent returned an invalid response or tool request."
        except Exception:
            # Provider exceptions may contain private prompts, tool arguments, or credentials.
            error_code = "agent_run_failed"
        if context.host_error is not None:
            error_code, message = context.host_error
        if error_code and context.budget.work_log and context.budget.work_log[-1].kind == "model" and context.budget.work_log[-1].status == "started":
            context.record_activity("model", "failed")
        audit = self._record_usage(context, hooks, selection, error_code, started, thread.id)
        return AssistantResponse(
            work_log=context.budget.work_log,
            message=PROPOSAL_MESSAGE if context.proposal is not None else message,
            role_used=request.role,
            response_type=(AssistantResponseType.proposal if context.proposal is not None else
                           AssistantResponseType.error if error_code else AssistantResponseType.information),
            proposed_action=proposal_read(context.proposal) if context.proposal is not None else None,
            entity_references=context.entity_references,
            request_id=request_id, provider=audit.provider, model=audit.model,
            model_tier=preferred_tier, capability=audit.capability,
            skill_name=skill.manifest.name, skill_version=skill.manifest.version, error_code=error_code,
        )

    def _record_usage(self, context, hooks, selection, error_code, started, thread_id):
        skill = context.skill
        audit = self.usage.record(
            context.db, context.user, request_id=context.request_id, assistant_role=context.role,
            provider=selection.provider if selection else self.settings.agent_provider,
            model=selection.model if selection else None,
            capability=selection.capability if selection else skill.manifest.default_capability,
            skill_name=skill.manifest.name, skill_version=skill.manifest.version,
            prompt_version=self.settings.agent_prompt_version,
            status="proposed" if context.proposal is not None else "error" if error_code else "success",
            usage=hooks.metadata(), conversation_thread_id=thread_id,
            tool_call_count=context.tool_call_count, latency_ms=round((perf_counter() - started) * 1000),
            error_category=error_code,
        )
        audit.metadata_json = {
            **audit.metadata_json, "runtime": "sdk", "model_requests": hooks.usage.requests,
            "reasoning_tokens": hooks.usage.output_tokens_details.reasoning_tokens,
            "parent_request_id": context.parent_request_id,
        }
        if context.proposal is not None:
            audit.proposal_id = context.proposal.id
            audit.tool_name = context.proposal.tool_name
        return audit

    def _max_turns(self, skill) -> int:
        return min(6, self.settings.agent_max_turns, skill.manifest.max_iterations)

    def _test_model(self, skill_name: str) -> Model | None:
        return self.models.get(skill_name, self.model)

    def _test_model_name(self, skill_name: str) -> str | None:
        model = self._test_model(skill_name)
        return getattr(model, "model_name", "life-os-fake-agent") if model is not None else None

    def _run_config(self) -> RunConfig:
        return RunConfig(
            tracing_disabled=not self.settings.agent_trace_export_enabled,
            trace_include_sensitive_data=False,
            workflow_name="Life OS agents",
            # Request sessions and the shared run budget require serial tool execution.
            tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1),
        )

    async def _run(
        self, context: LifeOSAgentContext, bundle: ContextBundle, selection, hooks: AgentUsageHooks,
        request: AssistantMessageRequest, thread: ConversationThread,
    ) -> str:
        async def execute(model: Model) -> str:
            result = await Runner.run(
                self.factory.build(context.role, bundle, model,
                                   agent_tools=self._specialist_tools(context, request, thread)),
                input=[{"role": item.role, "content": item.content} for item in bundle.messages],
                context=context,
                max_turns=self._max_turns(context.skill),
                hooks=hooks,
                run_config=self._run_config(),
            )
            if not isinstance(result.final_output, str) or not result.final_output.strip():
                raise AIProviderError("agent_invalid_output", "The agent returned no final answer.")
            return result.final_output

        test_model = self._test_model(context.skill.manifest.name)
        if test_model is not None:
            return await execute(test_model)
        async with self._configured_model(selection, context.db, context.user) as (model, _client):
            return await execute(model)

    @asynccontextmanager
    async def _configured_model(self, selection, db: Session, user: UserProfile) -> AsyncIterator[tuple[Model, AsyncOpenAI]]:
        api_key = self.provider_secrets.get(db, user, selection.provider)
        options = {
            "api_key": api_key,
            "timeout": self.settings.ai_timeout_seconds,
            "max_retries": 0,
        }
        if selection.provider == "gemini":
            options["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif selection.provider != "openai":
            raise AIProviderError("agent_provider_unsupported", "The selected agent provider is not supported.")
        async with AsyncOpenAI(**options) as client:
            if selection.provider == "openai":
                model = OpenAIResponsesModel(model=selection.model, openai_client=client)
            else:
                model = OpenAIChatCompletionsModel(model=selection.model, openai_client=client)
            yield model, client

    def _specialist_tools(self, parent, request, thread) -> list[FunctionTool]:
        if parent.role != "GENERAL_ASSISTANT" or parent.parent_request_id is not None:
            return []
        tools = []
        for name in parent.skill.manifest.allowed_agents:
            target = self.skills.get(name, require_enabled=False)
            if not target.manifest.enabled or not self.intelligence_settings.skill_enabled(parent.db, parent.user, name):
                continue

            async def invoke(wrapper, arguments: str, skill_name=name):
                return await self._delegate(wrapper.context, skill_name, arguments, request, thread)

            tools.append(FunctionTool(
                name=f"consult_{name.replace('-', '_')}",
                description=f"Consult {target.manifest.name} for specialist reasoning: {target.manifest.description} "
                            "Use direct canonical tools for simple facts. Pass only relevant task details.",
                params_json_schema=SpecialistTask.model_json_schema(),
                on_invoke_tool=invoke,
                strict_json_schema=True,
            ))
        return tools

    async def _delegate(self, parent, name, arguments, request, thread) -> str:
        if (parent.role != "GENERAL_ASSISTANT" or parent.parent_request_id is not None
                or name not in parent.skill.manifest.allowed_agents):
            parent.fail("unauthorized_agent", "The active skill cannot call that specialist.")
        if parent.proposal is not None:
            return PROPOSAL_MESSAGE
        parent.consume_tool_call()
        try:
            task = SpecialistTask.model_validate_json(arguments)
        except ValidationError:
            parent.fail("invalid_agent_arguments", "The specialist task failed host validation.")
        skill = self.skills.get(name, require_enabled=False)
        if (not skill.manifest.enabled or skill.manifest.allowed_agents
                or len(skill.manifest.assistant_roles) != 1
                or skill.manifest.assistant_roles[0] == "GENERAL_ASSISTANT"
                or not self.intelligence_settings.skill_enabled(parent.db, parent.user, name)):
            parent.fail("agent_unavailable", "The requested specialist is unavailable.")
        child = LifeOSAgentContext(
            parent.db, parent.user, skill.manifest.assistant_roles[0], str(uuid4()), skill,
            min(6, skill.manifest.max_tool_calls), budget=parent.budget, parent_request_id=parent.request_id,
        )
        hooks = AgentUsageHooks()
        selection = None
        error_code = None
        started = perf_counter()
        parent.record_activity("delegation", "started", name)
        try:
            selection = self.resolver.resolve(
                skill, ModelTier.standard, db=child.db, user=child.user,
                test_model_name=self._test_model_name(name),
            )
            bundle = self.context_builder.build(
                child.db, child.user, role=child.role, skill=skill, thread=thread, user_request=task.task,
                now=request.now, timezone=request.timezone, request_id=child.request_id, runtime="sdk", delegated=True,
            )
            async def invoke(model: Model) -> str:
                agent = self.factory.build(child.role, bundle, model)
                agent_tool = agent.as_tool(
                    tool_name=f"consult_{name.replace('-', '_')}", tool_description=skill.manifest.description,
                    parameters=SpecialistTask, input_builder=lambda options: options["params"]["task"],
                    max_turns=self._max_turns(skill), run_config=self._run_config(), hooks=hooks,
                    failure_error_function=None,
                )
                # A fresh host context prevents the child from inheriting manager permissions/history.
                return await agent_tool.on_invoke_tool(RunContextWrapper(context=child), task.model_dump_json())

            test_model = self._test_model(name)
            if test_model is not None:
                output = await invoke(test_model)
            else:
                async with self._configured_model(selection, child.db, child.user) as (model, _client):
                    output = await invoke(model)
            if not isinstance(output, str) or not output.strip():
                raise AIProviderError("agent_invalid_output", "The specialist returned no answer.")
            parent.record_activity("delegation", "awaiting_confirmation" if child.proposal else "completed", name)
            return json.dumps({"specialist": name, "answer": output, "proposal_pending": child.proposal is not None})
        except Exception as exc:
            parent.record_activity("delegation", "failed", name)
            if child.host_error is not None:
                error_code, message = child.host_error
            elif isinstance(exc, AIProviderError):
                error_code, message = exc.code, exc.message
            elif isinstance(exc, MaxTurnsExceeded):
                error_code, message = "agent_turn_limit", "The specialist reached its turn limit."
            elif isinstance(exc, ModelBehaviorError):
                error_code, message = "agent_invalid_output", "The specialist returned an invalid response or tool request."
            else:
                error_code, message = "agent_run_failed", "The specialist could not complete the request."
            parent.fail(error_code, message)
        finally:
            if child.proposal is not None:
                parent.proposal = child.proposal
            for ref in child.entity_references:
                if ref not in parent.entity_references:
                    parent.entity_references.append(ref)
            self._record_usage(child, hooks, selection, error_code, started, thread.id)
