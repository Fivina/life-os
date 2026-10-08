from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.database.models import CognitiveTrace, UserProfile
from app.decision.errors import (
    DecisionError,
    DecisionInfrastructureDisabled,
    DecisionProviderError,
    DecisionProviderTimeout,
    DecisionProviderUnavailable,
    DecisionValidationError,
)
from app.decision.evidence import DecisionProviderEvidenceService
from app.decision.provider_schemas import ProviderCallRecord, ProviderRole, ProviderStatus, RoutingReason
from app.decision.providers.base import DecisionProvider
from app.decision.providers.fake import FakeDecisionProvider
from app.decision.providers.jev import JevProvider
from app.decision.providers.laya import LayaLocalProvider
from app.decision.routing import DecisionRoutingPolicy
from app.decision.schemas import CognitiveEvent, DecisionContext, DecisionExecution, DecisionOutputType, DecisionProviderResult, DecisionQuestion, DecisionResult
from app.decision.traces import DecisionTraceService
from app.intelligence_settings.provider_credentials import ProviderSecretStore


logger = get_logger(__name__)


class DecisionGateway:
    """Host-owned boundary for routing and validating bounded typed decisions."""

    def __init__(
        self,
        settings: Settings,
        providers: dict[str, DecisionProvider] | None = None,
        trace_service: DecisionTraceService | None = None,
        routing_policy: DecisionRoutingPolicy | None = None,
        evidence_service: DecisionProviderEvidenceService | None = None,
    ):
        self.settings = settings
        self._uses_builtin_providers = providers is None
        self.providers = providers if providers is not None else {
            "fake": FakeDecisionProvider(),
            "laya_local": LayaLocalProvider(settings),
            # A shared environment key must never become every user's credential.
            "jev": JevProvider(settings.model_copy(update={"jev_api_key": None})),
        }
        self.trace_service = trace_service or DecisionTraceService()
        self.routing_policy = routing_policy or DecisionRoutingPolicy(settings)
        self.evidence_service = evidence_service or DecisionProviderEvidenceService()

    def evaluate(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        context: DecisionContext,
        skill_name: str | None = None,
        skill_version: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> DecisionExecution:
        if not self.settings.decision_infra_enabled:
            raise DecisionInfrastructureDisabled("Decision infrastructure is disabled.")
        if (context.event_id, context.question_id, context.question_version) != (
            event.event_id,
            question.question_id,
            question.question_version,
        ):
            raise DecisionValidationError("Decision context does not match the event and question identity.")

        providers = self._providers_for_user(db, user)
        route = self.routing_policy.route(question=question, context=context, providers=providers)
        started_at = datetime.now(UTC)
        calls: list[ProviderCallRecord] = []
        comparisons: list[dict[str, Any]] = []
        jev_budget_available = (
            self.evidence_service.provider_cost_today_eur(db, user, provider="jev")
            < self.settings.jev_daily_budget_eur
        )

        primary_result, primary_call, primary_error = self._call(
            provider_id=route.primary_provider,
            role=ProviderRole.primary,
            routing_reason=route.reason_code.value,
            providers=providers,
            question=question,
            context=context,
            budget_allowed=jev_budget_available,
        )
        calls.append(primary_call)
        operational_result = primary_result
        final_error = primary_error

        fallback_needed = bool(
            route.fallback_provider
            and (
                primary_result is None
                or (
                    route.minimum_confidence is not None
                    and (primary_result.confidence is None or primary_result.confidence < route.minimum_confidence)
                )
            )
        )
        if fallback_needed and route.fallback_provider:
            fallback_reason = (
                RoutingReason.primary_error.value
                if primary_result is None
                else RoutingReason.low_primary_confidence.value
            )
            fallback_result, fallback_call, fallback_error = self._call(
                provider_id=route.fallback_provider,
                role=ProviderRole.fallback,
                routing_reason=fallback_reason,
                providers=providers,
                question=question,
                context=context,
                budget_allowed=jev_budget_available,
            )
            calls.append(fallback_call)
            comparisons.append({
                "primary_provider": route.primary_provider,
                "comparison_provider": route.fallback_provider,
                "comparison_role": ProviderRole.fallback,
                "primary_result": primary_result,
                "comparison_result": fallback_result,
                "primary_error_code": primary_error.code if primary_error else None,
                "comparison_error_code": fallback_error.code if fallback_error else None,
            })
            if fallback_result is not None:
                operational_result = fallback_result
                final_error = None
            elif primary_result is not None:
                operational_result = primary_result
                final_error = None
            else:
                final_error = fallback_error or primary_error

        if operational_result is None:
            error = final_error or DecisionProviderUnavailable("No decision provider produced a valid result.")
            self._persist_failed_attempt(
                db,
                user,
                event=event,
                question=question,
                context=context,
                started_at=started_at,
                error=error,
                route=route,
                calls=calls,
                providers=providers,
            )
            raise error

        if (
            route.shadow_provider
            and route.shadow_provider != operational_result.provider
            and self.routing_policy.should_sample_shadow(event_id=event.event_id, question=question)
            and self.evidence_service.shadow_cost_today_eur(db, user) < self.settings.decision_shadow_daily_budget_eur
        ):
            shadow_result, shadow_call, shadow_error = self._call(
                provider_id=route.shadow_provider,
                role=ProviderRole.shadow,
                routing_reason=RoutingReason.shadow_only.value,
                providers=providers,
                question=question,
                context=context,
                budget_allowed=jev_budget_available,
            )
            calls.append(shadow_call)
            comparisons.append({
                "primary_provider": operational_result.provider,
                "comparison_provider": route.shadow_provider,
                "comparison_role": ProviderRole.shadow,
                "primary_result": operational_result,
                "comparison_result": shadow_result,
                "primary_error_code": None,
                "comparison_error_code": shadow_error.code if shadow_error else None,
            })

        trace, trace_status = self._persist_completed(
            db,
            user,
            event=event,
            question=question,
            context=context,
            result=operational_result,
            started_at=started_at,
            skill_name=skill_name,
            skill_version=skill_version,
            route=route,
            calls=calls,
            comparisons=comparisons,
            trace_metadata=trace_metadata,
        )
        return DecisionExecution(result=operational_result, trace_id=trace.id if trace else None, trace_status=trace_status)

    def _providers_for_user(self, db: Session, user: UserProfile) -> dict[str, DecisionProvider]:
        if not self._uses_builtin_providers:
            return self.providers
        providers = dict(self.providers)
        # Never use JEV_API_KEY from process configuration for account decisions.
        providers["jev"] = JevProvider(self.settings.model_copy(update={"jev_api_key": None}))
        if not self.settings.jev_enabled:
            return providers
        try:
            secret_store = ProviderSecretStore()
            if not secret_store.configured(db, user, "jev"):
                return providers
            api_key = secret_store.get(db, user, "jev")
        except Exception as exc:
            logger.warning(
                "jev_user_credential_unavailable",
                extra={"user_id": user.id, "error_type": type(exc).__name__},
            )
            return providers
        providers["jev"] = JevProvider(self.settings.model_copy(update={"jev_api_key": api_key}))
        return providers

    def provider_health(self) -> tuple[dict[str, Any], ...]:
        return tuple(provider.health().model_dump(mode="json") for provider in self.providers.values())

    def _call(
        self,
        *,
        provider_id: str,
        role: ProviderRole,
        routing_reason: str,
        providers: dict[str, DecisionProvider],
        question: DecisionQuestion,
        context: DecisionContext,
        budget_allowed: bool = True,
    ) -> tuple[DecisionResult | None, ProviderCallRecord, DecisionError | None]:
        provider = providers[provider_id]
        started = perf_counter()
        if provider_id == "jev" and not budget_allowed:
            error = DecisionProviderUnavailable("Jev daily budget is exhausted.")
            return None, ProviderCallRecord(
                provider=provider.name,
                model_version=provider.model_version,
                role=role,
                routing_reason=routing_reason,
                status=ProviderStatus.skipped,
                latency_ms=0,
                error_code=error.code,
                metadata={"budget_exhausted": True},
            ), error
        try:
            raw_result = provider.evaluate(question=question, context=context)
            payload = raw_result.model_dump(mode="python") if isinstance(raw_result, DecisionProviderResult) else raw_result
            validated = DecisionProviderResult.model_validate(payload)
            validated.validate_for(question)
            if validated.provider != provider.name:
                raise DecisionValidationError("Decision result provider identity does not match the selected adapter.")
            if (
                provider.name in {"laya_local", "jev"}
                and question.output_type in {DecisionOutputType.categorical, DecisionOutputType.boolean}
                and validated.confidence is None
            ):
                raise DecisionValidationError("Production decision providers must return normalized confidence.")
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            result = DecisionResult(
                **validated.model_dump(),
                latency_ms=latency_ms,
                host_policy_version=self.settings.decision_policy_version,
            )
            return result, self._call_record(
                result=result,
                role=role,
                routing_reason=routing_reason,
                latency_ms=latency_ms,
            ), None
        except DecisionError as exc:
            error = exc
        except TimeoutError as exc:
            error = DecisionProviderTimeout("Decision provider timed out.", retryable=True)
            error.__cause__ = exc
        except (ValidationError, ValueError, TypeError) as exc:
            error = DecisionValidationError("Decision provider returned an invalid typed result.")
            error.__cause__ = exc
        except Exception as exc:
            error = DecisionProviderError("Decision provider failed.", retryable=True)
            error.__cause__ = exc
        finally:
            if provider_id == "jev" and provider is not self.providers.get("jev"):
                close = getattr(provider, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception as exc:
                        logger.warning(
                            "jev_request_client_close_failed",
                            extra={"error_type": type(exc).__name__},
                        )
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        return None, ProviderCallRecord(
            provider=provider.name,
            model_version=provider.model_version,
            role=role,
            routing_reason=routing_reason,
            status=ProviderStatus.failed,
            latency_ms=latency_ms,
            error_code=error.code,
        ), error

    @staticmethod
    def _call_record(
        *,
        result: DecisionResult,
        role: ProviderRole,
        routing_reason: str,
        latency_ms: int,
    ) -> ProviderCallRecord:
        usage = result.metadata.get("usage") or {}
        return ProviderCallRecord(
            provider=result.provider,
            model_version=result.model_version,
            role=role,
            routing_reason=routing_reason,
            status=ProviderStatus.completed,
            latency_ms=latency_ms,
            input_units=int(usage.get("input_tokens") or usage.get("input_units") or 0),
            output_units=int(usage.get("output_tokens") or usage.get("output_units") or 0),
            estimated_cost_eur=result.metadata.get("estimated_cost_eur"),
            request_id=result.metadata.get("request_id"),
            metadata={
                "provider_version": result.provider_version,
                "question_count": int(result.metadata.get("batch_question_count") or 1),
                "reported_cost_usd": result.metadata.get("cost_usd"),
            },
        )

    def _persist_completed(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        context: DecisionContext,
        result: DecisionResult,
        started_at: datetime,
        skill_name: str | None,
        skill_version: str | None,
        route: Any,
        calls: list[ProviderCallRecord],
        comparisons: list[dict[str, Any]],
        trace_metadata: dict[str, Any] | None,
    ) -> tuple[CognitiveTrace | None, str]:
        trace: CognitiveTrace | None = None
        trace_status = "disabled"
        try:
            with db.begin_nested():
                if self.settings.decision_tracing_enabled:
                    trace = self.trace_service.record_completed(
                        db,
                        user,
                        event=event,
                        question=question,
                        context=context,
                        result=result,
                        started_at=started_at,
                        skill_name=skill_name,
                        skill_version=skill_version,
                        trace_metadata={
                            **(trace_metadata or {}),
                            "provider_route": route.model_dump(mode="json"),
                            "provider_calls": [call.model_dump(mode="json") for call in calls],
                        },
                    )
                    trace_status = "persisted"
                self.evidence_service.record_usage(
                    db,
                    user,
                    event=event,
                    question_id=question.question_id,
                    question_version=question.question_version,
                    question_family=question.family,
                    routing_policy_version=route.policy_version,
                    calls=calls,
                    trace=trace,
                )
                for comparison in comparisons:
                    self.evidence_service.record_disagreement(
                        db,
                        user,
                        event=event,
                        question_id=question.question_id,
                        question_version=question.question_version,
                        question_family=question.family,
                        context=context,
                        routing_policy_version=route.policy_version,
                        operational_result=result,
                        trace=trace,
                        **comparison,
                    )
        except Exception as exc:
            logger.exception(
                "decision_trace_persistence_failed",
                extra={"user_id": user.id, "event_type": event.event_type, "error_type": type(exc).__name__},
            )
            trace = None
            trace_status = "failed" if self.settings.decision_tracing_enabled else "disabled"
        return trace, trace_status

    def _persist_failed_attempt(
        self,
        db: Session,
        user: UserProfile,
        *,
        event: CognitiveEvent,
        question: DecisionQuestion,
        context: DecisionContext,
        started_at: datetime,
        error: DecisionError,
        route: Any,
        calls: list[ProviderCallRecord],
        providers: dict[str, DecisionProvider],
    ) -> None:
        try:
            with db.begin_nested():
                trace = None
                if self.settings.decision_tracing_enabled:
                    provider = providers[route.primary_provider]
                    trace = self.trace_service.record_failed(
                        db,
                        user,
                        event=event,
                        question=question,
                        context=context,
                        provider=provider.name,
                        provider_version=provider.provider_version,
                        model_version=provider.model_version,
                        policy_version=self.settings.decision_policy_version,
                        started_at=started_at,
                        latency_ms=sum(call.latency_ms for call in calls),
                        error_code=error.code,
                        error_message=error.message,
                    )
                self.evidence_service.record_usage(
                    db,
                    user,
                    event=event,
                    question_id=question.question_id,
                    question_version=question.question_version,
                    question_family=question.family,
                    routing_policy_version=route.policy_version,
                    calls=calls,
                    trace=trace,
                )
        except Exception as exc:
            logger.exception(
                "decision_failure_evidence_persistence_failed",
                extra={"user_id": user.id, "event_type": event.event_type, "error_type": type(exc).__name__},
            )
