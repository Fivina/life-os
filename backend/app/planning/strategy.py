from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Action, Plan, PlanBlock, UserProfile
from app.events.service import append_event
from app.planning.engine import BLOCK_GENERATED_ACTION, BLOCK_HARD_COMMITMENT, CorePlannerV03
from app.planning.schemas import PlanGenerateRequest
from app.planning.service import _action_candidate, _preserved_blocks, _summary, assemble_planning_context
from app.planning.types import CandidateAction, PlannedBlock
from app.strategy.schemas import ExamTrajectorySnapshot, ProposalModificationRequest


SIMULATION_VERSION = "planner-strategic-simulation-v1"


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _block_snapshot(block: PlanBlock) -> dict[str, Any]:
    return jsonable_encoder({
        "id": block.id,
        "action_id": block.action_id,
        "commitment_id": block.commitment_id,
        "source_type": block.source_type,
        "source_id": block.source_id,
        "domain": block.domain,
        "title": block.title,
        "starts_at": block.starts_at,
        "ends_at": block.ends_at,
        "duration_minutes": block.duration_minutes,
        "block_type": block.block_type,
        "commitment_level": block.commitment_level,
        "movable": block.movable,
        "status": block.status,
        "action_group_id": block.action_group_id,
        "variant_type": block.variant_type,
        "frozen_until": block.frozen_until,
        "user_locked": block.user_locked,
        "user_modified": block.user_modified,
        "original_starts_at": block.original_starts_at,
        "started_at": block.started_at,
        "finished_at": block.finished_at,
        "actual_duration_minutes": block.actual_duration_minutes,
        "outcome_reason": block.outcome_reason,
        "note": block.note,
        "residual_minutes": block.residual_minutes,
    })


def _candidate_snapshot(block: PlannedBlock) -> dict[str, Any]:
    data = asdict(block)
    data["decision_factors"] = [asdict(item) for item in block.decision_factors]
    return jsonable_encoder(data)


def _identity(block: dict[str, Any]) -> str:
    return str(block.get("action_id") or block.get("commitment_id") or f"{block.get('block_type')}:{block.get('title')}:{block.get('starts_at')}")


def _time_key(value: Any) -> str | None:
    if value in (None, ""):
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return _aware(parsed).isoformat()


def _diff(current_blocks: list[dict[str, Any]], candidate_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {_identity(item): item for item in current_blocks}
    candidate = {_identity(item): item for item in candidate_blocks}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(candidate)):
        before, after = current.get(key), candidate.get(key)
        if before is None and after is not None:
            changes.append({"change_type": "ADD_RECOVERY_BLOCK", "entity_ref": key, "before": None, "after": after})
        elif after is None and before is not None and before.get("block_type") == BLOCK_GENERATED_ACTION:
            change_type = "REMOVE_OPTIONAL_ALLOCATION" if before.get("commitment_level") == "optional" else "REALLOCATE"
            changes.append({"change_type": change_type, "entity_ref": key, "before": before, "after": None})
        elif before is not None and after is not None:
            if before.get("starts_at") != after.get("starts_at"):
                changes.append({"change_type": "MOVE", "entity_ref": key, "before": before, "after": after})
            elif before.get("duration_minutes") != after.get("duration_minutes"):
                change_type = "INCREASE" if int(after.get("duration_minutes") or 0) > int(before.get("duration_minutes") or 0) else "DECREASE"
                changes.append({"change_type": change_type, "entity_ref": key, "before": before, "after": after})
            elif before.get("variant_type") != after.get("variant_type"):
                changes.append({"change_type": "CHANGE_REQUIREMENT_VARIANT", "entity_ref": key, "before": before, "after": after})
    return changes


def _protected_signature(block: dict[str, Any]) -> tuple[Any, ...]:
    return (
        block.get("action_id"), block.get("commitment_id"), block.get("title"), _time_key(block.get("starts_at")),
        _time_key(block.get("ends_at")), block.get("duration_minutes"), block.get("block_type"),
    )


