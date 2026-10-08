from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.planning.types import (
    CandidateAction,
    CapacityEstimate,
    DecisionFactor,
    PlannedBlock,
    PlanningContext,
    PlanningResult,
    ScoredCandidate,
    StressEstimate,
    TimeInterval,
    UnscheduledAction,
)

BLOCK_HARD_COMMITMENT = "hard_commitment"
BLOCK_GENERATED_ACTION = "generated_action"
BLOCK_SLACK = "slack"

STRESS_THRESHOLD = 68
LEARNED_RANKING_BOUND = 6.0


def _naive_pair(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    if (left.tzinfo is None) != (right.tzinfo is None):
        return left.replace(tzinfo=None), right.replace(tzinfo=None)
    return left, right


def _max_datetime(*values: datetime) -> datetime:
    current = values[0]
    for value in values[1:]:
        left, right = _naive_pair(current, value)
        if right > left:
            current = value
    return current


def _min_datetime(*values: datetime) -> datetime:
    current = values[0]
    for value in values[1:]:
        left, right = _naive_pair(current, value)
        if right < left:
            current = value
    return current


def _overlaps(left: TimeInterval, right: TimeInterval) -> bool:
    left_start, right_end = _naive_pair(left.start, right.end)
    right_start, left_end = _naive_pair(right.start, left.end)
    return left_start < right_end and right_start < left_end


def _add_minutes(value: datetime, minutes: int) -> datetime:
    return value + timedelta(minutes=minutes)


def _align_timezone(value: datetime | None, reference: datetime) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _state_band(energy: int, mental_state: int) -> str:
    average = round((energy + mental_state) / 2)
    if average >= 70:
        return "HIGH"
    if average >= 50:
        return "MEDIUM"
    if average >= 35:
        return "LOW"
    return "VERY_LOW"


def _time_bucket(value: datetime) -> str:
    if 5 <= value.hour < 12:
        return "morning"
    if 12 <= value.hour < 17:
        return "afternoon"
    if 17 <= value.hour < 22:
        return "evening"
    return "night"


def _load_class(candidate: CandidateAction) -> str:
    return "physical" if candidate.physical_load > candidate.cognitive_load else "cognitive"


def _learned_parameters(context: PlanningContext, model_type: str) -> dict[str, Any]:
    snapshot = context.personal_model_snapshot or {}
    params = snapshot.get("parameters", {}) if isinstance(snapshot, dict) else {}
    value = params.get(model_type, {}) if isinstance(params, dict) else {}
    return value if isinstance(value, dict) else {}


def _model_note(context: PlanningContext, model_type: str) -> str:
    snapshot = context.personal_model_snapshot or {}
    ids = snapshot.get("active_model_ids", {}) if isinstance(snapshot, dict) else {}
    confidence = snapshot.get("confidence", {}) if isinstance(snapshot, dict) else {}
    model_id = ids.get(model_type) if isinstance(ids, dict) else None
    conf = confidence.get(model_type, 0) if isinstance(confidence, dict) else 0
    return f"PersonalModel {model_type} id={model_id or 'baseline'} confidence={conf}."


def _candidate_bin(context: PlanningContext, candidate: CandidateAction, slot: datetime, *, broad: bool = False) -> str:
    parts = [_load_class(candidate), _time_bucket(slot), _state_band(context.energy, context.mental_state)]
    if not broad:
        parts.append(candidate.domain)
    return "|".join(parts)


def _learned_completion_probability(context: PlanningContext, candidate: CandidateAction, slot: datetime) -> float | None:
    bins = (_learned_parameters(context, "completion").get("bins") or {})
    for key in (_candidate_bin(context, candidate, slot), _candidate_bin(context, candidate, slot, broad=True), "global"):
        value = bins.get(key)
        if isinstance(value, dict) and "completion_probability" in value:
            return float(value["completion_probability"])
    return None


def _learned_capacity_multiplier(context: PlanningContext) -> tuple[float, str | None]:
    bins = (_learned_parameters(context, "capacity").get("bins") or {})
    load_class = "cognitive"
    broad = "|".join([load_class, _time_bucket(context.generated_at), _state_band(context.energy, context.mental_state)])
    for key in (broad, "global"):
        value = bins.get(key)
        if isinstance(value, dict) and "planner_multiplier" in value:
            return max(0.9, min(1.1, float(value["planner_multiplier"]))), key
    return 1.0, None


class CorePlannerV03:
    """Deterministic Planner V2 with bounded Action x Variant x Slot evaluation."""

    def run(self, context: PlanningContext) -> PlanningResult:
        settings = get_settings()
        hard_blocks = self._hard_commitment_blocks(context) + list(context.preserved_blocks)
        free_intervals = self.free_intervals(context.horizon_start, context.horizon_end, hard_blocks)
        capacity = self.capacity_estimate(context, free_intervals)
        scored_candidates = [self.score_candidate(context, candidate) for candidate in context.candidate_actions]
        scored_candidates.sort(
            key=lambda item: (
                -item.score,
                item.candidate.deadline or datetime.max.replace(tzinfo=context.horizon_start.tzinfo),
                item.candidate.domain,
                item.candidate.title.lower(),
                item.candidate.source_action_id,
            )
        )

        generated_blocks, unscheduled = self._place_actions(context, scored_candidates, hard_blocks, capacity)
        slack_blocks = self._slack_blocks(context, hard_blocks + generated_blocks, capacity.required_slack_minutes)
        blocks = sorted(hard_blocks + generated_blocks + slack_blocks, key=lambda block: (block.starts_at, block.block_type, block.title))
        stress = self.stress_estimate(context, blocks, capacity)

        if stress.value > stress.threshold:
            generated_blocks, unscheduled = self._trim_to_stress_budget(context, generated_blocks, unscheduled, scored_candidates, hard_blocks, capacity)
            slack_blocks = self._slack_blocks(context, hard_blocks + generated_blocks, capacity.required_slack_minutes)
            blocks = sorted(hard_blocks + generated_blocks + slack_blocks, key=lambda block: (block.starts_at, block.block_type, block.title))
            stress = self.stress_estimate(context, blocks, capacity)

        plan_factors = [
            DecisionFactor("state_band", 0, capacity.state_band),
            DecisionFactor("usable_flexible_minutes", capacity.usable_flexible_minutes),
            DecisionFactor("required_slack_minutes", capacity.required_slack_minutes),
            DecisionFactor("stress_estimate", stress.value, stress.band),
            DecisionFactor(
                "personal_model_snapshot",
                context.personal_model_snapshot.get("model_revision", 0) if isinstance(context.personal_model_snapshot, dict) else 0,
                f"Active personal models: {context.personal_model_snapshot.get('active_model_ids', {}) if isinstance(context.personal_model_snapshot, dict) else {}}",
            ),
        ]
        required_by_group: dict[str, int] = {}
        for candidate in context.candidate_actions:
            group = candidate.action_group_id or candidate.source_action_id
            required_by_group[group] = max(required_by_group.get(group, 0), candidate.allocated_minutes or candidate.estimated_minutes)
        scheduled_by_group: dict[str, int] = {}
        for block in generated_blocks:
            group = block.action_group_id or block.action_id or ""
            scheduled_by_group[group] = scheduled_by_group.get(group, 0) + block.duration_minutes
        required_minutes = sum(required_by_group.values())
        scheduled_minutes = sum(min(required, scheduled_by_group.get(group, 0)) for group, required in required_by_group.items())
        shortfall = max(0, required_minutes - scheduled_minutes)
        overload_status = "overloaded" if shortfall > 0 else "tight" if scheduled_minutes > capacity.usable_flexible_minutes * 0.85 else "feasible"
        if shortfall and any(candidate.deadline and _align_timezone(candidate.deadline, context.horizon_end) <= context.horizon_end for candidate in context.candidate_actions):
            overload_status = "impossible_before_deadline"
        overload = {
            "status": overload_status,
            "required_minutes": required_minutes,
            "available_minutes": capacity.usable_flexible_minutes,
            "scheduled_minutes": scheduled_minutes,
            "shortfall_minutes": shortfall,
            "conflicts": [item.name for item in context.constraints if item.strength == "hard"],
        }
        return PlanningResult(
            planner_version=settings.planner_version,
            generated_from_world_revision=context.generated_from_world_revision,
            planning_date=context.planning_date,
            horizon_start=context.horizon_start,
            horizon_end=context.horizon_end,
            capacity=capacity,
            stress=stress,
            blocks=blocks,
            unscheduled_actions=unscheduled,
            decision_factors=plan_factors,
            warnings=["Required work exceeds feasible capacity."] if shortfall else [],
            overload_status=overload_status,
            shortfall_minutes=shortfall,
            overload=overload,
        )

    def _hard_commitment_blocks(self, context: PlanningContext) -> list[PlannedBlock]:
        blocks: list[PlannedBlock] = []
        for commitment in context.hard_commitments:
            commitment_start = _align_timezone(commitment.starts_at, context.horizon_start)
            commitment_end = _align_timezone(commitment.ends_at, context.horizon_start)
            starts_at = _max_datetime(commitment_start, context.horizon_start)
            ends_at = _min_datetime(commitment_end, context.horizon_end)
            if starts_at >= ends_at:
                continue
            blocks.append(
                PlannedBlock(
                    title=commitment.title,
                    block_type=BLOCK_HARD_COMMITMENT,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    duration_minutes=int((ends_at - starts_at).total_seconds() // 60),
                    source_type="commitment",
                    source_id=commitment.id,
                    domain="commitment",
                    commitment_level=commitment.level,
                    movable=False,
                    commitment_id=commitment.id,
                    decision_factors=[DecisionFactor("hard_commitment", 0, "Fixed canonical commitment is preserved.")],
                )
            )
        return blocks

    def free_intervals(self, horizon_start: datetime, horizon_end: datetime, blocks: list[PlannedBlock]) -> list[TimeInterval]:
        intervals = [TimeInterval(horizon_start, horizon_end)]
        occupied = sorted([TimeInterval(block.starts_at, block.ends_at) for block in blocks], key=lambda item: item.start)
        for busy in occupied:
            next_intervals: list[TimeInterval] = []
            for interval in intervals:
                if not _overlaps(interval, busy):
                    next_intervals.append(interval)
                    continue
                if interval.start < busy.start:
                    next_intervals.append(TimeInterval(interval.start, _min_datetime(busy.start, interval.end)))
                if busy.end < interval.end:
                    next_intervals.append(TimeInterval(_max_datetime(busy.end, interval.start), interval.end))
            intervals = [interval for interval in next_intervals if interval.minutes > 0]
        return intervals

    def capacity_estimate(self, context: PlanningContext, free_intervals: list[TimeInterval]) -> CapacityEstimate:
        available = sum(interval.minutes for interval in free_intervals)
        average_state = max(0, min(100, round((context.energy + context.mental_state) / 2)))
        if average_state >= 70:
            state_band, capacity_ratio, slack_ratio, min_slack = "high", 0.78, 0.15, 45
        elif average_state >= 50:
            state_band, capacity_ratio, slack_ratio, min_slack = "medium", 0.60, 0.22, 75
        elif average_state >= 35:
            state_band, capacity_ratio, slack_ratio, min_slack = "low", 0.42, 0.35, 120
        else:
            state_band, capacity_ratio, slack_ratio, min_slack = "very_low", 0.28, 0.45, 150
        required_slack = min(available, max(min_slack, round(available * slack_ratio)))
        usable = max(0, min(available - required_slack, round(available * capacity_ratio)))
        multiplier, _ = _learned_capacity_multiplier(context)
        settings = get_settings()
        multiplier = max(settings.planner_capacity_floor, min(settings.planner_capacity_ceiling, multiplier))
        usable = max(0, min(available - required_slack, round(usable * multiplier)))
        return CapacityEstimate(
            average_state=average_state,
            available_minutes=available,
            required_slack_minutes=required_slack,
            usable_flexible_minutes=usable,
            capacity_ratio=capacity_ratio,
            slack_ratio=slack_ratio,
            state_band=state_band,
        )

    def score_candidate(self, context: PlanningContext, candidate: CandidateAction, slot: datetime | None = None) -> ScoredCandidate:
        evaluated_slot = slot or context.horizon_start
        factors: list[DecisionFactor] = []
        level_value = {"goal_critical": 34, "maintenance": 21, "optional": 6}.get(candidate.commitment_level, 10)
        factors.append(DecisionFactor("commitment_level", level_value, candidate.commitment_level))
        factors.append(DecisionFactor("trajectory_value", candidate.trajectory_value))
        factors.append(DecisionFactor("deadline_urgency", self._deadline_urgency(context, candidate)))
        factors.append(DecisionFactor("neglect_cost", candidate.neglect_cost))
        factors.append(DecisionFactor("maintenance_value", candidate.maintenance_value))
        factors.append(DecisionFactor("stress_cost", -candidate.stress_cost))
        factors.append(DecisionFactor("activation_cost", -self._activation_cost(context, candidate)))
        factors.append(DecisionFactor("capacity_mismatch_cost", -self._capacity_mismatch_cost(context, candidate)))
        factors.append(DecisionFactor("context_switch_cost", -self._context_switch_cost(candidate)))
        factors.append(DecisionFactor("time_cost", -round(candidate.estimated_minutes / 12, 2)))
        factors.extend(self._learned_factors(context, candidate, evaluated_slot))
        return ScoredCandidate(candidate=candidate, score=round(sum(item.contribution for item in factors), 2), factors=factors)

    def _learned_factors(self, context: PlanningContext, candidate: CandidateAction, slot: datetime) -> list[DecisionFactor]:
        factors: list[DecisionFactor] = []
        probability = _learned_completion_probability(context, candidate, slot)
        if probability is not None:
            contribution = max(-LEARNED_RANKING_BOUND, min(LEARNED_RANKING_BOUND, round((probability - 0.5) * 10, 2)))
            if candidate.commitment_level == "goal_critical" and contribution < 0:
                contribution = max(contribution, -1.0)
            factors.append(DecisionFactor("learned_completion_fit", contribution, _model_note(context, "completion")))

        activation_bins = (_learned_parameters(context, "activation").get("bins") or {})
        for key in (_candidate_bin(context, candidate, slot), _candidate_bin(context, candidate, slot, broad=True), "global"):
            value = activation_bins.get(key)
            if isinstance(value, dict) and "activation_adjustment" in value:
                factors.append(DecisionFactor("learned_activation_cost", -min(LEARNED_RANKING_BOUND, float(value["activation_adjustment"])), _model_note(context, "activation")))
                break

        preference_scores = (_learned_parameters(context, "preference").get("scores") or {})
        pref = preference_scores.get(f"domain:{candidate.domain}")
        if isinstance(pref, dict):
            factors.append(DecisionFactor("learned_preference_fit", max(-LEARNED_RANKING_BOUND, min(LEARNED_RANKING_BOUND, float(pref.get("ranking_adjustment", 0)))), _model_note(context, "preference")))

        routine_patterns = (_learned_parameters(context, "routine").get("patterns") or {})
        routine_key = f"{candidate.domain}|{_time_bucket(slot)}"
        routine = routine_patterns.get(routine_key)
        if isinstance(routine, dict):
            evidence = [item for item in context.behavior_patterns if (item.get("scope") or {}).get("key") == routine_key]
            invalidated = any(item.get("status") != "ACTIVE" for item in evidence)
            active = [item for item in evidence if item.get("status") == "ACTIVE"]
            if not invalidated or active:
                model_confidence = float((context.personal_model_snapshot.get("confidence") or {}).get("routine", 0))
                pattern_confidence = max((float(item.get("confidence") or 0) for item in active), default=model_confidence)
                evidence_scale = min(1.0, max(0.0, pattern_confidence))
                contribution = min(LEARNED_RANKING_BOUND, float(routine.get("ranking_adjustment", 0)) * evidence_scale)
                factors.append(DecisionFactor("learned_routine_fit", round(contribution, 2), f"Future slot {slot.isoformat()} uses {routine_key}; confidence={round(evidence_scale, 3)}."))
        factors.append(DecisionFactor("future_slot_weekday", 0, f"weekday={slot.weekday()} bucket={_time_bucket(slot)}"))
        return factors

    def _deadline_urgency(self, context: PlanningContext, candidate: CandidateAction) -> int:
        deadline = _align_timezone(candidate.deadline, context.generated_at)
        if deadline is None:
            return 0
        seconds_until = (deadline - context.generated_at).total_seconds()
        days_until = seconds_until / 86400
        if days_until < 0:
            return 32
        if days_until <= 1:
            return 30
        if days_until <= 3:
            return 22
        if days_until <= 7:
            return 12
        return 4

    def _activation_cost(self, context: PlanningContext, candidate: CandidateAction) -> int:
        multiplier = 0.32 if min(context.energy, context.mental_state) >= 50 else 0.55
        return round(candidate.activation_difficulty * multiplier)

    def _capacity_mismatch_cost(self, context: PlanningContext, candidate: CandidateAction) -> int:
        state = (context.energy + context.mental_state) / 2
        load = max(candidate.cognitive_load, candidate.physical_load)
        if state >= 70:
            return max(0, round((load - 80) / 5))
        if state >= 50:
            return max(0, round((load - 65) / 4))
        return max(0, round((load - 45) / 2.5))

    def _context_switch_cost(self, candidate: CandidateAction) -> int:
        if candidate.context:
            return 2
        return 4 if candidate.domain in {"admin", "kitchen", "home"} else 3

    def _block_size(self, context: PlanningContext, candidate: CandidateAction) -> int:
        if candidate.mutually_exclusive:
            return max(candidate.minimum_minutes, min(candidate.maximum_minutes, candidate.estimated_minutes))
        average_state = (context.energy + context.mental_state) / 2
        if average_state >= 70:
            target = candidate.estimated_minutes
        elif average_state >= 50:
            target = min(candidate.estimated_minutes, 90)
        elif candidate.commitment_level == "goal_critical":
            target = min(candidate.estimated_minutes, 45)
        elif candidate.commitment_level == "maintenance":
            target = min(candidate.estimated_minutes, 35)
        else:
            target = min(candidate.estimated_minutes, 25)
        target = max(candidate.minimum_minutes, min(candidate.maximum_minutes, target))
        probability = _learned_completion_probability(context, candidate, context.horizon_start)
        if probability is not None and probability < 0.45:
            reduced = max(candidate.minimum_minutes, min(target, 45))
            if candidate.commitment_level == "goal_critical":
                target = reduced
            elif candidate.commitment_level == "maintenance":
                target = max(candidate.minimum_minutes, min(target, 35))
        return max(1, round(target))

    def _place_actions(
        self,
        context: PlanningContext,
        scored_candidates: list[ScoredCandidate],
        hard_blocks: list[PlannedBlock],
        capacity: CapacityEstimate,
    ) -> tuple[list[PlannedBlock], list[UnscheduledAction]]:
        settings = get_settings()
        blocks: list[PlannedBlock] = []
        unscheduled: list[UnscheduledAction] = []
        occupied = hard_blocks.copy()
        scheduled_minutes = 0
        groups: dict[str, list[CandidateAction]] = {}
        preserved_groups = {
            block.action_group_id or block.action_id
            for block in hard_blocks
            if block.block_type == BLOCK_GENERATED_ACTION and block.status in {"planned", "in_progress", "completed"} and (block.action_group_id or block.action_id)
        }
        for scored in scored_candidates:
            candidate = scored.candidate
            group_id = candidate.action_group_id or candidate.source_action_id
            if group_id in preserved_groups:
                continue
            groups.setdefault(group_id, []).append(candidate)

        remaining = dict(sorted(groups.items()))
        while remaining:
            choices: list[tuple[float, str, CandidateAction, TimeInterval, list[DecisionFactor]]] = []
            for group_id, variants in remaining.items():
                for candidate in sorted(variants, key=lambda item: (-item.variant_rank, item.source_action_id)):
                    if not self._variant_allowed_for_state(context, candidate):
                        continue
                    if candidate.variant_type == "activation" and not self._activation_variant_allowed(context, candidate):
                        continue
                    duration = self._block_size(context, candidate)
                    if candidate.allocated_minutes is not None:
                        duration = min(duration, max(candidate.minimum_minutes, candidate.allocated_minutes))
                    if scheduled_minutes + duration > capacity.usable_flexible_minutes:
                        continue
                    for slot in self._candidate_slots(context, occupied, candidate, duration)[: settings.planner_max_slots_per_candidate]:
                        factors = self._placement_factors(context, candidate, slot, occupied, duration)
                        if any(item.factor == "hard_constraint_violation" for item in factors):
                            continue
                        scored = self.score_candidate(context, candidate, slot.start)
                        quality_bonus = round(candidate.variant_quality * 8 + candidate.variant_rank * 0.35, 2)
                        all_factors = scored.factors + factors + [
                            DecisionFactor("variant_quality", quality_bonus, candidate.variant_type),
                            DecisionFactor("block_size", duration, "Selected deterministic execution variant."),
                        ]
                        score = round(sum(item.contribution for item in all_factors), 2)
                        choices.append((score, group_id, candidate, slot, all_factors))
            if not choices:
                for group_id, variants in remaining.items():
                    representative = sorted(variants, key=lambda item: (-item.variant_rank, item.source_action_id))[0]
                    required = representative.allocated_minutes or representative.estimated_minutes
                    unscheduled.append(UnscheduledAction(representative.source_action_id, representative.title, "capacity_or_constraint_limit", 0, required, max(0, capacity.usable_flexible_minutes - scheduled_minutes), required, "at_risk"))
                break
            choices.sort(key=lambda item: (-item[0], item[3].start, -item[2].variant_rank, item[2].source_action_id))
            score, group_id, candidate, placement, factors = choices[0]
            proposed = PlannedBlock(
                title=candidate.title,
                block_type=BLOCK_GENERATED_ACTION,
                starts_at=placement.start,
                ends_at=placement.end,
                duration_minutes=placement.minutes,
                source_type="action",
                source_id=candidate.source_action_id,
                domain=candidate.domain,
                commitment_level=candidate.commitment_level,
                movable=True,
                action_id=candidate.source_action_id,
                action_group_id=group_id,
                variant_type=candidate.variant_type,
                original_starts_at=placement.start,
                decision_factors=factors,
            )
            projected_stress = self.stress_estimate(context, occupied + [proposed], capacity)
            if projected_stress.value > projected_stress.threshold:
                variants = remaining.pop(group_id)
                representative = variants[0]
                unscheduled.append(UnscheduledAction(representative.source_action_id, representative.title, "stress_limit", score, representative.estimated_minutes, 0, representative.estimated_minutes, "at_risk"))
                continue
            blocks.append(proposed)
            occupied.append(proposed)
            scheduled_minutes += proposed.duration_minutes
            remaining.pop(group_id)
        return blocks, unscheduled

    def _variant_allowed_for_state(self, context: PlanningContext, candidate: CandidateAction) -> bool:
        if not candidate.mutually_exclusive or candidate.variant_type is None:
            return True
        average_state = (context.energy + context.mental_state) / 2
        if average_state >= 70:
            return True
        if average_state >= 50:
            return candidate.variant_type != "full"
        if average_state >= 35:
            return candidate.variant_type in {"reduced", "minimum", "activation"}
        return candidate.variant_type in {"minimum", "activation"}

    def _activation_variant_allowed(self, context: PlanningContext, candidate: CandidateAction) -> bool:
        probability = _learned_completion_probability(context, candidate, context.horizon_start)
        low_state = min(context.energy, context.mental_state) < 45
        late_day = context.horizon_start.hour >= 18
        return low_state or late_day or (probability is not None and probability < 0.4) or candidate.debt_minutes > 0

    def _candidate_slots(self, context: PlanningContext, occupied: list[PlannedBlock], candidate: CandidateAction, duration: int) -> list[TimeInterval]:
        settings = get_settings()
        free = self.free_intervals(context.horizon_start, context.horizon_end, occupied)
        earliest = _max_datetime(context.horizon_start, _align_timezone(candidate.earliest_start, context.horizon_start) or context.horizon_start)
        latest_end = _min_datetime(context.horizon_end, _align_timezone(candidate.deadline, context.horizon_end) or context.horizon_end)
        latest_start = _align_timezone(candidate.latest_start, context.horizon_start)
        slots: list[TimeInterval] = []
        for interval in free:
            start = _max_datetime(interval.start, earliest)
            minute_remainder = start.minute % settings.planner_slot_granularity_minutes
            if minute_remainder:
                start = start + timedelta(minutes=settings.planner_slot_granularity_minutes - minute_remainder)
            while _add_minutes(start, duration) <= _min_datetime(interval.end, latest_end):
                if latest_start is not None and start > latest_start:
                    break
                slots.append(TimeInterval(start, _add_minutes(start, duration)))
                start = _add_minutes(start, settings.planner_slot_granularity_minutes)
        return slots

    def _placement_factors(self, context: PlanningContext, candidate: CandidateAction, slot: TimeInterval, occupied: list[PlannedBlock], duration: int) -> list[DecisionFactor]:
        factors: list[DecisionFactor] = []
        depends_on = candidate.metadata.get("depends_on_action_id") if isinstance(candidate.metadata, dict) else None
        if depends_on:
            dependency = next((block for block in occupied if block.action_id == depends_on), None)
            if dependency is None:
                factors.append(DecisionFactor("hard_constraint_violation", -1000, f"Dependency {depends_on} must be scheduled first."))
            elif slot.start < dependency.ends_at:
                factors.append(DecisionFactor("hard_constraint_violation", -1000, "Dependent work cannot start before its prerequisite finishes."))
            else:
                factors.append(DecisionFactor("dependency_order", 8, "Prerequisite is scheduled before this block."))
        bucket = _time_bucket(slot.start)
        for constraint in context.constraints:
            if constraint.domain and constraint.domain != candidate.domain:
                continue
            overlaps = bool(constraint.starts_at and constraint.ends_at and _overlaps(slot, TimeInterval(_align_timezone(constraint.starts_at, slot.start), _align_timezone(constraint.ends_at, slot.start))))
            violation = constraint.constraint_type == "unavailable_window" and overlaps
            if constraint.constraint_type == "required_context" and constraint.payload.get("context") not in {candidate.context, candidate.location}:
                violation = True
            if violation and constraint.strength == "hard":
                factors.append(DecisionFactor("hard_constraint_violation", -1000, f"{constraint.provenance}: {constraint.name}"))
            elif violation:
                factors.append(DecisionFactor("preference_violation", -abs(constraint.penalty), f"{constraint.provenance}: {constraint.name}"))
            elif constraint.constraint_type == "preferred_time_bucket" and constraint.payload.get("bucket"):
                contribution = 5 if constraint.payload["bucket"] == bucket else -min(8, abs(constraint.penalty))
                factors.append(DecisionFactor("preferred_slot", contribution, f"{constraint.provenance}: {constraint.name}"))
        previous = max((block for block in occupied if block.ends_at <= slot.start), key=lambda block: block.ends_at, default=None)
        following = min((block for block in occupied if block.starts_at >= slot.end), key=lambda block: block.starts_at, default=None)
        if previous and previous.domain == candidate.domain:
            factors.append(DecisionFactor("adjacency_bonus", 3, "Adjacent work remains in the same domain."))
        elif previous and previous.domain not in {None, "commitment", "recovery", candidate.domain}:
            factors.append(DecisionFactor("context_switch_cost", -4, f"Switch from {previous.domain} to {candidate.domain}."))
        gaps = []
        if previous:
            gaps.append(max(0, int((slot.start - previous.ends_at).total_seconds() // 60)))
        if following:
            gaps.append(max(0, int((following.starts_at - slot.end).total_seconds() // 60)))
        tiny_gaps = [gap for gap in gaps if 0 < gap < 30]
        if tiny_gaps:
            factors.append(DecisionFactor("fragmentation_cost", -min(8, len(tiny_gaps) * 3), f"Small gaps: {tiny_gaps}."))
        preferred = candidate.estimated_minutes
        factors.append(DecisionFactor("duration_fit", max(-6, 4 - abs(preferred - duration) / 15), f"preferred={preferred} selected={duration}"))
        if candidate.energy_requirement == "high" and bucket in {"evening", "night"}:
            factors.append(DecisionFactor("energy_fit", -5, "High-focus work is penalized late in the day."))
        return factors

    def _find_placement(
        self,
        context: PlanningContext,
        occupied: list[PlannedBlock],
        candidate: CandidateAction,
        duration: int,
    ) -> TimeInterval | None:
        free = self.free_intervals(context.horizon_start, context.horizon_end, occupied)
        earliest_start = _align_timezone(candidate.earliest_start, context.horizon_start)
        latest_start = _align_timezone(candidate.latest_start, context.horizon_start)
        deadline = _align_timezone(candidate.deadline, context.horizon_start)
        window_start = _max_datetime(context.horizon_start, earliest_start or context.horizon_start)
        window_end = _min_datetime(context.horizon_end, deadline or context.horizon_end)

        for interval in free:
            start = _max_datetime(interval.start, window_start)
            end_limit = _min_datetime(interval.end, window_end)
            if latest_start is not None:
                end_limit = _min_datetime(end_limit, _add_minutes(latest_start, duration))
            end = _add_minutes(start, duration)
            if end <= end_limit:
                return TimeInterval(start, end)
        return None

    def _slack_blocks(
        self,
        context: PlanningContext,
        occupied: list[PlannedBlock],
        required_slack_minutes: int,
    ) -> list[PlannedBlock]:
        if required_slack_minutes <= 0:
            return []
        remaining = required_slack_minutes
        blocks: list[PlannedBlock] = []
        free = self.free_intervals(context.horizon_start, context.horizon_end, occupied)
        for interval in free:
            if remaining <= 0:
                break
            duration = min(interval.minutes, remaining)
            if duration <= 0:
                continue
            blocks.append(
                PlannedBlock(
                    title="Buffer / slack",
                    block_type=BLOCK_SLACK,
                    starts_at=interval.start,
                    ends_at=_add_minutes(interval.start, duration),
                    duration_minutes=duration,
                    source_type="planner",
                    source_id=None,
                    domain="recovery",
                    commitment_level=None,
                    movable=True,
                    decision_factors=[DecisionFactor("explicit_slack", duration, "Slack is reserved before leftover time is treated as capacity.")],
                )
            )
            remaining -= duration
        return blocks

    def stress_estimate(self, context: PlanningContext, blocks: list[PlannedBlock], capacity: CapacityEstimate) -> StressEstimate:
        action_blocks = [block for block in blocks if block.block_type == BLOCK_GENERATED_ACTION]
        flexible_minutes = sum(block.duration_minutes for block in action_blocks)
        domains = [block.domain for block in action_blocks if block.domain]
        switches = sum(1 for index in range(1, len(domains)) if domains[index] != domains[index - 1])
        load_ratio = 0 if capacity.usable_flexible_minutes == 0 else flexible_minutes / capacity.usable_flexible_minutes
        state_penalty = {"high": 2, "medium": 8, "low": 16, "very_low": 24}[capacity.state_band]
        block_pressure = len(action_blocks) * 4
        switch_pressure = switches * 3
        workload_pressure = round(min(45, load_ratio * 38))
        slack_relief = -8 if capacity.required_slack_minutes >= 90 else -3
        value = max(0, min(100, state_penalty + block_pressure + switch_pressure + workload_pressure + slack_relief))
        band = "low" if value < 34 else "moderate" if value < 67 else "high"
        return StressEstimate(
            value=value,
            threshold=STRESS_THRESHOLD,
            band=band,
            factors=[
                DecisionFactor("state_pressure", state_penalty),
                DecisionFactor("block_count_pressure", block_pressure),
                DecisionFactor("context_switch_pressure", switch_pressure),
                DecisionFactor("workload_pressure", workload_pressure),
                DecisionFactor("slack_relief", slack_relief),
            ],
        )

    def _trim_to_stress_budget(
        self,
        context: PlanningContext,
        generated_blocks: list[PlannedBlock],
        unscheduled: list[UnscheduledAction],
        scored_candidates: list[ScoredCandidate],
        hard_blocks: list[PlannedBlock],
        capacity: CapacityEstimate,
    ) -> tuple[list[PlannedBlock], list[UnscheduledAction]]:
        score_by_id = {item.candidate.source_action_id: item.score for item in scored_candidates}
        blocks = sorted(
            generated_blocks,
            key=lambda block: (
                {"optional": 0, "maintenance": 1, "goal_critical": 2}.get(block.commitment_level or "", 0),
                score_by_id.get(block.action_id or "", 0),
                block.starts_at,
            ),
        )
        removed: list[UnscheduledAction] = []
        while blocks and self.stress_estimate(context, hard_blocks + blocks, capacity).value > STRESS_THRESHOLD:
            block = blocks.pop(0)
            removed.append(UnscheduledAction(block.action_id or "", block.title, "stress_limit", score_by_id.get(block.action_id or "", 0)))
        remaining = sorted(blocks, key=lambda block: block.starts_at)
        return remaining, unscheduled + removed


def decision_factors_json(factors: list[DecisionFactor]) -> list[dict[str, Any]]:
    return [asdict(factor) for factor in factors]
