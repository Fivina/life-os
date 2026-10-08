from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.attention.manager import AttentionManager
from app.attention.schemas import AttentionAction, AttentionCandidate
from app.attention.service import AttentionItemService
from app.core.config import Settings, get_settings
from app.database.models import (
    Goal, OpenThread, Opportunity, OpportunityExternalId, OpportunitySourceState, OpportunityUserState,
    PatternEvidence, ProspectiveThread, RecommendationOption, SocialActivity, Trajectory, UserProfile,
)
from app.decision.context import DecisionContextBuilder
from app.decision.errors import DecisionError
from app.decision.gateway import DecisionGateway
from app.decision.questions import OPPORTUNITY_RELEVANCE_V1
from app.decision.schemas import CognitiveEvent, EntityReference, ProvenanceReference
from app.domains.finance.contracts import SocialBudgetSignal, discretionary_social_budget_remaining
from app.events.service import append_event
from app.memory.schemas import RecommendationCreate, RecommendationOptionCreate, RecommendationOutcomeCreate
from app.planning.opportunity_feasibility import OpportunityFeasibility, evaluate_opportunity
from app.recommendations.service import create_recommendation, record_outcome
from app.social.providers import OpportunitySource, TicketmasterOpportunitySource
from app.social.schemas import (
    DiscoveryContext, DiscoverySummary, NormalizedOpportunity, OpportunityOutcomeCreate, OpportunityRead,
    OpportunitySourceRead, OpportunitySourceUpdate, OpportunityType, SocialActionCandidate, SocialActionType,
    SocialActivityCreate, SocialActivityRead, SocialTrajectoryRead, SocialTrajectoryUpdate,
)