def simulate_strategic_recovery(
    db: Session,
    user: UserProfile,
    current_plan: Plan,
    snapshot: ExamTrajectorySnapshot,
    *,
    modification: ProposalModificationRequest | None = None,
    planning_now: datetime | None = None,
) -> dict[str, Any]:
    """Run Planner V2 against a bounded strategic adjustment without persisting a plan."""
    now = _aware(planning_now or datetime.now(UTC))
    payload = PlanGenerateRequest(
        planning_date=current_plan.planning_day,
        timezone="Europe/Berlin",
        expected_world_revision=user.world_revision,
    )
    context = assemble_planning_context(db, user, payload)
    target_actions = list(db.scalars(
        select(Action).where(
            Action.user_id == user.id,
            Action.status == "active",
            Action.source_entity_type == "exam",
            Action.source_entity_id == snapshot.exam_id,
        ).order_by(Action.variant_rank.desc(), Action.estimated_minutes.desc())
    ))
    candidates = list(context.candidate_actions)
    candidate_ids = {item.source_action_id for item in candidates}
    for action in target_actions:
        if action.id not in candidate_ids:
            candidates.append(_action_candidate(action, None))

    requested = modification.requested_target_minutes if modification and modification.requested_target_minutes else max(
        30,
        min(180, snapshot.projected_shortfall_minutes or max(0, (snapshot.remaining_workload_minutes or 0) - snapshot.planned_future_minutes)),
    )
    best_target = next((item for item in candidates if item.source_action_id in {action.id for action in target_actions}), None)
    if best_target is not None:
        boosted = replace(
            best_target,
            estimated_minutes=max(best_target.estimated_minutes, requested),
            maximum_minutes=max(best_target.maximum_minutes, requested),
            minimum_minutes=min(best_target.minimum_minutes, requested),
            commitment_level="goal_critical",
            trajectory_value=max(95, best_target.trajectory_value),
            neglect_cost=max(70, best_target.neglect_cost),
            activation_difficulty=max(0, best_target.activation_difficulty - 8),
            metadata={**best_target.metadata, "strategic_recovery": True, "requested_minutes": requested},
        )
        candidates = [boosted if item.source_action_id == best_target.source_action_id else item for item in candidates]

    if modification:
        minimums = modification.minimum_exam_minutes
        if minimums:
            action_exam = {
                action.id: action.source_entity_id
                for action in db.scalars(select(Action).where(Action.user_id == user.id, Action.source_entity_type == "exam"))
            }
            candidates = [
                replace(item, minimum_minutes=max(item.minimum_minutes, min(item.maximum_minutes, minimums[action_exam[item.source_action_id]])))
                if item.source_action_id in action_exam and action_exam[item.source_action_id] in minimums
                else item
                for item in candidates
            ]

    preserved = _preserved_blocks(current_plan, now)
    explicit_protected = set(modification.protected_block_ids if modification else ())
    already = {(item.action_id, item.commitment_id, item.starts_at) for item in preserved}
    for block in current_plan.blocks:
        if block.id not in explicit_protected:
            continue
        key = (block.action_id, block.commitment_id, _aware(block.starts_at))
        if key in already or block.block_type == BLOCK_HARD_COMMITMENT:
            continue
        preserved.append(PlannedBlock(
            title=block.title, block_type=block.block_type, starts_at=_aware(block.starts_at), ends_at=_aware(block.ends_at),
            duration_minutes=block.duration_minutes, source_type=block.source_type, source_id=block.source_id,
            domain=block.domain, commitment_level=block.commitment_level, movable=block.movable,
            action_id=block.action_id, commitment_id=block.commitment_id, action_group_id=block.action_group_id,
            variant_type=block.variant_type, frozen_until=_aware(block.frozen_until) if block.frozen_until else None,
            user_locked=True, user_modified=block.user_modified, original_starts_at=_aware(block.original_starts_at) if block.original_starts_at else None,
            status=block.status, started_at=_aware(block.started_at) if block.started_at else None,
            finished_at=_aware(block.finished_at) if block.finished_at else None, actual_duration_minutes=block.actual_duration_minutes,
            outcome_reason=block.outcome_reason, note=block.note, residual_minutes=block.residual_minutes,
        ))

    simulation_context = replace(context, candidate_actions=candidates, preserved_blocks=preserved)
    result = CorePlannerV03().run(simulation_context)
    current_blocks = [_block_snapshot(item) for item in sorted(current_plan.blocks, key=lambda row: (_aware(row.starts_at), row.id))]
    candidate_blocks = [_candidate_snapshot(item) for item in result.blocks]
    protected = [
        item for item in current_blocks
        if item["user_locked"] or item["user_modified"] or item["block_type"] == BLOCK_HARD_COMMITMENT or item["id"] in explicit_protected
    ]
    candidate_signatures = {_protected_signature(item) for item in candidate_blocks}
    if any(_protected_signature(item) not in candidate_signatures for item in protected):
        raise ValueError("Planner simulation would alter a protected block.")

    action_exam = {
        action.id: action.source_entity_id
        for action in db.scalars(select(Action).where(Action.user_id == user.id, Action.source_entity_type == "exam"))
    }
    def exam_minutes(blocks: list[dict[str, Any]], exam_id: str) -> int:
        return sum(int(item.get("duration_minutes") or 0) for item in blocks if action_exam.get(item.get("action_id")) == exam_id)

    current_target = exam_minutes(current_blocks, snapshot.exam_id)
    proposed_target = exam_minutes(candidate_blocks, snapshot.exam_id)
    affected_exam_ids = sorted({exam_id for exam_id in action_exam.values() if exam_id})
    exam_effects = []
    for exam_id in affected_exam_ids:
        before, after = exam_minutes(current_blocks, exam_id), exam_minutes(candidate_blocks, exam_id)
        if before != after:
            exam_effects.append({"exam_id": exam_id, "current_minutes": before, "proposed_minutes": after, "delta_minutes": after - before})
    remaining = snapshot.remaining_workload_minutes or 0
    expected_effects = {
        "target_exam_id": snapshot.exam_id,
        "scheduled_minutes": {"current": current_target, "proposed": proposed_target, "delta": proposed_target - current_target},
        "projected_shortfall_minutes": {"current": max(0, remaining - current_target), "proposed": max(0, remaining - proposed_target)},
        "scheduled_coverage": {
            "current": round(min(1.0, current_target / remaining), 3) if remaining else 1.0,
            "proposed": round(min(1.0, proposed_target / remaining), 3) if remaining else 1.0,
        },
        "exam_allocation_effects": exam_effects,
        "protected_blocks_changed": 0,
    }
    tradeoffs = [
        {"type": "EXAM_BUFFER", "exam_id": item["exam_id"], "delta_minutes": item["delta_minutes"]}
        for item in exam_effects if item["exam_id"] != snapshot.exam_id and item["delta_minutes"] < 0
    ]
    if result.stress.band != current_plan.summary_metrics.get("planning_load"):
        tradeoffs.append({"type": "PLANNING_DENSITY", "current": current_plan.summary_metrics.get("planning_load"), "proposed": result.stress.band})

    return jsonable_encoder({
        "simulation_version": SIMULATION_VERSION,
        "planner_version": result.planner_version,
        "generated_from_world_revision": result.generated_from_world_revision,
        "planning_date": result.planning_date,
        "horizon_start": result.horizon_start,
        "horizon_end": result.horizon_end,
        "blocks": candidate_blocks,
        "summary_metrics": _summary(result, simulation_context),
        "overload_status": result.overload_status,
        "shortfall_minutes": result.shortfall_minutes,
        "overload": result.overload,
        "changes": _diff(current_blocks, candidate_blocks),
        "expected_effects": expected_effects,
        "tradeoffs": tradeoffs,
        "protected_block_signatures": [list(_protected_signature(item)) for item in protected],
        "requested_target_minutes": requested,
    })


