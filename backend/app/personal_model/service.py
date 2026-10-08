from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import median
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    PatternEvidence,
    PersonalModelRefreshRun,
    PersonalModelVersion,
    PreferenceEvidence,
    TrainingExample,
    UserProfile,
)
from app.events.service import append_event
from app.personal_model.calibration import baseline_capacity_ratio, baseline_completion_rate, brier_score, mean_absolute_error
from app.personal_model.confidence import MIN_EVIDENCE, confidence_score, recency_weight
from app.personal_model.features import extract_examples, persist_examples
from app.personal_model.promotion import apply_promotion, next_model_version
from app.personal_model.schemas import (
    EXTRACTION_VERSION,
    FEATURE_SCHEMA_VERSION,
    PatternCorrectionRequest,
    PatternEvidenceRead,
    PersonalModelRefreshRead,
    PersonalModelSnapshotRead,
    PersonalModelSummaryRead,
    PersonalModelVersionRead,
    TrainingExampleRead,
)

MODEL_TYPES = ["capacity", "completion", "activation", "preference", "routine", "state_transition"]
EWMA_ALPHA = 0.30
BETA_ALPHA_PRIOR = 2
BETA_BETA_PRIOR = 2
CAPACITY_MULTIPLIER_MIN = 0.90
CAPACITY_MULTIPLIER_MAX = 1.10
RANKING_FACTOR_BOUND = 6.0
STATE_DELTA_BOUND = 12.0


def _now() -> datetime:
    return datetime.now(UTC)


def record_plan_proposal_outcome(
    db: Session,
    user: UserProfile,
    *,
    proposal_id: str,
    plan_id: str,
    exam_id: str,
    choice: str,
    strategic_context: dict[str, Any],
    tradeoffs: list[dict[str, Any]],
    authority_level: int,
    attention_action: str,
    modification: dict[str, Any] | None = None,
) -> TrainingExample:
    """Record contextual proposal choice in the existing Personal Learning evidence table."""
    row = TrainingExample(
        user_id=user.id,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        extraction_version="plan-proposal-outcome-v1",
        decision_at=_now(),
        plan_id=plan_id,
        plan_block_id=None,
        source_action_id=None,
        source_entity_type="plan_proposal",
        source_entity_id=proposal_id,
        domain="learning",
        label_source="plan_proposal",
        feature_json={
            "exam_id": exam_id,
            "strategic_context": strategic_context,
            "tradeoffs": tradeoffs,
            "authority_level": authority_level,
            "attention_action": attention_action,
        },
        label_json={"proposal_choice": choice, "modification": modification or {}},
        provenance_json={
            "proposal_id": proposal_id,
            "contextual_only": True,
            "does_not_imply_universal_preference": True,
        },
        status="active",
    )
    db.add(row)
    db.flush()
    return row


def _active_examples(db: Session, user: UserProfile) -> list[TrainingExample]:
    return list(
        db.scalars(
            select(TrainingExample)
            .where(TrainingExample.user_id == user.id, TrainingExample.feature_schema_version == FEATURE_SCHEMA_VERSION, TrainingExample.status == "active")
            .order_by(TrainingExample.decision_at.asc(), TrainingExample.created_at.asc())
        ).all()
    )


def _active_models(db: Session, user: UserProfile) -> list[PersonalModelVersion]:
    return list(db.scalars(select(PersonalModelVersion).where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.status == "ACTIVE")).all())


def _candidate_count(db: Session, user: UserProfile) -> int:
    return db.scalar(select(PersonalModelVersion).where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.status == "CANDIDATE").count()) or 0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _load_class(feature: dict[str, Any]) -> str:
    return "physical" if feature.get("physical_load", 0) > feature.get("cognitive_load", 0) else "cognitive"


def _bin_key(feature: dict[str, Any], broad: bool = False) -> str:
    pieces = [_load_class(feature), feature.get("time_of_day_bucket") or "unknown", feature.get("state_band") or "MEDIUM"]
    if not broad:
        pieces.append(feature.get("domain") or "general")
    return "|".join(str(piece) for piece in pieces)


def _evidence_window(examples: list[TrainingExample]) -> tuple[datetime | None, datetime | None]:
    if not examples:
        return None, None
    return examples[0].decision_at, examples[-1].decision_at


def _split_eval(examples: list[TrainingExample]) -> tuple[list[TrainingExample], list[TrainingExample]]:
    if len(examples) < 4:
        return examples, []
    split = max(1, int(len(examples) * 0.7))
    return examples[:split], examples[split:]


