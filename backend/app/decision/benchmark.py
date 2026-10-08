from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
import math
from statistics import median
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import DecisionTrainingExample, UserProfile
from app.decision.errors import DecisionError, UnsupportedDecisionQuestion
from app.decision.providers.base import DecisionProvider
from app.decision.schemas import DecisionContext, DecisionOutputType, DecisionProviderResult, DecisionQuestion


BENCHMARK_DATASET_VERSION = "life-os-decisions-v1"


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=120)
    question: DecisionQuestion
    context: DecisionContext
    dataset_version: str = BENCHMARK_DATASET_VERSION
    task_family: str = "system"
    expected_answer: str | bool | int | float | None = None
    acceptable_answers: tuple[str | bool | int | float, ...] = ()
    label_source: str = "synthetic_explicit"
    label_confidence: float = Field(default=1.0, ge=0, le=1)
    difficulty: str = "normal"
    sensitivity: str = "synthetic_non_sensitive"
    tags: tuple[str, ...] = ()
    notes: str | None = Field(default=None, max_length=500)


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    task_family: str = "system"
    question_id: str
    question_version: int
    schema_valid: bool
    supported: bool = True
    selected_answer: str | bool | int | float | dict | None = None
    exact_match: bool | None = None
    acceptable: bool | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    provider: str
    provider_version: str
    model_version: str | None = None
    latency_ms: int = Field(ge=0)
    cold_start_ms: int | None = Field(default=None, ge=0)
    network_latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_eur: float | None = Field(default=None, ge=0)
    error_code: str | None = None


class TaskFamilyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    task_family: str
    n: int
    valid_output_rate: float
    exact_match_rate: float | None
    acceptable_match_rate: float | None
    failure_rate: float
    unsupported_rate: float
    median_latency_ms: float | None
    p95_latency_ms: float | None
    brier_score: float | None = None
    log_loss: float | None = None
    expected_calibration_error: float | None = None
    mean_absolute_error: float | None = None
    within_half_level_rate: float | None = None
    total_external_cost_eur: float | None = None
    cost_per_case_eur: float | None = None
    cost_per_1000_eur: float | None = None
    cold_start_ms: float | None = None
    median_warm_latency_ms: float | None = None


class RoutingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_version: str
    created_at: datetime
    benchmark_dataset_version: str
    task_family_routes: dict[str, str]
    confidence_thresholds: dict[str, float]
    fallback_providers: dict[str, str | None]
    shadow_settings: dict[str, Any]
    evidence_summary: dict[str, Any]
    status: str = "candidate"


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str
    generated_at: datetime
    provider_versions: dict[str, dict[str, str | None]]
    results: tuple[BenchmarkResult, ...]
    task_family_metrics: tuple[TaskFamilyMetrics, ...]
    routing_recommendation: RoutingProfile
    notes: tuple[str, ...] = ()


