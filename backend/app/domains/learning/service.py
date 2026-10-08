from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionUpdate
from app.actions.service import create_action, list_actions, update_action
from app.database.models import (
    Action,
    Commitment,
    Course,
    Exam,
    Plan,
    PlanBlock,
    StudyRequirement,
    StudySession,
    UserProfile,
)
from app.core.logging import get_logger
from app.domains.learning.schemas import (
    CourseCreate,
    CourseRead,
    CourseUpdate,
    ExamCreate,
    ExamRead,
    ExamUpdate,
    LearningCandidateRead,
    LearningContextRead,
    LearningStatusRead,
    LearningTrajectoryRead,
    StudySessionCreate,
    StudySessionRead,
    TopicCoverageRead,
    TopicCreate,
    TopicRead,
    TopicUpdate,
)
from app.domains.base import ActionVariantSpec, PlanningRequirement
from app.domains.planning import GENERATION_VERSION, reconcile_requirements
from app.events.service import append_event

STRATEGY_VERSION = "learning-trajectory-v1"
QUALITY_MULTIPLIERS = {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.1, 5: 1.2}
RISK_THRESHOLDS = {"moderate": 0.55, "high": 0.8, "critical": 0.95}
logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown timezone: {name}.") from exc


def _align(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _check_version(record, expected_version: int | None) -> None:
    if expected_version is not None and record.version != expected_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Version conflict. Current version is {record.version}.")


def _event(db: Session, user: UserProfile, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> None:
    append_event(db, user, event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload, outbox=True)


def _get_course(db: Session, user: UserProfile, course_id: str) -> Course:
    course = db.get(Course, course_id)
    if course is None or course.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return course


def _get_exam(db: Session, user: UserProfile, exam_id: str) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


def _get_topic(db: Session, user: UserProfile, topic_id: str) -> StudyRequirement:
    topic = db.get(StudyRequirement, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    return topic


def _exam_deadline(exam: Exam, timezone_name: str = "Europe/Berlin") -> datetime | None:
    if exam.exam_at is not None:
        value = exam.exam_at
        if value.tzinfo is None:
            return value.replace(tzinfo=_timezone(timezone_name))
        return value
    if exam.exam_date is None:
        return None
    return datetime.combine(exam.exam_date, time(23, 59), tzinfo=_timezone(timezone_name))


def _target_minutes(payload: ExamCreate) -> int:
    if payload.target_preparation_minutes is not None:
        return payload.target_preparation_minutes
    return max(1, round((payload.estimated_required_hours or 0) * 60))


def create_course(db: Session, user: UserProfile, payload: CourseCreate) -> Course:
    course = Course(user_id=user.id, name=payload.name, title=payload.name, code=payload.code, description=payload.description, institution=payload.institution, status=payload.status)
    db.add(course)
    db.flush()
    _event(db, user, "learning.course.created", "course", course.id, {"course_id": course.id, "name": course.name})
    return course


def list_courses(db: Session, user: UserProfile) -> list[Course]:
    return db.scalars(select(Course).where(Course.user_id == user.id).order_by(Course.status, Course.name)).all()


def update_course(db: Session, user: UserProfile, course_id: str, payload: CourseUpdate) -> Course:
    course = _get_course(db, user, course_id)
    _check_version(course, payload.expected_version)
    for key, value in payload.model_dump(exclude={"expected_version"}, exclude_unset=True).items():
        setattr(course, key, value)
        if key == "name":
            course.title = value
    course.version += 1
    _event(db, user, "learning.course.updated", "course", course.id, {"course_id": course.id})
    return course


def create_exam(db: Session, user: UserProfile, payload: ExamCreate) -> Exam:
    course = _get_course(db, user, payload.course_id) if payload.course_id else None
    target = _target_minutes(payload)
    exam = Exam(
        user_id=user.id,
        course_id=course.id if course else None,
        title=payload.title,
        exam_date=payload.exam_date or (payload.exam_at.date() if payload.exam_at else None),
        exam_at=payload.exam_at,
        estimated_required_hours=round(target / 60, 2),
        completed_hours=0,
        target_preparation_minutes=target,
        minimum_required_preparation_minutes=payload.minimum_required_preparation_minutes,
        target_quality_adjusted_minutes=payload.target_quality_adjusted_minutes or target,
        strategy_version=STRATEGY_VERSION,
        importance=payload.importance,
        attempts_remaining=payload.attempts_remaining,
        final_attempt=payload.final_attempt,
        exam_format=payload.exam_format,
        location=payload.location,
        notes=payload.notes,
        status=payload.status,
    )
    db.add(exam)
    db.flush()
    _event(db, user, "learning.exam.created", "exam", exam.id, {"exam_id": exam.id, "title": exam.title, "target_preparation_minutes": target})
    return exam


def list_exams(db: Session, user: UserProfile) -> list[Exam]:
    return db.scalars(
        select(Exam)
        .where(Exam.user_id == user.id)
        .order_by(Exam.exam_at.asc().nulls_last(), Exam.exam_date.asc().nulls_last(), Exam.created_at.desc())
    ).all()


def update_exam(db: Session, user: UserProfile, exam_id: str, payload: ExamUpdate) -> Exam:
    exam = _get_exam(db, user, exam_id)
    _check_version(exam, payload.expected_version)
    data = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if "course_id" in data and data["course_id"] is not None:
        data["course_id"] = _get_course(db, user, data["course_id"]).id
    for key, value in data.items():
        setattr(exam, key, value)
        if key == "target_preparation_minutes":
            exam.estimated_required_hours = round(value / 60, 2)
            if exam.target_quality_adjusted_minutes is None:
                exam.target_quality_adjusted_minutes = value
        if key == "exam_at" and value is not None:
            exam.exam_date = value.date()
    exam.strategy_version = STRATEGY_VERSION
    exam.version += 1
    _event(db, user, "learning.exam.updated", "exam", exam.id, {"exam_id": exam.id, "fields": sorted(data.keys())})
    return exam


def create_topic(db: Session, user: UserProfile, exam_id: str, payload: TopicCreate) -> StudyRequirement:
    exam = _get_exam(db, user, exam_id)
    prerequisite_id = _validated_prerequisite(db, user, exam, None, payload.prerequisite_topic_id)
    topic = StudyRequirement(
        user_id=user.id,
        exam_id=exam.id,
        title=payload.title,
        estimated_hours=round((payload.estimated_required_minutes or 0) / 60, 2),
        estimated_required_minutes=payload.estimated_required_minutes,
        order_index=payload.order_index,
        importance_weight=payload.importance_weight,
        prerequisite_topic_id=prerequisite_id,
        status=payload.status,
    )
    db.add(topic)
    db.flush()
    _event(db, user, "learning.topic.created", "study_topic", topic.id, {"exam_id": exam.id, "topic_id": topic.id})
    return topic


def list_topics(db: Session, user: UserProfile, exam_id: str) -> list[StudyRequirement]:
    exam = _get_exam(db, user, exam_id)
    return db.scalars(
        select(StudyRequirement).where(StudyRequirement.user_id == user.id, StudyRequirement.exam_id == exam.id).order_by(StudyRequirement.order_index, StudyRequirement.created_at)
    ).all()


def _validated_prerequisite(db: Session, user: UserProfile, exam: Exam, topic_id: str | None, prerequisite_id: str | None) -> str | None:
    if prerequisite_id is None:
        return None
    prerequisite = _get_topic(db, user, prerequisite_id)
    if prerequisite.exam_id != exam.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Prerequisite topic belongs to a different exam.")
    if topic_id and prerequisite_id == topic_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Topic cannot require itself.")
    cursor = prerequisite
    seen = {topic_id} if topic_id else set()
    while cursor.prerequisite_topic_id is not None:
        if cursor.prerequisite_topic_id in seen:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Prerequisite cycle detected.")
        seen.add(cursor.id)
        cursor = _get_topic(db, user, cursor.prerequisite_topic_id)
    return prerequisite.id


def update_topic(db: Session, user: UserProfile, topic_id: str, payload: TopicUpdate) -> StudyRequirement:
    topic = _get_topic(db, user, topic_id)
    exam = _get_exam(db, user, topic.exam_id)
    _check_version(topic, payload.expected_version)
    data = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if "prerequisite_topic_id" in data:
        data["prerequisite_topic_id"] = _validated_prerequisite(db, user, exam, topic.id, data["prerequisite_topic_id"])
    for key, value in data.items():
        setattr(topic, key, value)
        if key == "estimated_required_minutes" and value is not None:
            topic.estimated_hours = round(value / 60, 2)
    topic.version += 1
    _event(db, user, "learning.topic.updated", "study_topic", topic.id, {"topic_id": topic.id, "fields": sorted(data.keys())})
    return topic


def _quality_multiplier(rating: int | None) -> float:
    return QUALITY_MULTIPLIERS.get(rating or 3, 1.0)


def log_study_session(db: Session, user: UserProfile, payload: StudySessionCreate, idempotency_key: str | None = None) -> StudySession:
    if idempotency_key:
        existing = db.scalar(select(StudySession).where(StudySession.user_id == user.id, StudySession.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    exam = _get_exam(db, user, payload.exam_id)
    previous_trajectory = trajectory_for_exam(db, user, exam)
    topic = _get_topic(db, user, payload.topic_id) if payload.topic_id else None
    if topic is not None and topic.exam_id != exam.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Topic belongs to a different exam.")
    if payload.course_id is not None and exam.course_id is not None and payload.course_id != exam.course_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Course does not match exam.")
    when = payload.occurred_at or payload.completed_at or _now()
    started = payload.started_at or (when - timedelta(minutes=payload.duration_minutes))
    multiplier = _quality_multiplier(payload.quality_rating)
    adjusted = max(1, min(round(payload.duration_minutes * multiplier), round(payload.duration_minutes * 1.2)))
    session = StudySession(
        user_id=user.id,
        course_id=payload.course_id or exam.course_id,
        exam_id=exam.id,
        topic_id=topic.id if topic else None,
        source_action_id=payload.source_action_id,
        source_plan_block_id=payload.source_plan_block_id,
        occurred_at=when,
        started_at=started,
        ended_at=payload.completed_at or when,
        completed_at=payload.completed_at or when,
        minutes=payload.duration_minutes,
        duration_minutes=payload.duration_minutes,
        planned_duration_minutes=payload.planned_duration_minutes,
        completion_status=payload.completion_status,
        location=payload.location,
        context_json=payload.context_json,
        quality_rating=payload.quality_rating,
        focus_quality=payload.focus_quality,
        comprehension_quality=payload.comprehension_quality,
        quality_multiplier=multiplier,
        quality_adjusted_minutes=adjusted,
        source=payload.source,
        idempotency_key=idempotency_key,
        notes=payload.notes,
    )
    db.add(session)
    if topic is not None:
        topic.completed_minutes = (topic.completed_minutes or 0) + adjusted
        if topic.estimated_required_minutes and topic.completed_minutes >= topic.estimated_required_minutes:
            topic.status = "covered"
        topic.version += 1
    db.flush()
    _event(
        db,
        user,
        "learning.study_session.completed",
        "study_session",
        session.id,
        {
            "study_session_id": session.id,
            "exam_id": exam.id,
            "topic_id": topic.id if topic else None,
            "duration_minutes": session.duration_minutes,
            "quality_adjusted_minutes": session.quality_adjusted_minutes,
            "planned_duration_minutes": session.planned_duration_minutes,
            "completion_status": session.completion_status,
            "location": session.location,
            "context": session.context_json,
            "source": session.source,
        },
    )
    refreshed = trajectory_for_exam(db, user, exam)
    _event(
        db,
        user,
        "learning.readiness.updated",
        "exam",
        exam.id,
        {"exam_id": exam.id, "readiness_score": refreshed.readiness_score, "remaining_minutes": refreshed.remaining_quality_adjusted_minutes, "required_daily_minutes": refreshed.required_daily_minutes},
    )
    if refreshed.risk != previous_trajectory.risk:
        _event(db, user, "learning.risk.changed", "exam", exam.id, {"exam_id": exam.id, "previous": previous_trajectory.risk, "current": refreshed.risk})
    return session


def complete_learning_plan_block(
    db: Session,
    user: UserProfile,
    block: PlanBlock,
    actual_duration_minutes: int,
    occurred_at: datetime,
    *,
    completion_status: str = "completed",
) -> StudySession | None:
    if block.domain != "learning" or block.action_id is None:
        return None
    existing = db.scalar(select(StudySession).where(StudySession.user_id == user.id, StudySession.source_plan_block_id == block.id))
    if existing is not None:
        return existing
    action = db.scalar(select(Action).where(Action.user_id == user.id, Action.id == block.action_id))
    if action is None or not isinstance(action.metadata_json, dict) or "exam_id" not in action.metadata_json:
        return None
    return log_study_session(
        db,
        user,
        StudySessionCreate(
            course_id=action.metadata_json.get("course_id"),
            exam_id=action.metadata_json["exam_id"],
            topic_id=action.metadata_json.get("topic_id"),
            source_action_id=action.id,
            source_plan_block_id=block.id,
            occurred_at=occurred_at,
            completed_at=occurred_at,
            duration_minutes=actual_duration_minutes,
            planned_duration_minutes=block.duration_minutes,
            completion_status=completion_status,
            location=action.location,
            context_json={
                "planned_slot": block.starts_at.isoformat(),
                "actual_slot": (block.started_at or occurred_at).isoformat(),
                "daypart": "morning" if block.starts_at.hour < 12 else "afternoon" if block.starts_at.hour < 18 else "evening",
                "manual_movement": block.user_modified,
                "activation": block.variant_type == "activation",
            },
            quality_rating=None,
            source="plan_block",
            notes=f"Completed from PlanBlock: {block.title}",
        ),
        idempotency_key=f"plan-block:{block.id}",
    )


def list_study_sessions(db: Session, user: UserProfile, exam_id: str | None = None, limit: int = 50) -> list[StudySession]:
    query = select(StudySession).where(StudySession.user_id == user.id)
    if exam_id:
        query = query.where(StudySession.exam_id == exam_id)
    return db.scalars(query.order_by(StudySession.occurred_at.desc(), StudySession.created_at.desc()).limit(limit)).all()


def _sessions_for_exam(db: Session, user: UserProfile, exam: Exam) -> list[StudySession]:
    return db.scalars(select(StudySession).where(StudySession.user_id == user.id, StudySession.exam_id == exam.id)).all()


def _topics_for_exam(db: Session, user: UserProfile, exam: Exam) -> list[StudyRequirement]:
    return db.scalars(
        select(StudyRequirement).where(StudyRequirement.user_id == user.id, StudyRequirement.exam_id == exam.id).order_by(StudyRequirement.order_index, StudyRequirement.created_at)
    ).all()


def _topic_session_minutes(sessions: list[StudySession]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for session in sessions:
        if session.topic_id:
            totals[session.topic_id] = totals.get(session.topic_id, 0) + session.quality_adjusted_minutes
    return totals


def topic_coverage(db: Session, user: UserProfile, exam: Exam, sessions: list[StudySession] | None = None) -> tuple[float | None, list[TopicCoverageRead]]:
    sessions = sessions if sessions is not None else _sessions_for_exam(db, user, exam)
    totals = _topic_session_minutes(sessions)
    topics = _topics_for_exam(db, user, exam)
    if not topics:
        return None, []
    covered_by_status = {"covered", "complete", "completed", "done"}
    weight_total = sum(max(0.1, topic.importance_weight or 1.0) for topic in topics)
    weighted = 0.0
    rows: list[TopicCoverageRead] = []
    coverage_by_id: dict[str, float] = {}
    for topic in topics:
        estimated = topic.estimated_required_minutes or max(1, round((exam.target_preparation_minutes or 60) / max(1, len(topics))))
        completed = max(topic.completed_minutes or 0, totals.get(topic.id, 0))
        ratio = 1.0 if topic.status in covered_by_status else min(1.0, completed / estimated)
        coverage_by_id[topic.id] = ratio
        weighted += ratio * max(0.1, topic.importance_weight or 1.0)
    for topic in topics:
        prereq_ok = True
        if topic.prerequisite_topic_id:
            prereq_ok = coverage_by_id.get(topic.prerequisite_topic_id, 0) >= 0.8
        estimated = topic.estimated_required_minutes or max(1, round((exam.target_preparation_minutes or 60) / max(1, len(topics))))
        completed = max(topic.completed_minutes or 0, totals.get(topic.id, 0))
        rows.append(
            TopicCoverageRead(
                topic_id=topic.id,
                title=topic.title,
                status=topic.status,
                importance_weight=topic.importance_weight,
                estimated_required_minutes=topic.estimated_required_minutes,
                completed_quality_adjusted_minutes=completed,
                coverage_ratio=round(coverage_by_id[topic.id], 3),
                prerequisite_topic_id=topic.prerequisite_topic_id,
                prerequisite_satisfied=prereq_ok,
            )
        )
    return round(weighted / weight_total, 3) if weight_total else 0.0, rows


def _commitment_minutes_on_day(db: Session, user: UserProfile, day: date, zone: ZoneInfo) -> int:
    start = datetime.combine(day, time(0, 0), tzinfo=zone)
    end = start + timedelta(days=1)
    commitments = db.scalars(
        select(Commitment).where(
            Commitment.user_id == user.id,
            Commitment.status == "active",
            Commitment.level == "hard",
            Commitment.starts_at.is_not(None),
            Commitment.ends_at.is_not(None),
            Commitment.starts_at < end,
            Commitment.ends_at > start,
        )
    ).all()
    minutes = 0
    for commitment in commitments:
        begins = max(_align(commitment.starts_at, start), start)
        finishes = min(_align(commitment.ends_at, start), end)
        if finishes > begins:
            minutes += round((finishes - begins).total_seconds() / 60)
    return minutes


def future_capacity_minutes(db: Session, user: UserProfile, exam: Exam, now: datetime, timezone_name: str) -> tuple[int, dict[str, Any]]:
    deadline = _exam_deadline(exam, timezone_name)
    if deadline is None:
        return 0, {"reason": "no_deadline"}
    deadline = _align(deadline, now)
    if deadline <= now:
        return 0, {"reason": "exam_past_or_now"}
    zone = _timezone(timezone_name)
    local_now = now.astimezone(zone) if now.tzinfo else now.replace(tzinfo=UTC).astimezone(zone)
    local_deadline = deadline.astimezone(zone) if deadline.tzinfo else deadline.replace(tzinfo=zone)
    total = 0
    daily: list[dict[str, Any]] = []
    cursor = local_now.date()
    while cursor <= local_deadline.date():
        weekend = cursor.weekday() >= 5
        base = 180 if weekend else 120
        hard = _commitment_minutes_on_day(db, user, cursor, zone)
        after_commitments = max(0, base - round(hard * 0.35))
        usable = max(0, min(base, round(after_commitments * 0.85)))
        if cursor == local_now.date():
            fraction_left = max(0.0, min(1.0, (datetime.combine(cursor + timedelta(days=1), time(0, 0), tzinfo=zone) - local_now).total_seconds() / 86400))
            usable = round(usable * fraction_left)
        if cursor == local_deadline.date():
            fraction_before_exam = max(0.0, min(1.0, (local_deadline - datetime.combine(cursor, time(0, 0), tzinfo=zone)).total_seconds() / 86400))
            usable = round(usable * fraction_before_exam)
        total += usable
        daily.append({"date": cursor.isoformat(), "base_minutes": base, "hard_commitment_minutes": hard, "usable_minutes": usable})
        cursor += timedelta(days=1)
    return total, {"daily": daily, "assumptions": "weekday 120m/weekend 180m, hard commitments discount 35%, sustainability buffer 15%"}


def trajectory_for_exam(db: Session, user: UserProfile, exam: Exam, *, now: datetime | None = None, timezone_name: str = "Europe/Berlin") -> LearningTrajectoryRead:
    current = now or _now()
    deadline = _exam_deadline(exam, timezone_name)
    sessions = _sessions_for_exam(db, user, exam)
    raw_completed = sum(item.duration_minutes for item in sessions)
    adjusted_completed = sum(item.quality_adjusted_minutes for item in sessions)
    target = exam.target_quality_adjusted_minutes or exam.target_preparation_minutes
    remaining = max(target - adjusted_completed, 0)
    if deadline is None:
        hours_remaining = 0.0
        days_remaining = 0.0
    else:
        aligned_deadline = _align(deadline, current)
        seconds = max(0, (aligned_deadline - current).total_seconds())
        hours_remaining = round(seconds / 3600, 2)
        days_remaining = round(seconds / 86400, 2)
    capacity, capacity_notes = future_capacity_minutes(db, user, exam, current, timezone_name)
    if remaining == 0:
        feasible = True
        load_ratio = 0.0
        shortfall = 0
    elif capacity <= 0:
        feasible = False
        load_ratio = None
        shortfall = remaining
    else:
        load_ratio = round(remaining / capacity, 3)
        feasible = remaining <= capacity
        shortfall = max(remaining - capacity, 0)
    if not feasible:
        risk = "infeasible"
    elif load_ratio is None:
        risk = "critical"
    elif load_ratio >= RISK_THRESHOLDS["critical"]:
        risk = "critical"
    elif load_ratio >= RISK_THRESHOLDS["high"]:
        risk = "high"
    elif load_ratio >= RISK_THRESHOLDS["moderate"]:
        risk = "moderate"
    else:
        risk = "low"
    progress_ratio = min(1.0, adjusted_completed / target) if target > 0 else 0.0
    topic_ratio, _coverage = topic_coverage(db, user, exam, sessions)
    if topic_ratio is None:
        readiness = round(progress_ratio * 100)
    else:
        readiness = round((progress_ratio * 0.7 + topic_ratio * 0.3) * 100)
    readiness = max(0, min(100, readiness))
    readiness_label = "strong" if readiness >= 75 else "developing" if readiness >= 45 else "early"
    effective_days = max(days_remaining, 1 / 24)
    required_daily = round(remaining / max(1, ceil(effective_days)), 2)
    required_weekly = round(required_daily * 7 / 60, 2)
    latest_safe_start = None
    behind_safe_pace = False
    if remaining > 0 and capacity > 0 and deadline is not None:
        daily_values = capacity_notes.get("daily", [])
        avg_capacity = max(1, round(capacity / max(1, len(daily_values))))
        required_days = ceil(remaining / avg_capacity)
        safety_days = max(1, min(7, ceil(max(days_remaining, 1) * 0.15)))
        latest_safe_start = deadline - timedelta(days=required_days + safety_days)
        latest_safe_start = _align(latest_safe_start, current)
        behind_safe_pace = current > latest_safe_start
    return LearningTrajectoryRead(
        exam_id=exam.id,
        strategy_version=exam.strategy_version or STRATEGY_VERSION,
        target_preparation_minutes=target,
        raw_completed_minutes=raw_completed,
        quality_adjusted_completed_minutes=adjusted_completed,
        remaining_quality_adjusted_minutes=remaining,
        days_remaining=days_remaining,
        hours_remaining=hours_remaining,
        future_capacity_minutes=capacity,
        required_daily_minutes=required_daily,
        required_weekly_hours=required_weekly,
        load_ratio=load_ratio,
        risk=risk,
        feasible=feasible,
        shortfall_minutes=shortfall,
        shortfall_hours=round(shortfall / 60, 2),
        readiness_score=readiness,
        readiness_label=readiness_label,
        topic_coverage_ratio=topic_ratio,
        latest_safe_start=latest_safe_start,
        behind_safe_pace=behind_safe_pace,
        calculation_notes={"future_capacity": capacity_notes, "quality_multipliers": QUALITY_MULTIPLIERS, "risk_thresholds": RISK_THRESHOLDS},
    )


def _topic_read(topic: StudyRequirement) -> TopicRead:
    return TopicRead.model_validate(topic)


def exam_to_read(db: Session, user: UserProfile, exam: Exam, *, include_trajectory: bool = True, now: datetime | None = None, timezone_name: str = "Europe/Berlin") -> ExamRead:
    course = db.get(Course, exam.course_id) if exam.course_id else None
    topics = _topics_for_exam(db, user, exam)
    return ExamRead(
        id=exam.id,
        course_id=exam.course_id,
        title=exam.title,
        exam_date=exam.exam_date,
        exam_at=exam.exam_at,
        estimated_required_hours=exam.estimated_required_hours,
        completed_hours=round(sum(item.duration_minutes for item in _sessions_for_exam(db, user, exam)) / 60, 2),
        target_preparation_minutes=exam.target_preparation_minutes,
        minimum_required_preparation_minutes=exam.minimum_required_preparation_minutes,
        target_quality_adjusted_minutes=exam.target_quality_adjusted_minutes,
        strategy_version=exam.strategy_version,
        importance=exam.importance,
        attempts_remaining=exam.attempts_remaining,
        final_attempt=exam.final_attempt,
        exam_format=exam.exam_format,
        location=exam.location,
        notes=exam.notes,
        status=exam.status,
        version=exam.version,
        course=CourseRead.model_validate(course) if course else None,
        topics=[_topic_read(topic) for topic in topics],
        trajectory=trajectory_for_exam(db, user, exam, now=now, timezone_name=timezone_name) if include_trajectory else None,
    )


def _candidate_topic(db: Session, user: UserProfile, exam: Exam) -> tuple[StudyRequirement | None, bool]:
    sessions = _sessions_for_exam(db, user, exam)
    _topic_ratio, coverage = topic_coverage(db, user, exam, sessions)
    coverage_by_id = {item.topic_id: item for item in coverage}
    for topic in _topics_for_exam(db, user, exam):
        row = coverage_by_id.get(topic.id)
        if row is None:
            continue
        if row.coverage_ratio >= 0.9 or topic.status in {"covered", "complete", "completed", "done"}:
            continue
        if row.prerequisite_satisfied:
            return topic, True
    for topic in _topics_for_exam(db, user, exam):
        row = coverage_by_id.get(topic.id)
        if row and row.coverage_ratio < 0.9:
            return topic, False
    return None, True


def learning_candidates(db: Session, user: UserProfile, *, now: datetime | None = None, timezone_name: str = "Europe/Berlin") -> list[LearningCandidateRead]:
    current = now or _now()
    exams = [exam for exam in list_exams(db, user) if exam.status in {"planned", "active"}]
    candidates: list[LearningCandidateRead] = []
    for exam in exams:
        trajectory = trajectory_for_exam(db, user, exam, now=current, timezone_name=timezone_name)
        if trajectory.remaining_quality_adjusted_minutes <= 0:
            continue
        topic, prereq_ok = _candidate_topic(db, user, exam)
        topic_title = topic.title if topic else "exam preparation"
        deadline = _exam_deadline(exam, timezone_name)
        risk_bonus = {"low": 0, "moderate": 12, "high": 24, "critical": 34, "infeasible": 40}.get(trajectory.risk, 0)
        base_value = max(30, min(95, round(trajectory.readiness_score * 0.35 + risk_bonus + min(25, (trajectory.load_ratio or 1.2) * 20))))
        variants = [
            ("full", 90, 45, 90),
            ("standard", 60, 35, 60),
            ("reduced", 45, 25, 45),
            ("minimum", 25, 15, 25),
            ("activation", 10, 10, 15),
        ]
        for variant, duration, minimum, maximum in variants:
            if variant == "activation" and trajectory.risk == "low":
                continue
            activation = 54 if variant == "full" else 44 if variant == "standard" else 34 if variant == "reduced" else 24
            cognitive = 78 if variant in {"full", "standard"} else 62 if variant == "reduced" else 45
            if not prereq_ok and topic is not None:
                activation += 12
            candidates.append(
                LearningCandidateRead(
                    candidate_id=f"learning:{exam.id}:{topic.id if topic else 'general'}:{variant}",
                    title=f"{exam.title}: {topic_title} ({variant})",
                    exam_id=exam.id,
                    course_id=exam.course_id,
                    topic_id=topic.id if topic else None,
                    duration_minutes=duration,
                    minimum_minutes=minimum,
                    maximum_minutes=maximum,
                    variant=variant,
                    commitment_level="goal_critical" if exam.importance in {"goal_critical", "critical", "high"} else "maintenance",
                    cognitive_load=cognitive,
                    activation_difficulty=min(100, activation),
                    trajectory_value=base_value if variant not in {"minimum", "activation"} else max(25, base_value - 12),
                    urgency={"low": 8, "moderate": 18, "high": 28, "critical": 38, "infeasible": 42}.get(trajectory.risk, 10),
                    neglect_cost={"low": 10, "moderate": 22, "high": 34, "critical": 44, "infeasible": 48}.get(trajectory.risk, 15),
                    deadline=deadline,
                    prerequisite_satisfied=prereq_ok,
                    expected_state_effect={"cognitive_load": cognitive, "variant": variant, "trajectory_risk": trajectory.risk},
                    metadata={
                        "learning_candidate_id": f"learning:{exam.id}:{topic.id if topic else 'general'}:{variant}",
                        "exam_id": exam.id,
                        "course_id": exam.course_id,
                        "topic_id": topic.id if topic else None,
                        "duration_variant": variant,
                        "risk": trajectory.risk,
                        "load_ratio": trajectory.load_ratio,
                        "readiness_score": trajectory.readiness_score,
                        "prerequisite_satisfied": prereq_ok,
                        "splittable": variant not in {"minimum", "activation"},
                    },
                )
            )
    return candidates


def planning_requirements(
    db: Session,
    user: UserProfile,
    *,
    horizon_start: date,
    horizon_end: date,
    timezone_name: str = "Europe/Berlin",
) -> list[PlanningRequirement]:
    zone = _timezone(timezone_name)
    current = datetime.now(zone)
    result: list[PlanningRequirement] = []
    for exam in [item for item in list_exams(db, user) if item.status in {"planned", "active"}]:
        trajectory = trajectory_for_exam(db, user, exam, now=current, timezone_name=timezone_name)
        if trajectory.remaining_quality_adjusted_minutes <= 0:
            continue
        deadline = _exam_deadline(exam, timezone_name)
        last_day = min(horizon_end, deadline.astimezone(zone).date()) if deadline else horizon_end
        if last_day < horizon_start:
            continue
        topic, prerequisite_satisfied = _candidate_topic(db, user, exam)
        priority = 50
        goal_id = None
        try:
            from app.domains.goals.service import priority_signal

            priority, goal_id = priority_signal(db, user, domain="learning", source_entity_type="exam", source_entity_id=exam.id)
        except Exception as exc:
            logger.warning(
                "Optional Goals priority signal failed for Learning",
                extra={"user_id": user.id, "exam_id": exam.id, "error_type": type(exc).__name__},
            )
        priority = min(100, priority + {"low": 0, "moderate": 8, "high": 18, "critical": 28, "infeasible": 35}.get(trajectory.risk, 0))
        week_begin = horizon_start - timedelta(days=horizon_start.weekday())
        week_end = week_begin + timedelta(days=6)
        completed_this_week = sum(
            1
            for session in _sessions_for_exam(db, user, exam)
            if session.completion_status == "completed" and week_begin <= session.occurred_at.date() <= week_end
        )
        occurrence = completed_this_week + 1
        days_in_window = (last_day - horizon_start).days + 1
        rolling_minutes = min(trajectory.remaining_quality_adjusted_minutes, max(10, ceil(trajectory.required_daily_minutes * days_in_window)))
        target = min(90, max(10, rolling_minutes))
        variants = [ActionVariantSpec("full", target, min(45, target), target, 5, 1.0)]
        for name, minutes, rank, quality in (("standard", min(60, target), 4, .9), ("reduced", min(30, target), 3, .75), ("minimum", min(25, target), 2, .6), ("activation", min(15, target), 1, .45)):
            if minutes < target and minutes >= 10 and all(item.duration_minutes != minutes for item in variants):
                variants.append(ActionVariantSpec(name, minutes, min(10, minutes), minutes, rank, quality))
        requirement_key = f"learning:exam:{exam.id}:week:{week_begin.isoformat()}:occurrence:{occurrence}"
        result.append(
            PlanningRequirement(
                key=requirement_key,
                domain="learning",
                title=f"{exam.title}: {topic.title if topic else 'exam preparation'}",
                source_entity_type="exam",
                source_entity_id=exam.id,
                reason=f"{trajectory.remaining_quality_adjusted_minutes} effective minutes remain; {rolling_minutes} minutes are required in the rolling window and risk is {trajectory.risk}.",
                deadline=deadline,
                variants=tuple(variants),
                level="goal_critical" if exam.importance in {"goal_critical", "critical", "high"} else "maintenance",
                priority=priority,
                location=exam.location,
                context="study",
                goal_id=goal_id,
                metadata={
                    "exam_id": exam.id,
                    "course_id": exam.course_id,
                    "topic_id": topic.id if topic else None,
                    "risk": trajectory.risk,
                    "readiness_score": trajectory.readiness_score,
                    "rolling_requirement_minutes": rolling_minutes,
                    "prerequisite_satisfied": prerequisite_satisfied,
                    "cognitive_load": 75,
                    "activation_difficulty": 45 if prerequisite_satisfied else 60,
                    "trajectory_value": priority,
                    "neglect_cost": priority,
                    "splittable": False,
                },
            )
        )
    return result


def sync_candidate_actions(
    db: Session,
    user: UserProfile,
    *,
    horizon_start: date | None = None,
    horizon_end: date | None = None,
):
    start = horizon_start or _now().date()
    end = horizon_end or start + timedelta(days=9)
    for action in list_actions(db, user, status_filter="active", domain="learning"):
        if action.requirement_key is None and isinstance(action.metadata_json, dict) and action.metadata_json.get("learning_candidate_id"):
            action.status = "archived"
            action.version += 1
    requirements = planning_requirements(db, user, horizon_start=start, horizon_end=end)
    reconcile_requirements(db, user, "learning", requirements)
    return list_actions(db, user, planning_pool=True, domain="learning")


def status_summary(db: Session, user: UserProfile) -> LearningStatusRead:
    courses = list_courses(db, user)
    exams = list_exams(db, user)
    exam_reads = [exam_to_read(db, user, exam) for exam in exams]
    active_exam = sorted(
        [item for item in exam_reads if item.status in {"planned", "active"}],
        key=lambda item: (
            {"infeasible": 0, "critical": 1, "high": 2, "moderate": 3, "low": 4}.get(item.trajectory.risk if item.trajectory else "low", 5),
            item.exam_at or datetime.max.replace(tzinfo=UTC),
        ),
    )
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.status == "current", Plan.planning_day == _now().date()).order_by(Plan.generated_at.desc()))
    plan_blocks: list[dict[str, Any]] = []
    if plan is not None:
        plan_blocks = [
            {
                "id": block.id,
                "title": block.title,
                "starts_at": block.starts_at.isoformat(),
                "ends_at": block.ends_at.isoformat(),
                "status": block.status,
                "action_id": block.action_id,
            }
            for block in db.scalars(select(PlanBlock).where(PlanBlock.plan_id == plan.id, PlanBlock.domain == "learning").order_by(PlanBlock.starts_at)).all()
        ]
    return LearningStatusRead(
        courses=[CourseRead.model_validate(course) for course in courses],
        exams=exam_reads,
        active_exam=active_exam[0] if active_exam else None,
        candidates=learning_candidates(db, user),
        recent_sessions=[StudySessionRead.model_validate(item) for item in list_study_sessions(db, user, limit=12)],
        current_learning_plan_window=plan_blocks,
    )


def learning_context(db: Session, user: UserProfile) -> LearningContextRead:
    status = status_summary(db, user)
    return LearningContextRead(
        active_exams=[exam.model_dump(mode="json") for exam in status.exams if exam.status in {"planned", "active"}][:5],
        recent_study_sessions=[session.model_dump(mode="json") for session in status.recent_sessions],
        current_learning_plan_window=status.current_learning_plan_window,
        candidate_summary=[candidate.model_dump(mode="json") for candidate in status.candidates[:8]],
        allowed_tools=["get_learning_status", "log_study_session", "create_course", "create_exam", "update_exam", "get_exam_status"],
    )