def apply_strategy_candidate(
    db: Session,
    user: UserProfile,
    *,
    current_plan_id: str,
    current_plan_version: int,
    expected_world_revision: int,
    candidate: dict[str, Any],
    proposal_id: str,
) -> Plan:
    """Planner-owned publication path for an explicitly accepted candidate snapshot."""
    current = db.scalar(
        select(Plan)
        .where(Plan.id == current_plan_id, Plan.user_id == user.id)
        .options(selectinload(Plan.blocks))
        .with_for_update()
    )
    if current is None or current.status != "current" or current.version != current_plan_version:
        raise ValueError("Proposal is stale because the current plan changed.")
    signatures = {tuple(item) for item in candidate.get("protected_block_signatures", [])}
    current_protected = {
        _protected_signature(_block_snapshot(block))
        for block in current.blocks
        if block.user_locked or block.user_modified or block.block_type == BLOCK_HARD_COMMITMENT
    }
    candidate_signatures = {_protected_signature(item) for item in candidate.get("blocks", [])}
    if not current_protected.issubset(signatures) or not current_protected.issubset(candidate_signatures):
        raise ValueError("Proposal is stale because a protected block changed.")

    current.status = "superseded"
    current.version += 1
    plan = Plan(
        user_id=user.id,
        planner_version=str(candidate["planner_version"]),
        generated_from_world_revision=user.world_revision,
        status="current",
        planning_day=datetime.fromisoformat(str(candidate["planning_date"])).date() if "T" in str(candidate["planning_date"]) else datetime.strptime(str(candidate["planning_date"]), "%Y-%m-%d").date(),
        horizon_start=datetime.fromisoformat(candidate["horizon_start"]),
        horizon_end=datetime.fromisoformat(candidate["horizon_end"]),
        generated_at=datetime.now(UTC),
        previous_plan_id=current.id,
        replan_reason="accepted_strategic_proposal",
        control_loop_version=current.control_loop_version,
        plan_diff={"proposal_id": proposal_id, "changes": candidate.get("changes", [])},
        last_replanned_at=datetime.now(UTC),
        summary_metrics=candidate.get("summary_metrics", {}),
        decision_factors={"items": []},
        personal_model_snapshot=current.personal_model_snapshot,
        personal_model_revision=current.personal_model_revision,
        overload_status=candidate.get("overload_status", "feasible"),
        shortfall_minutes=int(candidate.get("shortfall_minutes") or 0),
        overload_json=candidate.get("overload", {}),
    )
    db.add(plan)
    db.flush()
    for item in candidate.get("blocks", []):
        db.add(PlanBlock(
            user_id=user.id, plan_id=plan.id, action_id=item.get("action_id"), commitment_id=item.get("commitment_id"),
            source_type=item.get("source_type") or "planner", source_id=item.get("source_id"), domain=item.get("domain"),
            title=item.get("title") or "", starts_at=datetime.fromisoformat(item["starts_at"]), ends_at=datetime.fromisoformat(item["ends_at"]),
            duration_minutes=int(item.get("duration_minutes") or 0), block_type=item.get("block_type") or BLOCK_GENERATED_ACTION,
            commitment_level=item.get("commitment_level"), movable=bool(item.get("movable", True)), status=item.get("status") or "planned",
            source="planner", decision_factors={"items": item.get("decision_factors", [])}, action_group_id=item.get("action_group_id"),
            variant_type=item.get("variant_type"), frozen_until=datetime.fromisoformat(item["frozen_until"]) if item.get("frozen_until") else None,
            user_locked=bool(item.get("user_locked", False)), user_modified=bool(item.get("user_modified", False)),
            original_starts_at=datetime.fromisoformat(item["original_starts_at"]) if item.get("original_starts_at") else None,
            started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
            finished_at=datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,
            actual_duration_minutes=item.get("actual_duration_minutes"), outcome_reason=item.get("outcome_reason"), note=item.get("note"),
            residual_minutes=int(item.get("residual_minutes") or 0),
        ))
    db.flush()
    append_event(
        db, user, event_type="plan.proposal_applied", aggregate_type="plan", aggregate_id=plan.id,
        payload={"plan_id": plan.id, "previous_plan_id": current.id, "proposal_id": proposal_id}, outbox=True,
    )
    return plan