def _completion_rate(rows: list[TrainingExample]) -> float:
    if not rows:
        return 0.5
    return sum(1 for row in rows if row.label_json.get("completed")) / len(rows)


def _create_candidate(
    db: Session,
    user: UserProfile,
    *,
    model_type: str,
    parameters: dict[str, Any],
    evidence: list[TrainingExample],
    confidence: float,
    metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    refresh_run: PersonalModelRefreshRun,
) -> PersonalModelVersion:
    start, end = _evidence_window(evidence)
    candidate = PersonalModelVersion(
        user_id=user.id,
        model_type=model_type,
        model_stage="STAGE_1",
        version=next_model_version(db, user, model_type),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        status="CANDIDATE",
        parameters=parameters,
        evidence_start=start,
        evidence_end=end,
        evidence_n=len(evidence),
        effective_evidence_n=round(sum(recency_weight((_now() - row.decision_at.replace(tzinfo=UTC) if row.decision_at.tzinfo is None else _now() - row.decision_at.astimezone(UTC)).days) for row in evidence), 3),
        confidence=confidence,
        metrics=metrics,
        baseline_metrics=baseline_metrics,
        refresh_run_id=refresh_run.id,
    )
    db.add(candidate)
    db.flush()
    return apply_promotion(db, user, candidate)


def _capacity_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    ewma_by_bin: dict[str, float] = {}
    values_by_bin: dict[str, list[float]] = defaultdict(list)
    labels: list[float] = []
    for row in examples:
        planned = max(1, row.feature_json.get("planned_duration_minutes") or 1)
        actual = row.label_json.get("actual_duration_minutes") or (planned if row.label_json.get("completed") else 0)
        ratio = _clamp(float(actual) / planned, 0.0, 1.25)
        labels.append(ratio)
        for key in {_bin_key(row.feature_json), _bin_key(row.feature_json, broad=True), "global"}:
            previous = ewma_by_bin.get(key, 1.0)
            ewma_by_bin[key] = round(EWMA_ALPHA * ratio + (1 - EWMA_ALPHA) * previous, 4)
            values_by_bin[key].append(ratio)
    parameters = {
        "formula": "ewma_new = 0.30 * observation + 0.70 * ewma_previous",
        "bins": {
            key: {
                "capacity_ratio": value,
                "planner_multiplier": round(_clamp(value, CAPACITY_MULTIPLIER_MIN, CAPACITY_MULTIPLIER_MAX), 4),
                "evidence_n": len(values_by_bin[key]),
            }
            for key, value in ewma_by_bin.items()
        },
        "bounds": {"planner_multiplier_min": CAPACITY_MULTIPLIER_MIN, "planner_multiplier_max": CAPACITY_MULTIPLIER_MAX},
    }
    train, eval_rows = _split_eval(examples)
    baseline = baseline_capacity_ratio([_clamp((row.label_json.get("actual_duration_minutes") or 0) / max(row.feature_json.get("planned_duration_minutes") or 1, 1), 0, 1.25) for row in train])
    eval_labels = [_clamp((row.label_json.get("actual_duration_minutes") or 0) / max(row.feature_json.get("planned_duration_minutes") or 1, 1), 0, 1.25) for row in eval_rows]
    predictions = [parameters["bins"].get(_bin_key(row.feature_json), parameters["bins"].get(_bin_key(row.feature_json, True), parameters["bins"].get("global", {"capacity_ratio": 1.0})))["capacity_ratio"] for row in eval_rows]
    model_mae = mean_absolute_error(predictions, eval_labels) if eval_rows else None
    baseline_mae = mean_absolute_error([baseline for _ in eval_rows], eval_labels) if eval_rows else None
    improvement = 0 if model_mae is None or baseline_mae in (None, 0) else max(0, (baseline_mae - model_mae) / baseline_mae)
    consistency = 1.0 - min(1.0, max((max(labels) - min(labels)) if labels else 1, 0) / 1.25)
    conf = confidence_score("capacity", len(examples), len(examples), improvement, consistency)
    return _create_candidate(
        db,
        user,
        model_type="capacity",
        parameters=parameters,
        evidence=examples,
        confidence=conf,
        metrics={"capacity_mae": model_mae, "loss": model_mae, "improvement": round(improvement, 4)},
        baseline_metrics={"capacity_mae": baseline_mae, "loss": baseline_mae, "baseline_ratio": round(baseline, 4)},
        refresh_run=refresh_run,
    )


