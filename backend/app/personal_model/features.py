from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Action, Plan, PlanBlock, StateObservation, TrainingExample, UserProfile
from app.personal_model.schemas import EXTRACTION_VERSION, FEATURE_SCHEMA_VERSION

TERMINAL_STATUSES = {"completed", "partially_completed", "skipped", "missed", "cancelled"}
FEATURE_FORBIDDEN_KEYS = {
    "status",
    "completed",
    "skipped",
    "missed",
    "actual_duration_minutes",
    "started_at",
    "finished_at",
    "outcome_reason",
    "post_energy_delta",
    "post_mental_state_delta",
}


@dataclass(frozen=True)
class ExtractedExample:
    feature_json: dict[str, Any]
    label_json: dict[str, Any]
    provenance_json: dict[str, Any]
    decision_at: datetime
    plan_id: str
    plan_block_id: str
    source_action_id: str | None
    domain: str | None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _bucket(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _state_band(energy: int, mental_state: int) -> str:
    average = round((energy + mental_state) / 2)
    if average >= 70:
        return "HIGH"
    if average >= 50:
        return "MEDIUM"
    if average >= 35:
        return "LOW"
    return "VERY_LOW"


def _metadata_int(action: Action | None, key: str, default: int) -> int:
    if action is None or not isinstance(action.metadata_json, dict):
        return default
    value = action.metadata_json.get(key)
    if isinstance(value, (int, float)):
        return max(0, min(100, round(value)))
    return default


def _latest_observation_before(db: Session, user: UserProfile, observation_type: str, before: datetime) -> StateObservation | None:
    return db.scalar(
        select(StateObservation)
        .where(StateObservation.user_id == user.id, StateObservation.observation_type == observation_type, StateObservation.observed_at <= before)
        .order_by(StateObservation.observed_at.desc(), StateObservation.created_at.desc())
    )


def _post_state_delta(db: Session, user: UserProfile, block: PlanBlock) -> dict[str, Any]:
    end = _aware(block.finished_at or block.ends_at)
    if end is None:
        return {"valid": False, "reason": "no_end"}
    window_end = end + timedelta(hours=4)
    start = _latest_observation_before(db, user, "energy", _aware(block.starts_at) or end)
    start_mental = _latest_observation_before(db, user, "mental_state", _aware(block.starts_at) or end)
    post_energy = db.scalar(
        select(StateObservation)
        .where(StateObservation.user_id == user.id, StateObservation.observation_type == "energy", StateObservation.observed_at > end, StateObservation.observed_at <= window_end)
        .order_by(StateObservation.observed_at.asc(), StateObservation.created_at.asc())
    )
    post_mental = db.scalar(
        select(StateObservation)
        .where(StateObservation.user_id == user.id, StateObservation.observation_type == "mental_state", StateObservation.observed_at > end, StateObservation.observed_at <= window_end)
        .order_by(StateObservation.observed_at.asc(), StateObservation.created_at.asc())
    )
    if not start or not start_mental or not post_energy or not post_mental:
        return {"valid": False, "reason": "missing_pair"}
    return {
        "valid": True,
        "post_window_hours": 4,
        "energy_delta": round(post_energy.value - start.value, 2),
        "mental_state_delta": round(post_mental.value - start_mental.value, 2),
        "pre_observation_ids": {"energy": start.id, "mental_state": start_mental.id},
        "post_observation_ids": {"energy": post_energy.id, "mental_state": post_mental.id},
    }


def _plan_blocks_before(plan: Plan, block: PlanBlock) -> list[PlanBlock]:
    return [item for item in plan.blocks if item.starts_at < block.starts_at]


def _example_from_block(db: Session, user: UserProfile, plan: Plan, block: PlanBlock) -> ExtractedExample | None:
    if block.block_type != "generated_action" or block.status not in TERMINAL_STATUSES:
        return None
    decision_at = _aware(plan.generated_at) or _aware(block.created_at) or datetime.now(UTC)
    action = db.get(Action, block.action_id) if block.action_id else None
    energy = int(plan.summary_metrics.get("energy") or 60)
    mental_state = int(plan.summary_metrics.get("mental_state") or 60)
    start = _aware(block.starts_at)
    started = _aware(block.started_at)
    finished = _aware(block.finished_at)
    prior_blocks = _plan_blocks_before(plan, block)
    context_switches = sum(
        1
        for index in range(1, len(prior_blocks))
        if prior_blocks[index].domain and prior_blocks[index - 1].domain and prior_blocks[index].domain != prior_blocks[index - 1].domain
    )
    deadline = _aware(action.deadline) if action else None
    deadline_days = round((deadline - decision_at).total_seconds() / 86400, 2) if deadline else None
    feature_json = {
        "domain": block.domain,
        "source_type": block.source_type,
        "commitment_level": block.commitment_level,
        "planned_duration_minutes": block.duration_minutes,
        "planned_start_hour": block.starts_at.hour,
        "original_planned_start_hour": block.original_starts_at.hour if block.original_starts_at else block.starts_at.hour,
        "manually_moved": bool(block.user_modified and block.original_starts_at),
        "user_locked": block.user_locked,
        "day_of_week": block.starts_at.weekday(),
        "time_of_day_bucket": _bucket(block.starts_at.hour),
        "latest_energy": energy,
        "latest_mental_state": mental_state,
        "state_band": _state_band(energy, mental_state),
        "activation_difficulty": _metadata_int(action, "activation_difficulty", 35),
        "cognitive_load": _metadata_int(action, "cognitive_load", 45),
        "physical_load": _metadata_int(action, "physical_load", 25),
        "location": action.location if action else None,
        "context": action.context if action else None,
        "recent_planned_load_minutes": sum(item.duration_minutes for item in prior_blocks if item.block_type == "generated_action"),
        "context_switches_before_block": context_switches,
        "deadline_days": deadline_days,
        "variant": block.variant_type or (action.metadata_json or {}).get("variant") if action and isinstance(action.metadata_json, dict) else block.variant_type,
        "reduced_or_minimum_variant": block.variant_type in {"reduced", "minimum", "activation"} or (bool((action.metadata_json or {}).get("minimum_variant", False)) if action and isinstance(action.metadata_json, dict) else False),
        "planner_version": plan.planner_version,
        "active_model_versions": (plan.personal_model_snapshot or {}).get("active_model_ids", {}),
    }
    label_json = {
        "started": started is not None or block.status in {"completed", "partially_completed"},
        "start_delay_minutes": round((started - start).total_seconds() / 60, 2) if started and start else None,
        "completed": block.status == "completed",
        "skipped": block.status == "skipped",
        "missed": block.status == "missed",
        "completion_ratio": min(1.5, round((block.actual_duration_minutes or 0) / max(block.duration_minutes, 1), 3)) if block.status in {"completed", "partially_completed"} else 0,
        "actual_duration_minutes": block.actual_duration_minutes,
        "state_transition": _post_state_delta(db, user, block),
    }
    provenance_json = {
        "user_id": user.id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "extraction_version": EXTRACTION_VERSION,
        "decision_timestamp": decision_at.isoformat(),
        "plan_id": plan.id,
        "plan_block_id": block.id,
        "source_action_id": block.action_id,
        "domain": block.domain,
        "label_source": "plan_block_execution",
        "state_observation_ids": {
            "plan_state_observed_at": plan.summary_metrics.get("state_observed_at"),
        },
        "planner_version": plan.planner_version,
        "model_versions_at_planning": (plan.personal_model_snapshot or {}).get("active_model_ids", {}),
    }
    return ExtractedExample(
        feature_json=feature_json,
        label_json=label_json,
        provenance_json=provenance_json,
        decision_at=decision_at,
        plan_id=plan.id,
        plan_block_id=block.id,
        source_action_id=block.action_id,
        domain=block.domain,
    )


def validate_no_target_leakage(feature_json: dict[str, Any]) -> None:
    leaked = sorted(FEATURE_FORBIDDEN_KEYS.intersection(feature_json.keys()))
    if leaked:
        raise ValueError(f"Feature payload contains label/future keys: {', '.join(leaked)}")


def extract_examples(db: Session, user: UserProfile) -> list[ExtractedExample]:
    plans = list(
        db.scalars(
            select(Plan)
            .where(Plan.user_id == user.id)
            .order_by(Plan.generated_at.asc(), Plan.created_at.asc())
        ).all()
    )
    examples: list[ExtractedExample] = []
    seen_blocks: set[str] = set()
    for plan in plans:
        for block in plan.blocks:
            if block.id in seen_blocks:
                continue
            seen_blocks.add(block.id)
            example = _example_from_block(db, user, plan, block)
            if example is None:
                continue
            validate_no_target_leakage(example.feature_json)
            examples.append(example)
    return examples


def persist_examples(db: Session, user: UserProfile, examples: list[ExtractedExample]) -> list[TrainingExample]:
    rows: list[TrainingExample] = []
    for example in examples:
        row = db.scalar(
            select(TrainingExample).where(
                TrainingExample.user_id == user.id,
                TrainingExample.feature_schema_version == FEATURE_SCHEMA_VERSION,
                TrainingExample.plan_block_id == example.plan_block_id,
            )
        )
        if row is None:
            row = TrainingExample(
                user_id=user.id,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                extraction_version=EXTRACTION_VERSION,
                decision_at=example.decision_at,
                plan_id=example.plan_id,
                plan_block_id=example.plan_block_id,
                source_action_id=example.source_action_id,
                source_entity_type="action" if example.source_action_id else None,
                source_entity_id=example.source_action_id,
                domain=example.domain,
                label_source="plan_block_execution",
                feature_json=example.feature_json,
                label_json=example.label_json,
                provenance_json=example.provenance_json,
                status="active",
            )
            db.add(row)
        else:
            row.extraction_version = EXTRACTION_VERSION
            row.decision_at = example.decision_at
            row.feature_json = example.feature_json
            row.label_json = example.label_json
            row.provenance_json = example.provenance_json
            row.domain = example.domain
            row.status = "active"
            row.version += 1
        rows.append(row)
    db.flush()
    return rows
