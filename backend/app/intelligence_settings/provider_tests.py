from __future__ import annotations

import asyncio
from time import perf_counter
from uuid import uuid4

from agents import Agent, ModelSettings, Runner, RunConfig
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.catalog import DEFAULT_AGENT_MODELS
from app.ai.types import AICapability, AIUsageMetadata
from app.ai.usage import AIUsageService
from app.core.config import Settings
from app.database.models import UserIntelligenceSettings, UserProfile
from app.decision.context import DecisionContextBuilder
from app.decision.errors import DecisionError
from app.decision.gateway import DecisionGateway
from app.decision.questions import SYSTEM_TEST_BOOLEAN_V1
from app.decision.schemas import CognitiveEvent
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.schemas import JevDecisionTestRead, OpenAIChatTestRead


OPENAI_TEST_RESPONSE = "LIFE OS OPENAI TEST OK"


class ProviderCapabilityTestService:
    """Runs bounded provider checks with fixed synthetic input and no life data."""

    def __init__(self, settings: Settings, secret_store: ProviderSecretStore | None = None):
        self.settings = settings
        self.secret_store = secret_store or ProviderSecretStore()
        self.usage = AIUsageService(settings)

    def test_openai_chat(self, db: Session, user: UserProfile) -> OpenAIChatTestRead:
        if not self.settings.ai_enabled:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="AI is disabled for this environment.")
        budget = self.usage.budget_state(db, user.id)
        if budget.optional_suppressed:
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="The monthly AI budget is exhausted; provider tests are paused.")

        api_key = self.secret_store.get(db, user, "openai")
        row = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        preferences = (row.metadata_json or {}).get("agent_model_preferences") or {} if row else {}
        self_core = preferences.get("self-core") or {}
        model = (
            self_core.get("fast_model")
            if self_core.get("provider") == "openai"
            else DEFAULT_AGENT_MODELS["openai"]["FAST"]
        ) or DEFAULT_AGENT_MODELS["openai"]["FAST"]
        started = perf_counter()
        request_id = str(uuid4())
        response_text = ""
        usage = AIUsageMetadata()
        error_code = None
        try:
            response_text, usage = asyncio.run(self._run_openai_probe(api_key, model))
        except Exception as exc:
            error_code = type(exc).__name__
        latency_ms = round((perf_counter() - started) * 1000)
        passed = _normalize_probe(response_text) == _normalize_probe(OPENAI_TEST_RESPONSE)
        self.usage.record(
            db, user, request_id=request_id, assistant_role="GENERAL_ASSISTANT", provider="openai", model=model,
            capability=AICapability.fast, skill_name="provider-test", skill_version="1",
            prompt_version=self.settings.agent_prompt_version, status="success" if response_text else "error",
            usage=usage, latency_ms=latency_ms, error_category=error_code,
        )
        if not response_text:
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail="OpenAI did not complete the controlled chat test. Check the saved key and selected model.")
        return OpenAIChatTestRead(
            model=model, connected=True, passed=passed, response=response_text[:500], latency_ms=latency_ms,
        )

    async def _run_openai_probe(self, api_key: str, model: str) -> tuple[str, AIUsageMetadata]:
        async with AsyncOpenAI(
            api_key=api_key, timeout=self.settings.ai_timeout_seconds, max_retries=0,
        ) as client:
            provider_model = OpenAIResponsesModel(model=model, openai_client=client)
            agent = Agent(
                name="Life OS OpenAI connection test",
                instructions=(
                    "This is a fixed provider connection check. Do not use tools, request personal information, "
                    f"or add any text. Reply with exactly: {OPENAI_TEST_RESPONSE}"
                ),
                model=provider_model,
                tools=[],
                model_settings=ModelSettings(store=False),
            )
            result = await Runner.run(
                agent,
                input="Run the fixed connection check.",
                max_turns=1,
                run_config=RunConfig(
                    tracing_disabled=True,
                    trace_include_sensitive_data=False,
                    workflow_name="Life OS provider connection test",
                ),
            )
        text = result.final_output if isinstance(result.final_output, str) else ""
        usage = _openai_run_usage(result)
        return text.strip(), usage

    def test_jev_decision(self, db: Session, user: UserProfile) -> JevDecisionTestRead:
        if not self.settings.jev_enabled:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Jev decisions are disabled for this environment.")

        test_settings = self.settings
        if self.settings.app_env.lower() != "production":
            test_settings = self.settings.model_copy(update={
                "decision_infra_enabled": True,
                "decision_routing_mode": "JEV_ONLY",
            })
        elif not self.settings.decision_infra_enabled:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Decision infrastructure is disabled in production.")

        event = CognitiveEvent(
            event_type="provider.connection_test", source="settings",
            input_payload={"test": "synthetic_boolean_check"},
        )
        context = DecisionContextBuilder().build(
            event=event,
            question=SYSTEM_TEST_BOOLEAN_V1,
            facts={"left": 7, "operator": "greater_than", "right": 3},
            metadata={"provider_test": True, "expected_result": True},
        )
        started = perf_counter()
        try:
            execution = DecisionGateway(test_settings).evaluate(
                db,
                user,
                event=event,
                question=SYSTEM_TEST_BOOLEAN_V1,
                context=context,
                skill_name="provider-test",
                skill_version="1",
                trace_metadata={"provider_test": True, "hidden_reasoning_stored": False},
            )
        except DecisionError:
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail="Jev did not complete the controlled typed-decision test.") from None
        result = execution.result
        latency_ms = round((perf_counter() - started) * 1000)
        if not isinstance(result.selected_answer, bool):
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail="Jev returned a non-boolean result for the typed decision test.")
        true_probability = (result.probabilities or {}).get("true")
        if true_probability is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail="Jev did not return the expected yes-probability for the typed decision test.")
        return JevDecisionTestRead(
            model=result.model_version,
            connected=True,
            passed=result.selected_answer is True,
            selected_answer=result.selected_answer,
            true_probability=true_probability,
            trace_id=execution.trace_id,
            latency_ms=latency_ms,
        )


def _openai_run_usage(result) -> AIUsageMetadata:
    metadata = AIUsageMetadata()
    for response in getattr(result, "raw_responses", ()):
        usage = getattr(response, "usage", None)
        if usage is None:
            continue
        metadata.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        metadata.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        metadata.total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
        input_details = getattr(usage, "input_tokens_details", None)
        metadata.cached_tokens += int(getattr(input_details, "cached_tokens", 0) or 0)
    metadata.estimated = metadata.total_tokens == 0
    return metadata


def _normalize_probe(value: str) -> str:
    return " ".join(value.upper().strip().split()).strip(" .!\n\t")