class DecisionBenchmarkHarness:
    def __init__(self, provider: DecisionProvider):
        self.provider = provider
        self._has_run = False

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        started = perf_counter()
        cold = not self._has_run
        self._has_run = True
        try:
            support = self.provider.supports(question=case.question, context=case.context)
            if not support.supported:
                raise UnsupportedDecisionQuestion(support.reason_code)
            raw = self.provider.evaluate(question=case.question, context=case.context)
            payload = raw.model_dump(mode="python") if isinstance(raw, DecisionProviderResult) else raw
            validated = DecisionProviderResult.model_validate(payload)
            validated.validate_for(case.question)
            elapsed = max(0, round((perf_counter() - started) * 1000))
            acceptable = None if not case.acceptable_answers else validated.selected_answer in case.acceptable_answers
            exact = None if case.expected_answer is None else validated.selected_answer == case.expected_answer
            return BenchmarkResult(
                case_id=case.case_id,
                task_family=case.task_family,
                question_id=case.question.question_id,
                question_version=case.question.question_version,
                schema_valid=True,
                selected_answer=validated.selected_answer,
                exact_match=exact,
                acceptable=acceptable,
                confidence=validated.confidence,
                probabilities=validated.probabilities,
                provider=validated.provider,
                provider_version=validated.provider_version,
                model_version=validated.model_version,
                latency_ms=elapsed,
                cold_start_ms=elapsed if cold else None,
                network_latency_ms=validated.metadata.get("network_latency_ms"),
                estimated_cost_eur=validated.metadata.get("estimated_cost_eur"),
            )
        except (DecisionError, ValidationError, ValueError, TypeError) as exc:
            return BenchmarkResult(
                case_id=case.case_id,
                task_family=case.task_family,
                question_id=case.question.question_id,
                question_version=case.question.question_version,
                schema_valid=False,
                supported=not isinstance(exc, UnsupportedDecisionQuestion),
                provider=self.provider.name,
                provider_version=self.provider.provider_version,
                model_version=self.provider.model_version,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
                error_code=getattr(exc, "code", "decision_validation_error"),
            )

    def run(self, cases: tuple[BenchmarkCase, ...]) -> tuple[BenchmarkResult, ...]:
        return tuple(self.run_case(case) for case in cases)