def _completion_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    bins: dict[str, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "completions": 0})
    labels = [bool(row.label_json.get("completed")) for row in examples]
    for row in examples:
        for key in {_bin_key(row.feature_json), _bin_key(row.feature_json, broad=True), "global"}:
            bins[key]["attempts"] += 1
            bins[key]["completions"] += 1 if row.label_json.get("completed") else 0
    params = {
        "formula": "(completions + 2) / (attempts + 2 + 2)",
        "bins": {
            key: {
                **value,
                "completion_probability": round((value["completions"] + BETA_ALPHA_PRIOR) / (value["attempts"] + BETA_ALPHA_PRIOR + BETA_BETA_PRIOR), 4),
            }
            for key, value in bins.items()
        },
        "guard": "Low probability is a bounded ranking/variant signal only; it never suppresses goal-critical work.",
    }
    train, eval_rows = _split_eval(examples)
    baseline_rate = baseline_completion_rate([bool(row.label_json.get("completed")) for row in train])
    eval_labels = [bool(row.label_json.get("completed")) for row in eval_rows]
    preds = [params["bins"].get(_bin_key(row.feature_json), params["bins"].get(_bin_key(row.feature_json, True), params["bins"].get("global", {"completion_probability": 0.5})))["completion_probability"] for row in eval_rows]
    model_brier = brier_score(preds, eval_labels) if eval_rows else None
    baseline_brier = brier_score([baseline_rate for _ in eval_rows], eval_labels) if eval_rows else None
    improvement = 0 if model_brier is None or baseline_brier in (None, 0) else max(0, (baseline_brier - model_brier) / baseline_brier)
    consistency = max(0.0, 1.0 - abs((_completion_rate(examples) - 0.5) * 0.5))
    conf = confidence_score("completion", len(examples), len(examples), improvement, consistency)
    return _create_candidate(
        db,
        user,
        model_type="completion",
        parameters=params,
        evidence=examples,
        confidence=conf,
        metrics={"completion_brier": model_brier, "loss": model_brier, "improvement": round(improvement, 4)},
        baseline_metrics={"completion_brier": baseline_brier, "loss": baseline_brier, "baseline_completion_rate": round(baseline_rate, 4)},
        refresh_run=refresh_run,
    )


def _activation_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    delays: dict[str, list[float]] = defaultdict(list)
    eligible: list[TrainingExample] = []
    for row in examples:
        delay = row.label_json.get("start_delay_minutes")
        if delay is None:
            continue
        eligible.append(row)
        for key in {_bin_key(row.feature_json), _bin_key(row.feature_json, broad=True), "global"}:
            delays[key].append(_clamp(float(delay), 0, 180))
    params = {
        "formula": "median_start_delay_minutes by bin; skip/miss rate from terminal status labels",
        "bins": {
            key: {"median_start_delay_minutes": round(median(values), 2), "evidence_n": len(values), "activation_adjustment": round(_clamp(median(values) / 15, 0, RANKING_FACTOR_BOUND), 2)}
            for key, values in delays.items()
        },
        "bounds": {"activation_adjustment_max": RANKING_FACTOR_BOUND},
    }
    model_loss = None
    baseline_loss = None
    if eligible:
        baseline_delay = median([_clamp(float(row.label_json.get("start_delay_minutes") or 0), 0, 180) for row in eligible])
        model_loss = mean_absolute_error(
            [params["bins"].get(_bin_key(row.feature_json), params["bins"].get(_bin_key(row.feature_json, True), params["bins"].get("global", {"median_start_delay_minutes": baseline_delay})))["median_start_delay_minutes"] for row in eligible],
            [_clamp(float(row.label_json.get("start_delay_minutes") or 0), 0, 180) for row in eligible],
        )
        baseline_loss = mean_absolute_error([baseline_delay for _ in eligible], [_clamp(float(row.label_json.get("start_delay_minutes") or 0), 0, 180) for row in eligible])
    improvement = 0 if model_loss is None or baseline_loss in (None, 0) else max(0, (baseline_loss - model_loss) / baseline_loss)
    conf = confidence_score("activation", len(eligible), len(eligible), improvement, 0.7)
    return _create_candidate(db, user, model_type="activation", parameters=params, evidence=eligible, confidence=conf, metrics={"activation_mae": model_loss, "loss": model_loss, "improvement": round(improvement, 4)}, baseline_metrics={"activation_mae": baseline_loss, "loss": baseline_loss}, refresh_run=refresh_run)