logger = logging.getLogger("life_os.social")
SOCIAL_GOAL_SOURCE = "social_trajectory"
SOCIAL_POLICY_VERSION = "social-opportunity-v1"
AMBIGUOUS_SCORE_RANGE = (34.0, 59.0)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _week_bounds(now: datetime, week_starts_on: int) -> tuple[datetime, datetime]:
    local = _aware(now)
    start = (local - timedelta(days=(local.weekday() - week_starts_on) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def _trajectory_rows(db: Session, user: UserProfile) -> tuple[Goal, Trajectory]:
    goal = db.scalar(select(Goal).where(Goal.user_id == user.id, Goal.source_entity_type == SOCIAL_GOAL_SOURCE))
    if goal is None:
        goal = Goal(
            user_id=user.id, title="Meaningful social activity", domain="social", status="active", priority=45,
            horizon="ongoing", success_condition="Configurable meaningful activities per week",
            progress_mode="automatic", source_entity_type=SOCIAL_GOAL_SOURCE, active=True,
        )
        db.add(goal); db.flush(); goal.source_entity_id = goal.id
    trajectory = db.scalar(select(Trajectory).where(Trajectory.user_id == user.id, Trajectory.source_entity_type == SOCIAL_GOAL_SOURCE))
    if trajectory is None:
        trajectory = Trajectory(
            user_id=user.id, goal_id=goal.id, name="Meaningful social activity", metric_name="meaningful_activities",
            target_value=2, current_value=0, unit="activities/week", status="below_range", risk="none", on_track=False,
            source_domain="social", source_entity_type=SOCIAL_GOAL_SOURCE, source_entity_id=goal.id,
            metadata_json={"enabled": True, "target_min": 2, "target_max": 3, "week_starts_on": 0,
                           "qualification": "explicitly logged meaningful activity or attended opportunity"},
        )
        db.add(trajectory); db.flush()
    return goal, trajectory


def get_social_trajectory(db: Session, user: UserProfile, *, now: datetime | None = None) -> SocialTrajectoryRead:
    goal, trajectory = _trajectory_rows(db, user)
    metadata = trajectory.metadata_json or {}
    enabled = bool(metadata.get("enabled", True)); minimum = int(metadata.get("target_min", 2)); maximum = int(metadata.get("target_max", 3))
    week_start = int(metadata.get("week_starts_on", 0)); start, end = _week_bounds(now or _now(), week_start)
    count = int(db.scalar(select(func.count(SocialActivity.id)).where(
        SocialActivity.user_id == user.id, SocialActivity.meaningful.is_(True),
        SocialActivity.occurred_at >= start, SocialActivity.occurred_at < end,
    )) or 0)
    state = "DISABLED" if not enabled else "BELOW_RANGE" if count < minimum else "ABOVE_RANGE" if count > maximum else "IN_RANGE"
    trajectory.current_value = count; trajectory.target_value = minimum; trajectory.status = state.lower(); trajectory.on_track = None if not enabled else count >= minimum; trajectory.calculated_at = now or _now()
    return SocialTrajectoryRead(
        goal_id=goal.id, trajectory_id=trajectory.id, enabled=enabled, target_min=minimum, target_max=maximum,
        week_starts_on=week_start, period_start=start, period_end=end, completed_count=count, state=state,
        remaining_to_min=max(0, minimum - count) if enabled else 0,
        qualification=str(metadata.get("qualification") or "explicitly logged meaningful activity or attended opportunity"),
    )


def update_social_trajectory(db: Session, user: UserProfile, payload: SocialTrajectoryUpdate) -> SocialTrajectoryRead:
    goal, trajectory = _trajectory_rows(db, user)
    trajectory.metadata_json = {**(trajectory.metadata_json or {}), **payload.model_dump(),
                                "qualification": "explicitly logged meaningful activity or attended opportunity"}
    trajectory.target_value = payload.target_min; trajectory.version += 1
    goal.active = payload.enabled; goal.status = "active" if payload.enabled else "paused"; goal.version += 1
    append_event(db, user, event_type="social.trajectory_changed", aggregate_type="trajectory", aggregate_id=trajectory.id,
                 payload={"enabled": payload.enabled, "target_min": payload.target_min, "target_max": payload.target_max}, outbox=True)
    return get_social_trajectory(db, user)


def log_social_activity(db: Session, user: UserProfile, payload: SocialActivityCreate) -> SocialActivityRead:
    if payload.idempotency_key:
        existing = db.scalar(select(SocialActivity).where(SocialActivity.user_id == user.id, SocialActivity.idempotency_key == payload.idempotency_key))
        if existing:
            return SocialActivityRead.model_validate(existing)
    row = SocialActivity(user_id=user.id, activity_type=payload.activity_type.value, title=payload.title,
                         occurred_at=payload.occurred_at, meaningful=payload.meaningful, source=payload.source,
                         source_ref=payload.source_ref, idempotency_key=payload.idempotency_key, metadata_json=payload.metadata)
    db.add(row); db.flush()
    append_event(db, user, event_type="social.activity_recorded", aggregate_type="social_activity", aggregate_id=row.id,
                 payload={"activity_id": row.id, "activity_type": row.activity_type, "meaningful": row.meaningful}, outbox=True)
    return SocialActivityRead.model_validate(row)


def _canonical_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _source_hash(item: NormalizedOpportunity) -> str:
    material = item.model_dump(mode="json", exclude={"source_updated_at"})
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def upsert_opportunity(db: Session, user: UserProfile, item: NormalizedOpportunity) -> tuple[Opportunity, str]:
    external = db.scalar(select(OpportunityExternalId).where(
        OpportunityExternalId.user_id == user.id, OpportunityExternalId.provider == item.provider,
        OpportunityExternalId.external_id == item.external_id,
    ))
    row = db.get(Opportunity, external.opportunity_id) if external else None
    canonical = _canonical_title(item.title)
    if row is None:
        row = db.scalar(select(Opportunity).where(
            Opportunity.user_id == user.id, Opportunity.canonical_title == canonical,
            Opportunity.starts_at == item.starts_at, func.coalesce(Opportunity.venue, "") == (item.venue or ""),
        ))
    action = "deduplicated" if row is not None and external is None else "updated" if row is not None else "created"
    digest = _source_hash(item)
    if row is None:
        row = Opportunity(user_id=user.id, opportunity_type=item.opportunity_type.value, title=item.title,
                          canonical_title=canonical, description=item.description, starts_at=item.starts_at, ends_at=item.ends_at,
                          timezone=item.timezone, venue=item.venue, city=item.city, region=item.region,
                          country_code=item.country_code.upper() if item.country_code else None, source_url=item.source_url,
                          cost_min=item.cost_min, cost_max=item.cost_max, currency=item.currency.upper() if item.currency else None,
                          pricing_source=item.pricing_source, status=item.status, tags_json=list(item.tags),
                          entities_json=list(item.entities), source_updated_at=item.source_updated_at, source_hash=digest,
                          metadata_json={**item.metadata, "providers": [item.provider]})
        db.add(row); db.flush()
    elif row.source_hash != digest or action == "deduplicated":
        row.opportunity_type=item.opportunity_type.value; row.title=item.title; row.canonical_title=canonical
        row.description=item.description; row.starts_at=item.starts_at; row.ends_at=item.ends_at; row.timezone=item.timezone
        row.venue=item.venue; row.city=item.city; row.region=item.region; row.country_code=item.country_code.upper() if item.country_code else None
        row.source_url=item.source_url or row.source_url; row.cost_min=item.cost_min; row.cost_max=item.cost_max
        row.currency=item.currency.upper() if item.currency else None; row.pricing_source=item.pricing_source
        row.status=item.status; row.tags_json=sorted(set(row.tags_json or []) | set(item.tags)); row.entities_json=list(item.entities)
        row.source_updated_at=item.source_updated_at; row.source_hash=digest; row.version += 1
        providers = set((row.metadata_json or {}).get("providers", [])); providers.add(item.provider)
        row.metadata_json = {**(row.metadata_json or {}), **item.metadata, "providers": sorted(providers)}
    if external is None:
        db.add(OpportunityExternalId(opportunity_id=row.id, user_id=user.id, provider=item.provider,
                                     external_id=item.external_id, source_url=item.source_url)); db.flush()
    if action in {"created", "updated"}:
        event_suffix = "discovered" if action == "created" else "updated"
        append_event(db, user, event_type=f"opportunity.{event_suffix}", aggregate_type="opportunity", aggregate_id=row.id,
                     payload={"opportunity_id": row.id, "type": row.opportunity_type, "provider": item.provider}, outbox=True)
    logger.info("opportunity_%s", action, extra={"opportunity_id": row.id, "provider": item.provider})
    return row, action


def _tokens(value: str) -> set[str]:
    return {token for token in _canonical_title(value).split() if len(token) >= 3}


def _thread_match(opportunity: Opportunity, threads: Iterable[Any]) -> tuple[float, list[str]]:
    haystack = _tokens(" ".join([opportunity.title, *(opportunity.tags_json or []),
                                 *(str(item.get("name", "")) for item in (opportunity.entities_json or []))]))
    best = 0.0; refs: list[str] = []
    for thread in threads:
        needle = _tokens(f"{thread.subject} {thread.intent}")
        if needle and haystack.intersection(needle):
            best = max(best, 1.0); refs.append(thread.id)
    return best, refs


def hard_filter(db: Session, user: UserProfile, opportunity: Opportunity, context: DiscoveryContext,
                budget: SocialBudgetSignal, *, now: datetime | None = None) -> list[str]:
    when = now or _now(); reasons: list[str] = []
    if opportunity.status != "ACTIVE": reasons.append("inactive_source_state")
    if _aware(opportunity.ends_at or opportunity.starts_at) < _aware(when): reasons.append("event_ended")
    if context.city and opportunity.city and context.city.casefold() != opportunity.city.casefold(): reasons.append("outside_configured_city")
    if context.region and opportunity.region and context.region.casefold() != opportunity.region.casefold(): reasons.append("outside_configured_region")
    state = db.scalar(select(OpportunityUserState).where(OpportunityUserState.user_id == user.id, OpportunityUserState.opportunity_id == opportunity.id))
    if state and state.status == "DISMISSED": reasons.append("explicitly_dismissed")
    if budget.status == "CONSTRAINED" and budget.amount_remaining is not None and opportunity.cost_min is not None and opportunity.cost_min > budget.amount_remaining:
        reasons.append("above_explicit_budget_signal")
    return reasons


@dataclass
class RankedOpportunity:
    row: Opportunity
    score: float
    factors: dict[str, float]
    reasons: list[str]
    feasibility: OpportunityFeasibility
    thread_refs: list[str]
    prospective_refs: list[str]
    provider_trace_id: str | None = None


def rank_opportunity(db: Session, user: UserProfile, row: Opportunity, trajectory: SocialTrajectoryRead,
                     budget: SocialBudgetSignal, *, settings: Settings | None = None, now: datetime | None = None) -> RankedOpportunity:
    prospective = list(db.scalars(select(ProspectiveThread).where(ProspectiveThread.user_id == user.id, ProspectiveThread.status.in_(["OPEN", "DORMANT"]))))
    open_threads = list(db.scalars(select(OpenThread).where(OpenThread.user_id == user.id, OpenThread.status == "OPEN")))
    p_match, p_refs = _thread_match(row, prospective); o_match, o_refs = _thread_match(row, open_threads)
    learned = db.scalar(select(func.max(PatternEvidence.confidence)).where(
        PatternEvidence.user_id == user.id, PatternEvidence.status == "ACTIVE", PatternEvidence.pattern_type.in_(["social_category", "opportunity_category"])
    )) or 0.0
    start, _ = _week_bounds(now or _now(), trajectory.week_starts_on)
    recent_same = int(db.scalar(select(func.count(SocialActivity.id)).where(
        SocialActivity.user_id == user.id, SocialActivity.activity_type == row.opportunity_type,
        SocialActivity.occurred_at >= start - timedelta(days=21),
    )) or 0)
    feasibility = evaluate_opportunity(db, user, row)
    factors = {
        "explicit_prospective_match": 45.0 * p_match,
        "open_thread_match": 22.0 * o_match,
        "social_trajectory": 8.0 if trajectory.enabled and trajectory.state == "BELOW_RANGE" else 0.0,
        "schedule_feasibility": 12.0 if feasibility.feasible else 4.0 if feasibility.requires_plan_proposal else -30.0,
        "budget_feasibility": 4.0 if budget.status == "AVAILABLE" and (row.cost_min is None or budget.amount_remaining is None or row.cost_min <= budget.amount_remaining) else 0.0,
        "recent_repetition": -min(12.0, recent_same * 4.0),
        "novelty": 4.0 if recent_same == 0 else 0.0,
        "learned_preference": round(float(learned) * 8.0, 2),
        "source_confidence": 5.0,
        "decision_gateway": 0.0,
    }
    score = sum(factors.values()); trace_id = None
    if AMBIGUOUS_SCORE_RANGE[0] <= score <= AMBIGUOUS_SCORE_RANGE[1]:
        adjustment, trace_id = _optional_ambiguity_rank(db, user, row, factors, settings or get_settings())
        factors["decision_gateway"] = adjustment; score += adjustment
    reasons = (["Matches an explicit future interest"] if p_match else []) + (["Connects with an open interest"] if o_match else [])
    if trajectory.enabled and trajectory.state == "BELOW_RANGE": reasons.append("Fits your current weekly activity target")
    if feasibility.feasible: reasons.append("Fits the current calendar")
    return RankedOpportunity(row, round(score, 2), factors, reasons, feasibility, o_refs, p_refs, trace_id)


def _optional_ambiguity_rank(db: Session, user: UserProfile, row: Opportunity, factors: dict[str, float], settings: Settings) -> tuple[float, str | None]:
    if not settings.decision_infra_enabled:
        return 0.0, None
    event = CognitiveEvent(event_type="opportunity.ambiguous_relevance", source="opportunity_pipeline", domains=("social",),
                           entity_refs=(EntityReference(entity_type="opportunity", entity_id=row.id, role="candidate"),),
                           world_revision=user.world_revision, input_payload={"policy_version": SOCIAL_POLICY_VERSION})
    facts = {"opportunity_type": row.opportunity_type, "starts_at": row.starts_at.isoformat(), "factor_total": sum(factors.values())}
    provenance = {key: (ProvenanceReference(source_type="opportunity", source_id=row.id),) for key in facts}
    context = DecisionContextBuilder().build(event=event, question=OPPORTUNITY_RELEVANCE_V1, facts=facts, provenance=provenance)
    try:
        execution = DecisionGateway(settings).evaluate(db, user, event=event, question=OPPORTUNITY_RELEVANCE_V1, context=context,
                                                       trace_metadata={"opportunity_path": {"opportunity_id": row.id, "score_factors": factors}})
    except DecisionError:
        return 0.0, None
    adjustment = {"RELEVANT": 8.0, "UNCERTAIN": 0.0, "IRRELEVANT": -8.0}[str(execution.result.selected_answer)]
    return adjustment, execution.trace_id


def _read(db: Session, user: UserProfile, row: Opportunity, ranked: RankedOpportunity | None = None) -> OpportunityRead:
    state = db.scalar(select(OpportunityUserState).where(OpportunityUserState.user_id == user.id, OpportunityUserState.opportunity_id == row.id))
    return OpportunityRead(
        id=row.id, opportunity_type=OpportunityType(row.opportunity_type), title=row.title, description=row.description,
        starts_at=row.starts_at, ends_at=row.ends_at, timezone=row.timezone, venue=row.venue, city=row.city,
        region=row.region, country_code=row.country_code, source_url=row.source_url, cost_min=row.cost_min,
        cost_max=row.cost_max, currency=row.currency, status=row.status, tags=list(row.tags_json or []),
        user_status=state.status if state else "AVAILABLE", score_factors=ranked.factors if ranked else {},
        reasons=ranked.reasons if ranked else [], feasibility=ranked.feasibility.model_dump(mode="json") if ranked else {},
    )


def list_opportunities(db: Session, user: UserProfile, *, category: OpportunityType | None = None,
                       starts_after: datetime | None = None, status: str = "ACTIVE", relevant: bool = False,
                       limit: int = 50, now: datetime | None = None) -> list[OpportunityRead]:
    query = select(Opportunity).where(Opportunity.user_id == user.id, Opportunity.status == status)
    if category: query = query.where(Opportunity.opportunity_type == category.value)
    if starts_after: query = query.where(Opportunity.starts_at >= starts_after)
    rows = list(db.scalars(query.order_by(Opportunity.starts_at.asc()).limit(min(max(limit, 1), 100))))
    if not relevant: return [_read(db, user, row) for row in rows]
    trajectory = get_social_trajectory(db, user, now=now); budget = discretionary_social_budget_remaining(db, user)
    ranked = [rank_opportunity(db, user, row, trajectory, budget, now=now) for row in rows]
    return [_read(db, user, item.row, item) for item in sorted(ranked, key=lambda value: value.score, reverse=True) if item.score >= 20][:limit]


def get_opportunity(db: Session, user: UserProfile, opportunity_id: str) -> OpportunityRead:
    row = db.scalar(select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.user_id == user.id))
    if row is None: raise LookupError("Opportunity not found.")
    return _read(db, user, row)


def dismiss_opportunity(db: Session, user: UserProfile, opportunity_id: str) -> OpportunityRead:
    row = db.scalar(select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.user_id == user.id))
    if row is None: raise LookupError("Opportunity not found.")
    state = db.scalar(select(OpportunityUserState).where(OpportunityUserState.user_id == user.id, OpportunityUserState.opportunity_id == row.id))
    if state is None:
        state = OpportunityUserState(user_id=user.id, opportunity_id=row.id, version=1)
        db.add(state)
    state.status="DISMISSED"; state.dismissed_at=_now(); state.version = (state.version or 1) + 1; db.flush()
    append_event(db, user, event_type="opportunity.outcome_recorded", aggregate_type="opportunity", aggregate_id=row.id,
                 payload={"opportunity_id": row.id, "outcome": "REJECTED"}, outbox=True)
    return _read(db, user, row)


