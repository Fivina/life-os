from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import (
    Action,
    Exam,
    Plan,
    PlanBlock,
    PlanningDebt,
    StudyRequirement,
    StudySession,
    UserProfile,
)
from app.domains.learning.service import future_capacity_minutes
from app.strategy.schemas import (
    CALCULATION_VERSION,
    DataCompleteness,
    DeviationSeverity,
    DeviationType,
    ExamTrajectorySnapshot,
    Recoverability,
    StrategicDeviation,
)


logger = get_logger(__name__)
RECENT_PACE_WINDOW_DAYS = 14


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _deadline(exam: Exam, timezone_name: str) -> datetime | None:
    if exam.exam_at is not None:
        return _aware(exam.exam_at)
    if exam.exam_date is None:
        return None
    zone = ZoneInfo(timezone_name)
    return datetime.combine(exam.exam_date, datetime.max.time().replace(microsecond=0), tzinfo=zone).astimezone(UTC)


class StrategicMonitor:
    """Build reproducible exam trajectory evidence from canonical state only."""

    calculation_version = CALCULATION_VERSION
    recent_window_days = RECENT_PACE_WINDOW_DAYS

    def assess_exam(
        self,
        db: Session,
        user: UserProfile,
        exam: Exam,
        *,
        now: datetime | None = None,
        timezone_name: str = "Europe/Berlin",
    ) -> ExamTrajectorySnapshot:
        current = _aware(now or datetime.now(UTC))
        deadline = _deadline(exam, timezone_name)
        requirements = list(db.scalars(
            select(StudyRequirement)
            .where(StudyRequirement.user_id == user.id, StudyRequirement.exam_id == exam.id)
            .order_by(StudyRequirement.order_index, StudyRequirement.created_at)
        ))
        workload, workload_source, workload_complete = self._workload(exam, requirements)
        sessions = list(db.scalars(
            select(StudySession).where(StudySession.user_id == user.id, StudySession.exam_id == exam.id)
        ))
        completed = sum(max(0, row.quality_adjusted_minutes) for row in sessions)
        remaining = max(0, workload - completed) if workload is not None else None
        window_start = current - timedelta(days=self.recent_window_days)
        recent_minutes = sum(
            max(0, row.quality_adjusted_minutes)
            for row in sessions
            if _aware(row.occurred_at) >= window_start and _aware(row.occurred_at) <= current
        )
        actual_weekly = round(recent_minutes * 7 / self.recent_window_days, 2)

        days_remaining = None
        required_weekly = None
        if deadline is not None:
            days_remaining = round(max(0, (deadline - current).total_seconds()) / 86400, 2)
            if remaining is not None and remaining > 0:
                required_weekly = round(remaining * 7 / max(days_remaining, 1), 2)
            elif remaining == 0:
                required_weekly = 0.0

        plan_metrics = self._future_plan_metrics(db, user, exam, current, deadline)
        broad_capacity, _capacity_notes = future_capacity_minutes(db, user, exam, current, timezone_name)
        additional_capacity = max(0, broad_capacity - plan_metrics["all_allocated_minutes"]) if deadline is not None else None
        projected_shortfall = (
            max(0, remaining - plan_metrics["exam_allocated_minutes"] - (additional_capacity or 0))
            if remaining is not None and additional_capacity is not None
            else None
        )
        capacity_shortfall = projected_shortfall
        buffer_minutes = (
            max(0, plan_metrics["exam_allocated_minutes"] + (additional_capacity or 0) - remaining)
            if remaining is not None and additional_capacity is not None
            else None
        )
        debt = self._planning_debt(db, user, exam)
        readiness = round(min(1.0, completed / workload) * 100) if workload and workload > 0 else None
        pace_gap = round(max(0.0, (required_weekly or 0) - actual_weekly), 2) if required_weekly is not None else None

        unavailable: list[str] = []
        if deadline is None:
            unavailable.extend(("days_remaining", "required_weekly_pace", "future_capacity"))
        if workload is None:
            unavailable.extend(("remaining_workload", "readiness", "projected_shortfall"))
        if not sessions:
            unavailable.append("observed_recent_execution_quality")
        completeness_score = round(sum((deadline is not None, workload is not None, bool(requirements), bool(sessions))) / 4, 2)
        if deadline is None or workload is None:
            completeness = DataCompleteness.insufficient
        elif workload_complete and sessions:
            completeness = DataCompleteness.complete
        else:
            completeness = DataCompleteness.partial

        indicators: list[str] = []
        if projected_shortfall and projected_shortfall > 0:
            indicators.append("capacity_shortfall")
        if pace_gap and pace_gap > 0:
            indicators.append("pace_shortfall")
        if remaining is not None and plan_metrics["exam_allocated_minutes"] < remaining:
            indicators.append("underallocated")
        if debt > 0:
            indicators.append("planning_debt")
        if days_remaining is not None and days_remaining <= 3 and remaining and remaining > 0:
            indicators.append("deadline_pressure")

        snapshot = ExamTrajectorySnapshot(
            exam_id=exam.id,
            course_id=exam.course_id,
            exam_title=exam.title,
            as_of=current,
            exam_at=deadline,
            days_remaining=days_remaining,
            total_workload_minutes=workload,
            workload_source=workload_source,
            completed_effective_minutes=completed,
            remaining_workload_minutes=remaining,
            planned_future_minutes=plan_metrics["exam_allocated_minutes"],
            recent_actual_effective_minutes=recent_minutes,
            recent_window_days=self.recent_window_days,
            actual_weekly_pace_minutes=actual_weekly,
            required_weekly_pace_minutes=required_weekly,
            pace_gap_minutes=pace_gap,
            future_capacity_minutes=additional_capacity,
            future_allocated_minutes=plan_metrics["all_allocated_minutes"],
            capacity_shortfall_minutes=capacity_shortfall,
            projected_shortfall_minutes=projected_shortfall,
            planning_debt_minutes=debt,
            readiness_score=readiness,
            readiness_source="effective_workload_completion" if readiness is not None else None,
            buffer_minutes=buffer_minutes,
            risk_indicators=tuple(indicators),
            completeness=completeness,
            completeness_score=completeness_score,
            unavailable_metrics=tuple(sorted(set(unavailable))),
            source_world_revision=user.world_revision,
        )
        logger.info(
            "strategic_assessment_completed",
            extra={"user_id": user.id, "exam_id": exam.id, "completeness": completeness.value, "risk_count": len(indicators)},
        )
        return snapshot

    def deviation(self, snapshot: ExamTrajectorySnapshot, *, trigger: str = "manual") -> StrategicDeviation | None:
        if snapshot.completeness == DataCompleteness.insufficient or snapshot.remaining_workload_minutes is None:
            return None
        types: list[DeviationType] = []
        reasons: list[str] = []
        scheduled_gap = max(0, snapshot.remaining_workload_minutes - snapshot.planned_future_minutes)
        unresolved = snapshot.projected_shortfall_minutes or 0
        pace_gap = int(ceil(snapshot.pace_gap_minutes or 0))
        if pace_gap > 0:
            types.append(DeviationType.pace_shortfall)
            reasons.append("recent_effective_pace_below_required")
        if unresolved > 0:
            types.append(DeviationType.capacity_shortfall)
            reasons.append("remaining_work_exceeds_planned_and_free_capacity")
        if scheduled_gap > 0:
            types.append(DeviationType.underallocation)
            reasons.append("remaining_work_not_covered_by_current_plan")
        if snapshot.planning_debt_minutes > 0:
            types.append(DeviationType.planning_debt_surge)
            reasons.append("open_learning_planning_debt")
        if snapshot.days_remaining is not None and snapshot.days_remaining <= 3 and snapshot.remaining_workload_minutes > 0:
            types.append(DeviationType.deadline_pressure)
            reasons.append("exam_deadline_near")
        if "missed" in trigger.lower():
            types.append(DeviationType.missed_critical_work)
            reasons.append("critical_study_execution_missed")
        if not types:
            return None

        magnitude = max(unresolved, scheduled_gap, pace_gap, snapshot.planning_debt_minutes)
        recoverability = self._recoverability(snapshot, scheduled_gap, unresolved)
        severity = self._severity(snapshot, magnitude, unresolved)
        material = {
            "exam_id": snapshot.exam_id,
            "types": sorted(item.value for item in set(types)),
            "magnitude": magnitude,
            "days": snapshot.days_remaining,
            "version": self.calculation_version,
        }
        fingerprint = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result = StrategicDeviation(
            exam_id=snapshot.exam_id,
            deviation_types=tuple(dict.fromkeys(types)),
            severity=severity,
            recoverability=recoverability,
            magnitude_minutes=magnitude,
            days_remaining=snapshot.days_remaining,
            evidence_quality=snapshot.completeness_score,
            reason_codes=tuple(dict.fromkeys(reasons)),
            fingerprint=fingerprint,
        )
        logger.info(
            "strategic_deviation_detected",
            extra={"exam_id": snapshot.exam_id, "severity": severity.value, "recoverability": recoverability.value},
        )
        return result

    @staticmethod
    def _workload(exam: Exam, requirements: list[StudyRequirement]) -> tuple[int | None, str | None, bool]:
        if requirements:
            estimates: list[int] = []
            complete = True
            for row in requirements:
                estimate = row.estimated_required_minutes
                if estimate is None and row.estimated_hours > 0:
                    estimate = round(row.estimated_hours * 60)
                if estimate is None or estimate <= 0:
                    complete = False
                    continue
                estimates.append(estimate)
            if estimates:
                return sum(estimates), "study_requirements", complete and len(estimates) == len(requirements)
        if exam.target_quality_adjusted_minutes is not None and exam.target_quality_adjusted_minutes > 0:
            return exam.target_quality_adjusted_minutes, "exam_target_quality_adjusted_minutes", True
        if exam.target_preparation_minutes > 0:
            return exam.target_preparation_minutes, "exam_target_preparation_minutes", False
        if exam.estimated_required_hours > 0:
            return round(exam.estimated_required_hours * 60), "exam_estimated_required_hours", False
        return None, None, False

    @staticmethod
    def _future_plan_metrics(
        db: Session,
        user: UserProfile,
        exam: Exam,
        now: datetime,
        deadline: datetime | None,
    ) -> dict[str, int]:
        upper = deadline or now + timedelta(days=14)
        rows = list(db.execute(
            select(PlanBlock, Action)
            .join(Plan, Plan.id == PlanBlock.plan_id)
            .outerjoin(Action, Action.id == PlanBlock.action_id)
            .where(
                Plan.user_id == user.id,
                Plan.status == "current",
                PlanBlock.starts_at >= now,
                PlanBlock.starts_at < upper,
                PlanBlock.status.in_(("planned", "in_progress")),
                PlanBlock.block_type == "generated_action",
            )
        ))
        all_allocated = sum(max(0, block.duration_minutes) for block, _action in rows)
        exam_allocated = sum(
            max(0, block.duration_minutes)
            for block, action in rows
            if action is not None and action.source_entity_type == "exam" and action.source_entity_id == exam.id
        )
        return {"all_allocated_minutes": all_allocated, "exam_allocated_minutes": exam_allocated}

    @staticmethod
    def _planning_debt(db: Session, user: UserProfile, exam: Exam) -> int:
        value = db.scalar(
            select(func.coalesce(func.sum(PlanningDebt.residual_minutes), 0))
            .join(Action, Action.id == PlanningDebt.source_action_id)
            .where(
                PlanningDebt.user_id == user.id,
                PlanningDebt.status == "open",
                Action.source_entity_type == "exam",
                Action.source_entity_id == exam.id,
            )
        )
        return int(value or 0)

    @staticmethod
    def _recoverability(snapshot: ExamTrajectorySnapshot, scheduled_gap: int, unresolved: int) -> Recoverability:
        capacity = snapshot.future_capacity_minutes
        if capacity is None:
            return Recoverability.unknown
        if scheduled_gap <= capacity and unresolved == 0:
            return Recoverability.existing_capacity
        if unresolved <= max(60, round(snapshot.remaining_workload_minutes or 0) * 0.15):
            return Recoverability.low_cost_reallocation
        if unresolved < (snapshot.remaining_workload_minutes or 0):
            return Recoverability.meaningful_tradeoff
        return Recoverability.unrecoverable

    @staticmethod
    def _severity(snapshot: ExamTrajectorySnapshot, magnitude: int, unresolved: int) -> DeviationSeverity:
        remaining = max(1, snapshot.remaining_workload_minutes or 1)
        ratio = magnitude / remaining
        days = snapshot.days_remaining if snapshot.days_remaining is not None else 999
        if (days <= 2 and unresolved >= 60) or ratio >= 0.75:
            return DeviationSeverity.critical
        if days <= 5 or ratio >= 0.45:
            return DeviationSeverity.high
        if ratio >= 0.15 or magnitude >= 60:
            return DeviationSeverity.moderate
        return DeviationSeverity.low