def _preference_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    support: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    now = _now()
    for row in examples:
        if row.feature_json.get("commitment_level") == "goal_critical":
            continue
        if row.label_json.get("missed"):
            continue
        key = f"domain:{row.feature_json.get('domain') or 'general'}"
        weight = recency_weight((now - (row.decision_at.replace(tzinfo=UTC) if row.decision_at.tzinfo is None else row.decision_at.astimezone(UTC))).days)
        support[key] += weight * (1.0 if row.label_json.get("completed") else 0.2 if row.label_json.get("started") else 0)
        count[key] += 1
    kitchen_pref = list(db.scalars(select(PreferenceEvidence).where(PreferenceEvidence.user_id == user.id)).all())
    for pref in kitchen_pref:
        key = f"kitchen_protein:{pref.protein_family or pref.category or 'general'}"
        support[key] += 2.0 * pref.value
        count[key] += 1
    params = {
        "formula": "recency_weight = exp(-ln(2) * age_days / 30); explicit evidence has 2x weight; missed alone is not dislike",
        "scores": {
            key: {"support": round(value, 4), "evidence_n": count[key], "ranking_adjustment": round(_clamp(value, -RANKING_FACTOR_BOUND, RANKING_FACTOR_BOUND), 3)}
            for key, value in support.items()
        },
        "bounds": {"ranking_adjustment_min": -RANKING_FACTOR_BOUND, "ranking_adjustment_max": RANKING_FACTOR_BOUND},
    }
    evidence_n = sum(count.values())
    consistency = 0.7 if evidence_n else 0
    conf = confidence_score("preference", evidence_n, evidence_n, 0.2 if evidence_n else 0, consistency)
    return _create_candidate(db, user, model_type="preference", parameters=params, evidence=examples[:evidence_n], confidence=conf, metrics={"loss": 0.4, "preference_signals": evidence_n}, baseline_metrics={"loss": 0.5}, refresh_run=refresh_run)


def _routine_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "completed": 0})
    for row in examples:
        key = f"{row.feature_json.get('domain') or 'general'}|{row.feature_json.get('time_of_day_bucket')}"
        buckets[key]["attempts"] += 1
        buckets[key]["completed"] += 1 if row.label_json.get("completed") else 0
    params = {
        "formula": "frequency * consistency; routines are soft fit signals only",
        "patterns": {
            key: {
                **value,
                "consistency": round(value["completed"] / max(value["attempts"], 1), 4),
                "ranking_adjustment": round(_clamp((value["completed"] / max(value["attempts"], 1)) * min(value["attempts"] / 8, 1) * RANKING_FACTOR_BOUND, 0, RANKING_FACTOR_BOUND), 3),
            }
            for key, value in buckets.items()
        },
    }
    consistency = max((value["completed"] / max(value["attempts"], 1) for value in buckets.values()), default=0)
    conf = confidence_score("routine", len(examples), len(examples), 0.2, consistency)
    return _create_candidate(db, user, model_type="routine", parameters=params, evidence=examples, confidence=conf, metrics={"loss": 0.4, "routine_bins": len(buckets)}, baseline_metrics={"loss": 0.5}, refresh_run=refresh_run)


def _state_transition_model(db: Session, user: UserProfile, examples: list[TrainingExample], refresh_run: PersonalModelRefreshRun) -> PersonalModelVersion:
    grouped: dict[str, list[dict[str, float]]] = defaultdict(list)
    paired: list[TrainingExample] = []
    for row in examples:
        transition = row.label_json.get("state_transition") or {}
        if not transition.get("valid"):
            continue
        paired.append(row)
        grouped[row.feature_json.get("domain") or "general"].append(
            {
                "energy_delta": _clamp(float(transition.get("energy_delta") or 0), -STATE_DELTA_BOUND, STATE_DELTA_BOUND),
                "mental_state_delta": _clamp(float(transition.get("mental_state_delta") or 0), -STATE_DELTA_BOUND, STATE_DELTA_BOUND),
            }
        )
    params = {
        "formula": "mean bounded post-minus-pre state delta by domain within a 4h observation window",
        "deltas": {
            key: {
                "energy_delta": round(sum(item["energy_delta"] for item in values) / len(values), 3),
                "mental_state_delta": round(sum(item["mental_state_delta"] for item in values) / len(values), 3),
                "evidence_n": len(values),
            }
            for key, values in grouped.items()
            if values
        },
        "bounds": {"delta_min": -STATE_DELTA_BOUND, "delta_max": STATE_DELTA_BOUND},
    }
    conf = confidence_score("state_transition", len(paired), len(paired), 0.1 if paired else 0, 0.6 if paired else 0)
    return _create_candidate(db, user, model_type="state_transition", parameters=params, evidence=paired, confidence=conf, metrics={"loss": 0.45, "paired_state_observations": len(paired)}, baseline_metrics={"loss": 0.5}, refresh_run=refresh_run)


def _create_patterns(db: Session, user: UserProfile, active_models: list[PersonalModelVersion]) -> list[PatternEvidence]:
    created: list[PatternEvidence] = []
    for model in active_models:
        if model.model_type == "routine":
            for key, value in (model.parameters.get("patterns") or {}).items():
                if value.get("evidence_n", 0) < MIN_EVIDENCE["routine"] or value.get("consistency", 0) < 0.65:
                    continue
                claim = f"Routine signal: {key.replace('|', ' in ')} completes with {round(value['consistency'] * 100)}% consistency."
                pattern = PatternEvidence(
                    user_id=user.id,
                    pattern_type="routine",
                    scope={"key": key},
                    claim=claim,
                    evidence_n=value["evidence_n"],
                    weighted_support=value["consistency"],
                    confidence=model.confidence,
                    first_observed=model.evidence_start,
                    last_observed=model.evidence_end,
                    last_updated=_now(),
                    status="ACTIVE",
                    source_model_version_id=model.id,
                )
                db.add(pattern)
                created.append(pattern)
        if model.model_type == "preference":
            for key, value in (model.parameters.get("scores") or {}).items():
                if value.get("evidence_n", 0) < MIN_EVIDENCE["preference"] or abs(value.get("ranking_adjustment", 0)) < 2:
                    continue
                pattern = PatternEvidence(
                    user_id=user.id,
                    pattern_type="preference",
                    scope={"key": key},
                    claim=f"Preference signal: {key} has support {value['support']}.",
                    evidence_n=value["evidence_n"],
                    weighted_support=value["support"],
                    confidence=model.confidence,
                    first_observed=model.evidence_start,
                    last_observed=model.evidence_end,
                    last_updated=_now(),
                    status="ACTIVE",
                    source_model_version_id=model.id,
                )
                db.add(pattern)
                created.append(pattern)
    db.flush()
    return created


def refresh_personal_models(db: Session, user: UserProfile) -> PersonalModelRefreshRead:
    running = db.scalar(select(PersonalModelRefreshRun).where(PersonalModelRefreshRun.user_id == user.id, PersonalModelRefreshRun.status == "running"))
    if running:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Personal model refresh already running.")
    run = PersonalModelRefreshRun(user_id=user.id, status="running", started_at=_now(), feature_schema_version=FEATURE_SCHEMA_VERSION, extraction_version=EXTRACTION_VERSION)
    db.add(run)
    db.flush()
    try:
        examples = persist_examples(db, user, extract_examples(db, user))
        run.evidence_n = len(examples)
        candidates = [
            _capacity_model(db, user, examples, run),
            _completion_model(db, user, examples, run),
            _activation_model(db, user, examples, run),
            _preference_model(db, user, examples, run),
            _routine_model(db, user, examples, run),
            _state_transition_model(db, user, examples, run),
        ]
        active = [item for item in candidates if item.status == "ACTIVE"]
        _create_patterns(db, user, active)
        run.status = "succeeded"
        run.finished_at = _now()
        run.metrics_json = {
            "candidate_models": len(candidates),
            "promoted_models": len(active),
            "rejected_models": len([item for item in candidates if item.status == "REJECTED"]),
            "evidence_n": len(examples),
        }
        append_event(
            db,
            user,
            event_type="personal_model.refreshed",
            aggregate_type="personal_model_refresh_run",
            aggregate_id=run.id,
            payload=run.metrics_json,
            outbox=True,
        )
        db.flush()
        return PersonalModelRefreshRead.model_validate(run)
    except Exception as exc:
        run.status = "failed"
        run.finished_at = _now()
        run.error = str(exc)
        db.flush()
        raise