def create_opportunity_recommendation(db: Session, user: UserProfile, *, limit: int = 5, now: datetime | None = None):
    when = now or _now(); trajectory = get_social_trajectory(db, user, now=when); budget = discretionary_social_budget_remaining(db, user)
    rows = list(db.scalars(select(Opportunity).where(Opportunity.user_id == user.id, Opportunity.status == "ACTIVE",
                                                      Opportunity.starts_at >= when).order_by(Opportunity.starts_at).limit(100)))
    context = DiscoveryContext(window_start=when, window_end=when + timedelta(days=90))
    ranked: list[RankedOpportunity] = []
    for row in rows:
        if hard_filter(db, user, row, context, budget, now=when): continue
        candidate = rank_opportunity(db, user, row, trajectory, budget, now=when)
        if candidate.score >= 20 and (candidate.feasibility.feasible or candidate.feasibility.requires_plan_proposal): ranked.append(candidate)
    ranked.sort(key=lambda item: item.score, reverse=True); ranked = ranked[: min(max(limit, 2), 5)]
    if not ranked: return None
    fingerprint = hashlib.sha256("|".join(f"{item.row.id}:{item.row.source_hash}" for item in ranked).encode()).hexdigest()[:32]
    recommendation = create_recommendation(db, user, RecommendationCreate(
        domain="social", kind="opportunity", title="Relevant opportunities", reason="Relevant, feasible options from your configured sources.",
        context_snapshot={"policy_version": SOCIAL_POLICY_VERSION, "trajectory_state": trajectory.state,
                          "budget_signal": {"status": budget.status, "amount_remaining": str(budget.amount_remaining) if budget.amount_remaining is not None else None,
                                            "currency": budget.currency, "window": budget.window},
                          "full_finance_data_used": False},
        idempotency_key=f"opportunities:{fingerprint}",
        options=[RecommendationOptionCreate(label=item.row.title, rank=index + 1, score=item.score,
                    payload_json={"opportunity_id": item.row.id, "score_factors": item.factors, "reasons": item.reasons,
                                  "feasibility": item.feasibility.model_dump(mode="json"), "prospective_thread_refs": item.prospective_refs,
                                  "open_thread_refs": item.thread_refs, "provider_trace_id": item.provider_trace_id},
                    reference_type="opportunity", reference_id=item.row.id) for index, item in enumerate(ranked)]
    ))
    top = ranked[0]
    requested = AttentionAction.mention_when_natural if top.score >= 55 else AttentionAction.show_passively if top.score >= 35 else AttentionAction.silent
    decision = AttentionManager().decide(AttentionCandidate(
        requested_action=requested, reason_code="relevant_opportunity", subject=top.row.title,
        priority=min(85, int(top.score)), urgency=0.35, evidence_quality=min(1, top.score / 75), confidence=min(1, top.score / 70),
        prospective_thread_id=top.prospective_refs[0] if top.prospective_refs else None,
        expires_at=top.row.ends_at or top.row.starts_at,
    ))
    if decision.action not in {AttentionAction.silent, AttentionAction.act_silently}:
        AttentionItemService().enqueue(db, user, decision, deduplication_key=f"opportunity:{top.row.id}:{top.row.source_hash[:12]}",
                                       payload={"opportunity_id": top.row.id, "recommendation_id": recommendation.id},
                                       metadata={"policy_version": SOCIAL_POLICY_VERSION})
        append_event(db, user, event_type="opportunity.recommendation_created", aggregate_type="recommendation",
                     aggregate_id=recommendation.id, payload={"recommendation_id": recommendation.id, "attention_action": decision.action.value}, outbox=True)
    return recommendation


def record_opportunity_outcome(db: Session, user: UserProfile, payload: OpportunityOutcomeCreate):
    option = db.scalar(select(RecommendationOption).where(RecommendationOption.id == payload.option_id,
                                                           RecommendationOption.recommendation_id == payload.recommendation_id,
                                                           RecommendationOption.user_id == user.id))
    if option is None or option.reference_type != "opportunity" or not option.reference_id: raise LookupError("Opportunity recommendation option not found.")
    mapping = {"VIEWED": "opened", "SELECTED": "accepted", "REJECTED": "rejected", "EXECUTED": "completed", "FEEDBACK": "modified"}
    result = record_outcome(db, user, RecommendationOutcomeCreate(
        domain="social", recommendation_type="opportunity", recommendation_summary=option.label, outcome=mapping[payload.outcome],
        source_entity_type="opportunity", source_entity_id=option.reference_id, recommendation_id=payload.recommendation_id,
        option_id=payload.option_id, feedback_text=payload.feedback_text, idempotency_key=payload.idempotency_key,
        metadata_json={"social_outcome": payload.outcome, "contextual_evidence_only": True},
    ))
    state = db.scalar(select(OpportunityUserState).where(OpportunityUserState.user_id == user.id, OpportunityUserState.opportunity_id == option.reference_id))
    if state is None:
        state = OpportunityUserState(user_id=user.id, opportunity_id=option.reference_id, version=1)
        db.add(state)
    when = payload.occurred_at or _now()
    if payload.outcome == "SELECTED": state.status="INTERESTED"; state.selected_at=when
    elif payload.outcome == "REJECTED": state.status="DISMISSED"; state.dismissed_at=when
    elif payload.outcome == "EXECUTED":
        state.status="ATTENDED"; state.attended_at=when
        opportunity = db.get(Opportunity, option.reference_id)
        log_social_activity(db, user, SocialActivityCreate(activity_type=OpportunityType(opportunity.opportunity_type), title=opportunity.title,
                            occurred_at=when, source="opportunity_outcome", source_ref=opportunity.id,
                            idempotency_key=f"opportunity-attended:{opportunity.id}:{result.id}", metadata={"recommendation_outcome_id": result.id}))
        for thread_id in option.payload_json.get("prospective_thread_refs", []):
            thread = db.scalar(select(ProspectiveThread).where(ProspectiveThread.id == thread_id, ProspectiveThread.user_id == user.id))
            if thread and thread.status in {"OPEN", "DORMANT"}:
                thread.status = "RESOLVED"; thread.resolved_at = when; thread.version += 1
    state.version = (state.version or 1) + 1
    append_event(db, user, event_type="opportunity.outcome_recorded", aggregate_type="opportunity", aggregate_id=option.reference_id,
                 payload={"opportunity_id": option.reference_id, "outcome": payload.outcome, "outcome_id": result.id}, outbox=True)
    return result


def social_action_candidates(*, free_evening: bool, trajectory: SocialTrajectoryRead, contact_refs: list[str], urgent_study_conflict: bool) -> list[SocialActionCandidate]:
    if not free_evening or urgent_study_conflict or not trajectory.enabled or trajectory.state != "BELOW_RANGE" or not contact_refs: return []
    return [SocialActionCandidate(action_type=SocialActionType.call_friend, subject="Call a friend",
                                  reason_codes=["free_evening", "explicit_contact_reference", "below_configured_target"],
                                  contact_ref=contact_refs[0])]


def configure_source(db: Session, user: UserProfile, source_id: str, payload: OpportunitySourceUpdate) -> OpportunitySourceRead:
    row = db.scalar(select(OpportunitySourceState).where(OpportunitySourceState.user_id == user.id, OpportunitySourceState.source_id == source_id))
    if row is None: row = OpportunitySourceState(user_id=user.id, source_id=source_id); db.add(row)
    for key, value in payload.model_dump(exclude={"categories"}).items(): setattr(row, key, value)
    row.categories_json=[item.value for item in payload.categories]; row.next_discovery_at=_now() if payload.enabled else None; row.version += 1; db.flush()
    append_event(db, user, event_type="opportunity.source_changed", aggregate_type="opportunity_source", aggregate_id=row.id,
                 payload={"source_id": source_id, "enabled": row.enabled}, outbox=True)
    return source_read(row, get_settings())


def source_read(row: OpportunitySourceState, settings: Settings) -> OpportunitySourceRead:
    configured = row.source_id != "ticketmaster" or bool(settings.ticketmaster_api_key)
    return OpportunitySourceRead(id=row.id, source_id=row.source_id, enabled=row.enabled, configured=configured, city=row.city,
        region=row.region, country_code=row.country_code, categories=list(row.categories_json or []), cadence_minutes=row.cadence_minutes,
        horizon_days=row.horizon_days, last_discovery_at=row.last_discovery_at, next_discovery_at=row.next_discovery_at,
        last_status=row.last_status, last_summary=row.last_summary_json or {}, last_error=row.last_error)


def list_sources(db: Session, user: UserProfile, settings: Settings | None = None) -> list[OpportunitySourceRead]:
    settings=settings or get_settings(); rows=list(db.scalars(select(OpportunitySourceState).where(OpportunitySourceState.user_id == user.id)))
    if not any(row.source_id == "ticketmaster" for row in rows):
        row=OpportunitySourceState(user_id=user.id, source_id="ticketmaster", enabled=False, city=settings.opportunity_default_city,
                                   country_code=settings.opportunity_default_country_code, cadence_minutes=settings.opportunity_source_cadence_minutes,
                                   horizon_days=settings.opportunity_discovery_horizon_days, last_status="NEVER")
        db.add(row); db.flush(); rows.append(row)
    return [source_read(row, settings) for row in rows]


def source_for(row: OpportunitySourceState, settings: Settings) -> OpportunitySource | None:
    if row.source_id == "ticketmaster" and settings.ticketmaster_api_key:
        return TicketmasterOpportunitySource(settings.ticketmaster_api_key, base_url=settings.ticketmaster_api_base_url,
                                              timeout_seconds=settings.opportunity_source_timeout_seconds)
    return None


def run_discovery(db: Session, user: UserProfile, sources: list[OpportunitySource], context: DiscoveryContext,
                  *, source_states: dict[str, OpportunitySourceState] | None = None, now: datetime | None = None) -> DiscoverySummary:
    summary=DiscoverySummary(); when=now or _now()
    for source in sources:
        state=(source_states or {}).get(source.source_id)
        try:
            raw_rows=source.discover(context); summary.fetched += len(raw_rows)
            for raw in raw_rows:
                item=source.normalize(raw); summary.normalized += 1
                row, action=upsert_opportunity(db, user, item)
                if action == "created": summary.created += 1
                elif action == "updated": summary.updated += 1
                else: summary.deduplicated += 1
            if state:
                state.last_status="SUCCESS"; state.last_error=None; state.last_discovery_at=when
                state.next_discovery_at=when + timedelta(minutes=state.cadence_minutes)
        except Exception as exc:
            logger.warning("source_fetch_failed", extra={"source_id": source.source_id, "error_type": type(exc).__name__})
            summary.failed_sources.append(source.source_id)
            if state:
                state.last_status="FAILED"; state.last_error=str(exc)[:1000]; state.last_discovery_at=when
                state.next_discovery_at=when + timedelta(minutes=state.cadence_minutes)
    ended = list(db.scalars(select(Opportunity).where(
        Opportunity.user_id == user.id, Opportunity.status == "ACTIVE",
        func.coalesce(Opportunity.ends_at, Opportunity.starts_at) < when,
    )))
    for row in ended:
        row.status = "ENDED"; row.version += 1
        append_event(db, user, event_type="opportunity.ended", aggregate_type="opportunity", aggregate_id=row.id,
                     payload={"opportunity_id": row.id}, outbox=True)
    for state in (source_states or {}).values(): state.last_summary_json=summary.model_dump()
    return summary


class OpportunityDiscoveryWorker:
    def __init__(self, settings: Settings | None = None): self.settings=settings or get_settings()

    def run_due(self, db: Session, *, limit: int = 25, now: datetime | None = None) -> int:
        if not self.settings.opportunity_discovery_enabled: return 0
        when=now or _now(); states=list(db.scalars(select(OpportunitySourceState).where(
            OpportunitySourceState.enabled.is_(True), or_(OpportunitySourceState.next_discovery_at.is_(None), OpportunitySourceState.next_discovery_at <= when)
        ).order_by(OpportunitySourceState.next_discovery_at.asc()).limit(limit)))
        processed=0
        for state in states:
            source=source_for(state, self.settings)
            if source is None:
                state.last_status="UNCONFIGURED"; state.last_error="Provider credentials are not configured."
                state.next_discovery_at=when + timedelta(minutes=state.cadence_minutes); continue
            user=db.get(UserProfile, state.user_id)
            context=DiscoveryContext(city=state.city, region=state.region, country_code=state.country_code,
                window_start=when, window_end=when+timedelta(days=state.horizon_days),
                categories=tuple(OpportunityType(item) for item in state.categories_json or []), max_results=self.settings.opportunity_max_results_per_source)
            run_discovery(db, user, [source], context, source_states={source.source_id: state}, now=when); processed += 1
        return processed