def run_provider_benchmark(
    providers: tuple[DecisionProvider, ...],
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> BenchmarkReport:
    dataset = cases or representative_life_os_cases()
    results: list[BenchmarkResult] = []
    versions: dict[str, dict[str, str | None]] = {}
    for provider in providers:
        capabilities = provider.capabilities()
        versions[provider.name] = {
            "provider_version": provider.provider_version,
            "model_version": provider.model_version,
            "available": str(capabilities.available).lower(),
        }
        results.extend(DecisionBenchmarkHarness(provider).run(dataset))
    metrics = _aggregate_metrics(tuple(results), dataset)
    recommendation = _recommend_profile(metrics, dataset)
    return BenchmarkReport(
        dataset_version=dataset[0].dataset_version if dataset else BENCHMARK_DATASET_VERSION,
        generated_at=datetime.now(UTC),
        provider_versions=versions,
        results=tuple(results),
        task_family_metrics=metrics,
        routing_recommendation=recommendation,
        notes=(
            "Candidate recommendations are evidence summaries and are never activated automatically.",
            "Cold-start and warm latency are reported separately; no winner-takes-all score is calculated.",
        ),
    )


def _aggregate_metrics(
    results: tuple[BenchmarkResult, ...],
    cases: tuple[BenchmarkCase, ...],
) -> tuple[TaskFamilyMetrics, ...]:
    expected = {case.case_id: case.expected_answer for case in cases}
    grouped: dict[tuple[str, str], list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        grouped[(result.provider, result.task_family)].append(result)
    summaries: list[TaskFamilyMetrics] = []
    for (provider, family), items in sorted(grouped.items()):
        n = len(items)
        valid = [item for item in items if item.schema_valid]
        exact = [item.exact_match for item in items if item.exact_match is not None]
        acceptable = [item.acceptable for item in items if item.acceptable is not None]
        latencies = sorted(item.latency_ms for item in items)
        warm = sorted(item.latency_ms for item in items if item.cold_start_ms is None)
        probability_rows = [
            item for item in valid
            if item.probabilities is not None and isinstance(expected.get(item.case_id), (str, bool))
        ]
        brier_values: list[float] = []
        log_losses: list[float] = []
        calibration_pairs: list[tuple[float, float]] = []
        score_pairs = [
            (float(item.selected_answer), float(expected[item.case_id]))
            for item in valid
            if isinstance(item.selected_answer, (int, float))
            and not isinstance(item.selected_answer, bool)
            and isinstance(expected.get(item.case_id), (int, float))
            and not isinstance(expected.get(item.case_id), bool)
        ]
        for item in probability_rows:
            label = str(expected[item.case_id]).lower() if isinstance(expected[item.case_id], bool) else str(expected[item.case_id])
            probability = max(1e-12, item.probabilities.get(label, 0.0))
            brier_values.append(sum((p - (1.0 if choice == label else 0.0)) ** 2 for choice, p in item.probabilities.items()))
            log_losses.append(-math.log(probability))
            calibration_pairs.append((item.confidence or max(item.probabilities.values()), 1.0 if item.exact_match else 0.0))
        costs = [item.estimated_cost_eur for item in items if item.estimated_cost_eur is not None]
        total_cost = sum(costs) if costs else None
        summaries.append(TaskFamilyMetrics(
            provider=provider,
            task_family=family,
            n=n,
            valid_output_rate=len(valid) / n,
            exact_match_rate=sum(bool(value) for value in exact) / len(exact) if exact else None,
            acceptable_match_rate=sum(bool(value) for value in acceptable) / len(acceptable) if acceptable else None,
            failure_rate=sum(item.error_code is not None and item.supported for item in items) / n,
            unsupported_rate=sum(not item.supported for item in items) / n,
            median_latency_ms=float(median(latencies)) if latencies else None,
            p95_latency_ms=float(latencies[min(len(latencies) - 1, math.ceil(len(latencies) * 0.95) - 1)]) if latencies else None,
            brier_score=sum(brier_values) / len(brier_values) if brier_values else None,
            log_loss=sum(log_losses) / len(log_losses) if log_losses else None,
            expected_calibration_error=_expected_calibration_error(calibration_pairs),
            mean_absolute_error=(
                sum(abs(selected - target) for selected, target in score_pairs) / len(score_pairs)
                if score_pairs else None
            ),
            within_half_level_rate=(
                sum(abs(selected - target) <= 0.5 for selected, target in score_pairs) / len(score_pairs)
                if score_pairs else None
            ),
            total_external_cost_eur=total_cost,
            cost_per_case_eur=total_cost / n if total_cost is not None else None,
            cost_per_1000_eur=total_cost * 1000 / n if total_cost is not None else None,
            cold_start_ms=float(next((item.cold_start_ms for item in items if item.cold_start_ms is not None), 0)),
            median_warm_latency_ms=float(median(warm)) if warm else None,
        ))
    return tuple(summaries)


def _expected_calibration_error(pairs: list[tuple[float, float]], bins: int = 5) -> float | None:
    if not pairs:
        return None
    total = len(pairs)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [pair for pair in pairs if lower <= pair[0] <= upper if index == bins - 1 or pair[0] < upper]
        if bucket:
            mean_confidence = sum(pair[0] for pair in bucket) / len(bucket)
            mean_accuracy = sum(pair[1] for pair in bucket) / len(bucket)
            error += (len(bucket) / total) * abs(mean_confidence - mean_accuracy)
    return error


def _recommend_profile(
    metrics: tuple[TaskFamilyMetrics, ...],
    cases: tuple[BenchmarkCase, ...],
) -> RoutingProfile:
    by_family: dict[str, list[TaskFamilyMetrics]] = defaultdict(list)
    for metric in metrics:
        by_family[metric.task_family].append(metric)
    routes: dict[str, str] = {}
    fallbacks: dict[str, str | None] = {}
    evidence: dict[str, Any] = {}
    for family, candidates in sorted(by_family.items()):
        eligible = [
            item for item in candidates
            if item.provider != "fake" and item.n >= 3 and item.valid_output_rate >= 0.9
        ]
        ranked = sorted(
            eligible,
            key=lambda item: (
                -(item.exact_match_rate if item.exact_match_rate is not None else -1),
                -(item.acceptable_match_rate if item.acceptable_match_rate is not None else -1),
                item.median_latency_ms if item.median_latency_ms is not None else float("inf"),
            ),
        )
        if ranked:
            routes[family] = ranked[0].provider
            fallbacks[family] = ranked[1].provider if len(ranked) > 1 else None
        evidence[family] = {
            "sufficient_sample": bool(ranked),
            "fake_is_test_only": any(item.provider == "fake" for item in candidates),
            "providers": [item.model_dump(mode="json") for item in candidates],
        }
    return RoutingProfile(
        profile_version="candidate-routing-v1",
        created_at=datetime.now(UTC),
        benchmark_dataset_version=cases[0].dataset_version if cases else BENCHMARK_DATASET_VERSION,
        task_family_routes=routes,
        confidence_thresholds={family: 0.72 for family in routes},
        fallback_providers=fallbacks,
        shadow_settings={"enabled": False, "sample_rate": 0.0},
        evidence_summary=evidence,
    )


class FeedbackBenchmarkSelector:
    """Selects strong explicit feedback evidence without treating every example as benchmark truth."""

    def select(self, db: Session, user: UserProfile, *, limit: int = 200) -> tuple[DecisionTrainingExample, ...]:
        candidates = list(db.scalars(
            select(DecisionTrainingExample)
            .where(
                DecisionTrainingExample.user_id == user.id,
                DecisionTrainingExample.label_strength == "STRONG",
                DecisionTrainingExample.feedback_confidence == "HIGH",
                DecisionTrainingExample.label_source != "MODEL_DISAGREEMENT",
            )
            .order_by(DecisionTrainingExample.created_at.desc())
            .limit(max(1, min(limit, 1000)))
        ))
        grouped: dict[tuple[str, int, str], list[DecisionTrainingExample]] = defaultdict(list)
        for item in candidates:
            if item.question_version >= 1 and item.context_json and item.label_json and item.explicit_feedback_json:
                grouped[(item.question_id, item.question_version, item.cognitive_event_ref)].append(item)
        selected: list[DecisionTrainingExample] = []
        for items in grouped.values():
            labels = {json.dumps(item.label_json, sort_keys=True) for item in items}
            if len(labels) == 1:
                selected.extend(items)
        return tuple(selected)


def representative_fake_cases() -> tuple[BenchmarkCase, ...]:
    from app.decision.context import DecisionContextBuilder
    from app.decision.questions import MEMORY_CONTEXT_RELEVANT_V1, SYSTEM_TEST_BOOLEAN_V1
    from app.decision.schemas import CognitiveEvent

    builder = DecisionContextBuilder()
    event = CognitiveEvent(event_id="benchmark:event:1", event_type="benchmark.fixture", source="benchmark")
    normal = builder.build(
        event=event,
        question=MEMORY_CONTEXT_RELEVANT_V1,
        facts={"candidate_kind": "preference", "current_domain": "kitchen"},
    )
    low_confidence = builder.build(
        event=event,
        question=SYSTEM_TEST_BOOLEAN_V1,
        facts={"fixture": True},
        metadata={"fake_scenario": "low_confidence"},
    )
    invalid = builder.build(
        event=event,
        question=MEMORY_CONTEXT_RELEVANT_V1,
        metadata={"fake_scenario": "invalid_response"},
    )
    return (
        BenchmarkCase(
            case_id="memory-context-normal-v1", task_family="memory",
            question=MEMORY_CONTEXT_RELEVANT_V1, context=normal,
            acceptable_answers=MEMORY_CONTEXT_RELEVANT_V1.allowed_choices,
            tags=("categorical", "normal"),
        ),
        BenchmarkCase(
            case_id="boolean-low-confidence-v1", task_family="system",
            question=SYSTEM_TEST_BOOLEAN_V1, context=low_confidence,
            acceptable_answers=(True, False), tags=("boolean", "low-confidence"),
        ),
        BenchmarkCase(
            case_id="invalid-provider-output-v1", task_family="memory",
            question=MEMORY_CONTEXT_RELEVANT_V1, context=invalid,
            tags=("categorical", "invalid"),
        ),
    )


def representative_life_os_cases() -> tuple[BenchmarkCase, ...]:
    from app.decision.context import DecisionContextBuilder
    from app.decision.questions import ATTENTION_ACTION_V1, MEMORY_CONTEXT_RELEVANT_V1
    from app.decision.schemas import CognitiveEvent

    evaluation_questions = (
        ATTENTION_ACTION_V1,
        DecisionQuestion(
            question_id="benchmark.curiosity_action", question_version=1, family="curiosity",
            output_type=DecisionOutputType.categorical, allowed_choices=("ASK_NOW", "DEFER", "SKIP"),
            description="Evaluate whether an explicit bounded question is worth the interaction cost.",
        ),
        DecisionQuestion(
            question_id="benchmark.context_relevance", question_version=1, family="context_relevance",
            output_type=DecisionOutputType.categorical, allowed_choices=("RELEVANT", "IRRELEVANT"),
            description="Evaluate relevance of an explicit context candidate.",
        ),
        DecisionQuestion(
            question_id="benchmark.prospective_relevance", question_version=1, family="prospective",
            output_type=DecisionOutputType.categorical, allowed_choices=("ELIGIBLE", "DORMANT"),
            description="Evaluate a supplied prospective-thread relevance state.",
        ),
        MEMORY_CONTEXT_RELEVANT_V1,
        DecisionQuestion(
            question_id="benchmark.contributor_activation", question_version=1, family="contributor_activation",
            output_type=DecisionOutputType.categorical, allowed_choices=("ACTIVATE", "SKIP"),
            description="Evaluate whether an already routed contributor candidate is relevant.",
        ),
        DecisionQuestion(
            question_id="benchmark.urgency_score", question_version=1, family="urgency_score",
            output_type=DecisionOutputType.scalar,
            score_rubric=("can wait", "soon", "blocking"),
            description="Score the urgency of an explicitly supplied bounded candidate.",
        ),
    )
    fixtures: list[BenchmarkCase] = []
    expected_by_family = {
        "attention": ("SILENT", "MENTION_WHEN_NATURAL", "ASK"),
        "curiosity": ("SKIP", "DEFER", "ASK_NOW"),
        "context_relevance": ("IRRELEVANT", "RELEVANT", "RELEVANT"),
        "prospective": ("DORMANT", "ELIGIBLE", "DORMANT"),
        "memory": ("irrelevant", "relevant", "relevant"),
        "contributor_activation": ("SKIP", "ACTIVATE", "ACTIVATE"),
        "urgency_score": (0, 1, 2),
    }
    scenarios = (
        {"signal": "weak", "urgency": 0.1, "current_activity": "focused_work"},
        {"signal": "clear", "urgency": 0.5, "current_activity": "available"},
        {"signal": "high_impact_uncertainty", "urgency": 0.8, "current_activity": "transition"},
    )
    builder = DecisionContextBuilder()
    for question in evaluation_questions:
        for index, facts in enumerate(scenarios, start=1):
            expected = expected_by_family[question.family][index - 1]
            event = CognitiveEvent(
                event_id=f"benchmark:{question.family}:{index}",
                event_type=f"benchmark.{question.family}", source="synthetic_benchmark",
            )
            context = builder.build(
                event=event, question=question, facts=facts,
                metadata=(
                    {"fake_selected_answer": expected}
                    if question.output_type == DecisionOutputType.categorical else {}
                ),
            )
            fixtures.append(BenchmarkCase(
                case_id=f"{question.family}-{index}-v1",
                task_family=question.family,
                question=question,
                context=context,
                expected_answer=expected,
                acceptable_answers=(expected,),
                difficulty=("easy", "normal", "boundary")[index - 1],
                tags=(question.output_type.value, facts["signal"]),
                notes="Synthetic evaluation case over explicit Life OS state; no private user content.",
            ))
    return tuple(fixtures)