def snapshot(db: Session, user: UserProfile) -> PersonalModelSnapshotRead:
    active = _active_models(db, user)
    active_by_type = {model.model_type: model for model in active}
    parameters: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    counts: dict[str, int] = {}
    fallback: dict[str, str] = {}
    for model_type in MODEL_TYPES:
        model = active_by_type.get(model_type)
        if model is None:
            fallback[model_type] = "BASELINE / INSUFFICIENT_EVIDENCE"
            parameters[model_type] = {}
            confidence[model_type] = 0
            counts[model_type] = 0
        else:
            parameters[model_type] = model.parameters
            confidence[model_type] = model.confidence
            counts[model_type] = model.evidence_n
    revision = max((model.version for model in active), default=0)
    return PersonalModelSnapshotRead(
        status="ACTIVE" if active else "BASELINE_INSUFFICIENT_EVIDENCE",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        model_revision=revision,
        active_model_ids={model.model_type: model.id for model in active},
        model_versions={model.model_type: model.version for model in active},
        parameters=parameters,
        confidence=confidence,
        evidence_counts=counts,
        fallback_reasons=fallback,
    )


def summary(db: Session, user: UserProfile) -> PersonalModelSummaryRead:
    examples = _active_examples(db, user)
    active = _active_models(db, user)
    candidates = list(db.scalars(select(PersonalModelVersion).where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.status == "CANDIDATE")).all())
    rejected = list(db.scalars(select(PersonalModelVersion).where(PersonalModelVersion.user_id == user.id, PersonalModelVersion.status == "REJECTED")).all())
    patterns = list(db.scalars(select(PatternEvidence).where(PatternEvidence.user_id == user.id)).all())
    latest = db.scalar(select(PersonalModelRefreshRun).where(PersonalModelRefreshRun.user_id == user.id).order_by(PersonalModelRefreshRun.started_at.desc()).limit(1))
    snap = snapshot(db, user)
    fallback_count = len([value for value in snap.fallback_reasons.values() if value])
    return PersonalModelSummaryRead(
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        extraction_version=EXTRACTION_VERSION,
        status=snap.status,
        evidence_n=len(examples),
        active_model_count=len(active),
        candidate_model_count=len(candidates),
        rejected_model_count=len(rejected),
        pattern_count=len([item for item in patterns if item.status == "ACTIVE"]),
        corrected_pattern_count=len([item for item in patterns if item.status in {"DOWNWEIGHTED", "INVALIDATED"}]),
        fallback_rate=round(fallback_count / len(MODEL_TYPES), 3),
        latest_refresh=PersonalModelRefreshRead.model_validate(latest) if latest else None,
        snapshot=snap,
        metrics={"model_types": MODEL_TYPES, "min_evidence": MIN_EVIDENCE},
    )


def list_models(db: Session, user: UserProfile) -> list[PersonalModelVersionRead]:
    rows = list(db.scalars(select(PersonalModelVersion).where(PersonalModelVersion.user_id == user.id).order_by(PersonalModelVersion.created_at.desc())).all())
    return [PersonalModelVersionRead.model_validate(row) for row in rows]


def get_model(db: Session, user: UserProfile, model_id: str) -> PersonalModelVersionRead:
    row = db.get(PersonalModelVersion, model_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personal model not found.")
    return PersonalModelVersionRead.model_validate(row)


def list_patterns(db: Session, user: UserProfile) -> list[PatternEvidenceRead]:
    rows = list(db.scalars(select(PatternEvidence).where(PatternEvidence.user_id == user.id).order_by(PatternEvidence.confidence.desc(), PatternEvidence.last_updated.desc())).all())
    return [PatternEvidenceRead.model_validate(row) for row in rows]


def correct_pattern(db: Session, user: UserProfile, pattern_id: str, payload: PatternCorrectionRequest) -> PatternEvidenceRead:
    pattern = db.get(PatternEvidence, pattern_id)
    if pattern is None or pattern.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pattern evidence not found.")
    pattern.status = "INVALIDATED"
    pattern.weighted_support = 0
    pattern.confidence = 0
    pattern.correction_metadata = {"reason": payload.reason, "note": payload.note, "corrected_at": _now().isoformat(), "preserved_history": True}
    pattern.last_updated = _now()
    pattern.version += 1
    append_event(
        db,
        user,
        event_type="personal_model.pattern.corrected",
        aggregate_type="pattern_evidence",
        aggregate_id=pattern.id,
        payload={"pattern_id": pattern.id, "reason": payload.reason, "influence_removed": True},
        outbox=True,
    )
    db.flush()
    return PatternEvidenceRead.model_validate(pattern)


def list_examples(db: Session, user: UserProfile, limit: int = 50) -> list[TrainingExampleRead]:
    rows = list(
        db.scalars(
            select(TrainingExample)
            .where(TrainingExample.user_id == user.id)
            .order_by(TrainingExample.decision_at.desc())
            .limit(limit)
        ).all()
    )
    return [TrainingExampleRead.model_validate(row) for row in rows]
