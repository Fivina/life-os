from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.attention.schemas import AttentionAction, AttentionDecision
from app.attention.service import AttentionItemService
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.models import CognitiveTrace, Exam, Plan, PlanProposal, StudyRequirement, UserProfile
from app.decision.context import DecisionContextBuilder
from app.decision.errors import DecisionError
from app.decision.gateway import DecisionGateway
from app.decision.questions import STRATEGY_INTERVENTION_NEEDED_V1
from app.decision.schemas import CognitiveEvent, EntityReference, ProvenanceReference
from app.decision.traces import DecisionTraceService
from app.events.service import append_event
from app.personal_model.service import record_plan_proposal_outcome
from app.planning.service import get_current_plan
from app.planning.strategy import apply_strategy_candidate, simulate_strategic_recovery
from app.strategy.intervention import InterventionEngine
from app.strategy.monitor import StrategicMonitor
from app.strategy.schemas import (
    AuthorityLevel,
    ExamTrajectorySnapshot,
    InterventionDecision,
    PlanProposalRead,
    ProposalModificationRequest,
    ProposalStatus,
    PROPOSAL_POLICY_VERSION,
    StrategicEvaluationRead,
)


logger = get_logger(__name__)
ACTIVE_STATUSES = (ProposalStatus.draft.value, ProposalStatus.presented.value)
REJECTION_COOLDOWN_DAYS = 7


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PlanProposalService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        monitor: StrategicMonitor | None = None,
        intervention_engine: InterventionEngine | None = None,
        gateway: DecisionGateway | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.monitor = monitor or StrategicMonitor()
        self.intervention_engine = intervention_engine or InterventionEngine()
        self.gateway = gateway or DecisionGateway(self.settings)

    def evaluate_exam(
        self,
        db: Session,
        user: UserProfile,
        exam_id: str,
        *,
        trigger: str = "manual",
        now: datetime | None = None,
        create_proposal: bool = True,
    ) -> StrategicEvaluationRead:
        exam = self._exam(db, user, exam_id)
        snapshot = self.monitor.assess_exam(db, user, exam, now=now)
        deviation = self.monitor.deviation(snapshot, trigger=trigger)
        provider_judgment, trace_id = self._provider_judgment(db, user, snapshot, deviation, trigger)
        intervention = self.intervention_engine.decide(
            snapshot,
            deviation,
            provider_judgment=provider_judgment,
            source_trace_id=trace_id,
        )
        proposal = None
        deduplicated = False
        if create_proposal and deviation is not None and intervention.authority_level >= AuthorityLevel.prepare_proposal:
            current_plan = get_current_plan(db, user)
            if current_plan is not None:
                proposal, deduplicated = self._create(
                    db,
                    user,
                    exam,
                    current_plan,
                    snapshot,
                    deviation.model_dump(mode="json"),
                    intervention,
                    trigger=trigger,
                )
        return StrategicEvaluationRead(
            snapshot=snapshot,
            deviation=deviation,
            intervention=intervention,
            proposal=self.to_read(proposal) if proposal is not None else None,
            deduplicated=deduplicated,
        )

    def evaluate_relevant_event(self, db: Session, user: UserProfile, *, event_type: str, payload: dict[str, Any]) -> int:
        exam_id = payload.get("exam_id")
        exams: list[Exam]
        if exam_id:
            row = db.scalar(select(Exam).where(Exam.id == str(exam_id), Exam.user_id == user.id))
            exams = [row] if row is not None else []
        else:
            exams = list(db.scalars(
                select(Exam).where(Exam.user_id == user.id, Exam.status.in_(("planned", "active"))).order_by(Exam.exam_at, Exam.exam_date).limit(8)
            ))
        created = 0
        for exam in exams:
            result = self.evaluate_exam(db, user, exam.id, trigger=event_type)
            if result.proposal is not None and not result.deduplicated:
                created += 1
        return created

    def get(self, db: Session, user: UserProfile, proposal_id: str, *, lock: bool = False) -> PlanProposal:
        query = select(PlanProposal).where(PlanProposal.id == proposal_id, PlanProposal.user_id == user.id)
        if lock:
            query = query.with_for_update()
        row = db.scalar(query)
        if row is None:
            raise LookupError("Plan proposal not found.")
        self._expire_if_due(row)
        return row

    def list_active(self, db: Session, user: UserProfile, *, limit: int = 20) -> list[PlanProposal]:
        rows = list(db.scalars(
            select(PlanProposal)
            .where(PlanProposal.user_id == user.id, PlanProposal.status.in_(ACTIVE_STATUSES))
            .order_by(PlanProposal.created_at.desc())
            .limit(max(1, min(limit, 100)))
        ))
        for row in rows:
            self._expire_if_due(row)
        return [row for row in rows if row.status in ACTIVE_STATUSES]

    def present(self, db: Session, user: UserProfile, proposal_id: str, *, now: datetime | None = None) -> PlanProposal:
        row = self.get(db, user, proposal_id, lock=True)
        if row.status == ProposalStatus.presented.value:
            return row
        if row.status != ProposalStatus.draft.value:
            raise ValueError("Only a draft proposal can be presented.")
        row.status = ProposalStatus.presented.value
        row.presented_at = now or utcnow()
        row.version += 1
        self._event(db, user, row, "strategy.proposal.presented")
        logger.info("proposal_presented", extra={"proposal_id": row.id, "user_id": user.id})
        return row

    def accept(self, db: Session, user: UserProfile, proposal_id: str, *, now: datetime | None = None) -> PlanProposal:
        when = now or utcnow()
        row = self.get(db, user, proposal_id, lock=True)
        self._require_open(row)
        if _aware(row.expires_at) <= _aware(when):
            self._mark_expired(row, when)
            raise ValueError("Proposal expired and must be re-simulated.")
        exam = self._exam(db, user, row.exam_id)
        if row.metadata_json.get("canonical_signature") != self._canonical_signature(db, exam):
            logger.info("proposal_stale_on_accept", extra={"proposal_id": row.id, "reason": "learning_state_changed"})
            raise ValueError("Proposal is stale because exam or requirement state changed; re-simulation is required.")
        try:
            applied = apply_strategy_candidate(
                db,
                user,
                current_plan_id=row.current_plan_id,
                current_plan_version=row.current_plan_version,
                expected_world_revision=row.current_world_revision,
                candidate=row.candidate_plan_json,
                proposal_id=row.id,
            )
        except ValueError:
            logger.info("proposal_stale_on_accept", extra={"proposal_id": row.id, "reason": "plan_changed"})
            raise
        row.status = ProposalStatus.accepted.value
        row.accepted_at = when
        row.applied_plan_id = applied.id
        row.version += 1
        evidence = self._record_outcome(db, user, row, "ACCEPT")
        self._audit_outcome(db, user, row, "proposal_accepted", evidence.id)
        self._event(db, user, row, "strategy.proposal.accepted", {"applied_plan_id": applied.id})
        logger.info("proposal_accepted", extra={"proposal_id": row.id, "applied_plan_id": applied.id})
        return row

    def modify(
        self,
        db: Session,
        user: UserProfile,
        proposal_id: str,
        request: ProposalModificationRequest,
        *,
        now: datetime | None = None,
    ) -> PlanProposal:
        original = self.get(db, user, proposal_id, lock=True)
        self._require_open(original)
        current = db.scalar(
            select(Plan).where(Plan.id == original.current_plan_id, Plan.user_id == user.id).options(selectinload(Plan.blocks))
        )
        if current is None or current.status != "current" or current.version != original.current_plan_version:
            raise ValueError("Proposal is stale; start from a fresh strategic evaluation.")
        exam = self._exam(db, user, original.exam_id)
        snapshot = self.monitor.assess_exam(db, user, exam, now=now)
        deviation = self.monitor.deviation(snapshot, trigger="proposal.modified")
        if deviation is None:
            raise ValueError("The refreshed trajectory no longer requires a proposal.")
        original.status = ProposalStatus.modified.value
        original.modified_at = now or utcnow()
        original.modification_json = request.model_dump(mode="json")
        original.version += 1
        evidence = self._record_outcome(db, user, original, "MODIFY", request.model_dump(mode="json"))
        self._audit_outcome(db, user, original, "proposal_modified", evidence.id)
        self._event(db, user, original, "strategy.proposal.modified")
        intervention = self.intervention_engine.decide(snapshot, deviation, source_trace_id=original.source_trace_id)
        replacement, _ = self._create(
            db,
            user,
            exam,
            current,
            snapshot,
            deviation.model_dump(mode="json"),
            intervention,
            trigger="proposal.modified",
            modification=request,
            parent_proposal_id=original.id,
        )
        return replacement

    def reject(self, db: Session, user: UserProfile, proposal_id: str, *, now: datetime | None = None) -> PlanProposal:
        when = now or utcnow()
        row = self.get(db, user, proposal_id, lock=True)
        self._require_open(row)
        row.status = ProposalStatus.rejected.value
        row.rejected_at = when
        row.rejection_cooldown_until = when + timedelta(days=REJECTION_COOLDOWN_DAYS)
        row.version += 1
        evidence = self._record_outcome(db, user, row, "REJECT")
        self._audit_outcome(db, user, row, "proposal_rejected", evidence.id)
        self._event(db, user, row, "strategy.proposal.rejected")
        logger.info("proposal_rejected", extra={"proposal_id": row.id})
        return row

    def expire_due(self, db: Session, user: UserProfile, *, now: datetime | None = None) -> int:
        when = now or utcnow()
        rows = list(db.scalars(
            select(PlanProposal).where(
                PlanProposal.user_id == user.id,
                PlanProposal.status.in_(ACTIVE_STATUSES),
                PlanProposal.expires_at <= when,
            ).with_for_update()
        ))
        for row in rows:
            self._mark_expired(row, when)
            self._event(db, user, row, "strategy.proposal.expired")
        return len(rows)

    def _create(
        self,
        db: Session,
        user: UserProfile,
        exam: Exam,
        current_plan: Plan,
        snapshot: ExamTrajectorySnapshot,
        deviation: dict[str, Any],
        intervention: InterventionDecision,
        *,
        trigger: str,
        modification: ProposalModificationRequest | None = None,
        parent_proposal_id: str | None = None,
    ) -> tuple[PlanProposal, bool]:
        dedup = hashlib.sha256(
            f"{exam.id}:{current_plan.id}:{current_plan.version}:{deviation['fingerprint']}:{PROPOSAL_POLICY_VERSION}:{parent_proposal_id or ''}".encode()
        ).hexdigest()[:48]
        dedup_key = f"strategy:{dedup}"
        existing = db.scalar(select(PlanProposal).where(PlanProposal.user_id == user.id, PlanProposal.deduplication_key == dedup_key))
        if existing is not None:
            logger.info("proposal_deduplicated", extra={"proposal_id": existing.id, "exam_id": exam.id})
            return existing, True
        cooldown = db.scalar(
            select(PlanProposal)
            .where(
                PlanProposal.user_id == user.id,
                PlanProposal.exam_id == exam.id,
                PlanProposal.status == ProposalStatus.rejected.value,
                PlanProposal.rejection_cooldown_until > utcnow(),
                PlanProposal.deviation_fingerprint == deviation["fingerprint"],
            )
            .order_by(PlanProposal.rejected_at.desc())
            .limit(1)
        )
        if cooldown is not None:
            logger.info("intervention_suppressed", extra={"exam_id": exam.id, "reason": "rejection_cooldown"})
            return cooldown, True

        simulation = simulate_strategic_recovery(db, user, current_plan, snapshot, modification=modification)
        confidence = {
            "data_completeness": snapshot.completeness_score,
            "deterministic_calculation": 1.0 if snapshot.completeness.value == "COMPLETE" else 0.7,
            "planner_feasibility": 1.0 if simulation["overload_status"] in {"feasible", "tight"} else 0.45,
            "decision_provider": intervention.confidence if intervention.provider_judgment else None,
            "host_policy": intervention.confidence,
        }
        expiry = min(
            [value for value in (snapshot.exam_at, utcnow() + timedelta(days=7)) if value is not None],
            default=utcnow() + timedelta(days=7),
        )
        row = PlanProposal(
            user_id=user.id,
            exam_id=exam.id,
            source_trace_id=intervention.source_trace_id,
            parent_proposal_id=parent_proposal_id,
            current_plan_id=current_plan.id,
            current_plan_version=current_plan.version,
            current_world_revision=user.world_revision,
            trigger=trigger[:120],
            reason_code=intervention.reason_code,
            deviation_fingerprint=deviation["fingerprint"],
            deduplication_key=dedup_key,
            trajectory_snapshot_json=snapshot.model_dump(mode="json"),
            deviation_json=deviation,
            candidate_plan_json=simulation,
            changes_json=simulation["changes"],
            expected_effects_json=simulation["expected_effects"],
            tradeoffs_json=simulation["tradeoffs"],
            confidence_json=confidence,
            modification_json=modification.model_dump(mode="json") if modification else {},
            authority_level=int(intervention.authority_level),
            attention_action=intervention.attention_action.value,
            status=ProposalStatus.draft.value,
            expires_at=expiry,
            policy_version=PROPOSAL_POLICY_VERSION,
            planner_version=simulation["planner_version"],
            calculation_version=snapshot.calculation_version,
            metadata_json={
                "canonical_signature": self._canonical_signature(db, exam),
                "provider_judgment": intervention.provider_judgment,
                "contextual_outcomes_only": True,
            },
        )
        db.add(row)
        db.flush()
        self._event(db, user, row, "strategy.proposal.created")
        self._queue_attention(db, user, row, intervention)
        logger.info("proposal_created", extra={"proposal_id": row.id, "exam_id": exam.id, "authority_level": row.authority_level})
        return row, False

    def _provider_judgment(
        self,
        db: Session,
        user: UserProfile,
        snapshot: ExamTrajectorySnapshot,
        deviation: Any,
        trigger: str,
    ) -> tuple[str | None, str | None]:
        if not self.settings.decision_infra_enabled or deviation is None:
            return None, None
        event = CognitiveEvent(
            event_type="strategy.trajectory.assessed",
            source="strategic_monitor",
            domains=("learning", "planning"),
            entity_refs=(EntityReference(entity_type="exam", entity_id=snapshot.exam_id, role="trajectory"),),
            world_revision=snapshot.source_world_revision,
            input_payload={"trigger": trigger, "deviation_fingerprint": deviation.fingerprint},
        )
        facts = {
            "severity": deviation.severity.value,
            "recoverability": deviation.recoverability.value,
            "magnitude_minutes": deviation.magnitude_minutes,
            "days_remaining": deviation.days_remaining,
            "data_completeness": snapshot.completeness.value,
            "planned_future_minutes": snapshot.planned_future_minutes,
            "projected_shortfall_minutes": snapshot.projected_shortfall_minutes,
        }
        provenance = {
            key: (ProvenanceReference(source_type="trajectory_snapshot", source_id=snapshot.exam_id, observed_at=snapshot.as_of),)
            for key in facts
        }
        context = DecisionContextBuilder().build(
            event=event,
            question=STRATEGY_INTERVENTION_NEEDED_V1,
            facts=facts,
            provenance=provenance,
        )
        try:
            execution = self.gateway.evaluate(
                db,
                user,
                event=event,
                question=STRATEGY_INTERVENTION_NEEDED_V1,
                context=context,
                trace_metadata={
                    "strategic_path": {
                        "trajectory_snapshot": snapshot.model_dump(mode="json"),
                        "deviation": deviation.model_dump(mode="json"),
                        "calculation_version": snapshot.calculation_version,
                    }
                },
            )
            return str(execution.result.selected_answer), execution.trace_id
        except DecisionError as exc:
            logger.warning("strategic_decision_degraded", extra={"exam_id": snapshot.exam_id, "error_code": exc.code})
            return None, None

    def _queue_attention(
        self,
        db: Session,
        user: UserProfile,
        proposal: PlanProposal,
        intervention: InterventionDecision,
    ) -> None:
        if intervention.attention_action in {AttentionAction.silent, AttentionAction.act_silently}:
            return
        decision = AttentionDecision(
            action=intervention.attention_action,
            reason_code=intervention.reason_code,
            subject=f"Plan proposal for {proposal.trajectory_snapshot_json.get('exam_title', 'exam')}",
            priority=intervention.priority,
            urgency=intervention.urgency,
            confidence=intervention.confidence,
            evidence_quality=float(proposal.confidence_json.get("data_completeness") or 0),
            expires_at=proposal.expires_at,
            source_trace_id=proposal.source_trace_id,
            policy_version="attention-policy-v1",
            metadata={"proposal_id": proposal.id},
        )
        AttentionItemService().enqueue(
            db,
            user,
            decision,
            deduplication_key=f"plan-proposal:{proposal.id}",
            payload={"proposal_id": proposal.id, "exam_id": proposal.exam_id},
            metadata={"authority_level": proposal.authority_level},
        )

    @staticmethod
    def _canonical_signature(db: Session, exam: Exam) -> str:
        requirements = list(db.scalars(
            select(StudyRequirement).where(StudyRequirement.exam_id == exam.id).order_by(StudyRequirement.id)
        ))
        material = {
            "exam": {"id": exam.id, "version": exam.version, "exam_at": str(exam.exam_at), "exam_date": str(exam.exam_date)},
            "requirements": [
                {"id": row.id, "version": row.version, "estimate": row.estimated_required_minutes, "completed": row.completed_minutes, "status": row.status}
                for row in requirements
            ],
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _exam(db: Session, user: UserProfile, exam_id: str) -> Exam:
        exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.user_id == user.id))
        if exam is None:
            raise LookupError("Exam not found.")
        return exam

    @staticmethod
    def _expire_if_due(row: PlanProposal) -> None:
        if row.status in ACTIVE_STATUSES and _aware(row.expires_at) <= utcnow():
            PlanProposalService._mark_expired(row, utcnow())

    @staticmethod
    def _mark_expired(row: PlanProposal, when: datetime) -> None:
        row.status = ProposalStatus.expired.value
        row.expired_at = when
        row.version += 1

    @staticmethod
    def _require_open(row: PlanProposal) -> None:
        if row.status not in ACTIVE_STATUSES:
            raise ValueError(f"Proposal is {row.status.lower()} and cannot be changed.")

    @staticmethod
    def _event(
        db: Session,
        user: UserProfile,
        row: PlanProposal,
        event_type: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        prior_revision = user.world_revision
        append_event(
            db,
            user,
            event_type=event_type,
            aggregate_type="plan_proposal",
            aggregate_id=row.id,
            payload={"proposal_id": row.id, "exam_id": row.exam_id, "status": row.status, **(extra or {})},
            outbox=True,
            increment_world_revision=True,
        )
        # A proposal's own lifecycle event must be visible to other clients without
        # making that same event render the proposal stale for later acceptance.
        if row.current_world_revision == prior_revision and row.status in ACTIVE_STATUSES:
            row.current_world_revision = user.world_revision

    @staticmethod
    def _record_outcome(
        db: Session,
        user: UserProfile,
        row: PlanProposal,
        choice: str,
        modification: dict[str, Any] | None = None,
    ):
        return record_plan_proposal_outcome(
            db,
            user,
            proposal_id=row.id,
            plan_id=row.current_plan_id,
            exam_id=row.exam_id,
            choice=choice,
            strategic_context={
                "deviation": row.deviation_json,
                "expected_effects": row.expected_effects_json,
                "calculation_version": row.calculation_version,
            },
            tradeoffs=row.tradeoffs_json,
            authority_level=row.authority_level,
            attention_action=row.attention_action,
            modification=modification,
        )

    @staticmethod
    def _audit_outcome(db: Session, user: UserProfile, row: PlanProposal, audit_type: str, evidence_id: str) -> None:
        if not row.source_trace_id:
            return
        trace = db.scalar(select(CognitiveTrace).where(CognitiveTrace.id == row.source_trace_id, CognitiveTrace.user_id == user.id))
        if trace is None:
            return
        DecisionTraceService().add_audit(
            db,
            user,
            trace=trace,
            audit_type=audit_type,
            outcome={"proposal_id": row.id, "status": row.status},
            downstream_action_ref=row.applied_plan_id,
            training_eligible=True,
            metadata={"personal_learning_evidence_id": evidence_id},
        )

    @staticmethod
    def to_read(row: PlanProposal | None) -> PlanProposalRead | None:
        if row is None:
            return None
        return PlanProposalRead(
            id=row.id,
            exam_id=row.exam_id,
            source_trace_id=row.source_trace_id,
            parent_proposal_id=row.parent_proposal_id,
            current_plan_id=row.current_plan_id,
            current_plan_version=row.current_plan_version,
            current_world_revision=row.current_world_revision,
            applied_plan_id=row.applied_plan_id,
            trigger=row.trigger,
            reason_code=row.reason_code,
            trajectory_snapshot=row.trajectory_snapshot_json,
            deviation=row.deviation_json,
            candidate_plan=row.candidate_plan_json,
            changes=row.changes_json,
            expected_effects=row.expected_effects_json,
            tradeoffs=row.tradeoffs_json,
            confidence=row.confidence_json,
            modification=row.modification_json,
            authority_level=row.authority_level,
            attention_action=AttentionAction(row.attention_action),
            status=ProposalStatus(row.status),
            expires_at=row.expires_at,
            presented_at=row.presented_at,
            accepted_at=row.accepted_at,
            modified_at=row.modified_at,
            rejected_at=row.rejected_at,
            expired_at=row.expired_at,
            policy_version=row.policy_version,
            planner_version=row.planner_version,
            calculation_version=row.calculation_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )
