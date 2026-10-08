from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.api.deps import get_or_create_user
from app.database.models import (
    AttentionItem, Commitment, FinanceBudget, FinanceCategory, Goal, OpenThread, Opportunity, OpportunityExternalId,
    OpportunityUserState, PlanBlock, ProspectiveThread, RecommendationOutcome, SocialActivity, Trajectory, WorldRevision,
)
from app.domains.finance.contracts import discretionary_social_budget_remaining
from app.social.providers import FakeOpportunitySource
from app.social.schemas import (
    DiscoveryContext, NormalizedOpportunity, OpportunityOutcomeCreate, OpportunityType, SocialActivityCreate,
    SocialTrajectoryUpdate,
)
from app.social.service import (
    create_opportunity_recommendation, get_social_trajectory, hard_filter, rank_opportunity,
    record_opportunity_outcome, run_discovery, social_action_candidates, update_social_trajectory,
)
from app.realtime.service import RealtimeStateService
from tests.conftest import AUTH_HEADERS


NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def normalized(external_id: str, title: str, *, starts: datetime | None = None, city: str = "Berlin", venue: str = "Arena",
               kind: OpportunityType = OpportunityType.concert, provider: str = "fake", cost: Decimal | None = None):
    return {
        "provider": provider, "external_id": external_id, "opportunity_type": kind.value, "title": title,
        "starts_at": starts or NOW + timedelta(days=7), "ends_at": (starts or NOW + timedelta(days=7)) + timedelta(hours=2),
        "city": city, "country_code": "DE", "venue": venue, "cost_min": cost,
        "currency": "EUR" if cost is not None else None, "tags": ["music"] if kind == OpportunityType.concert else [],
    }


def context():
    return DiscoveryContext(city="Berlin", country_code="DE", window_start=NOW, window_end=NOW + timedelta(days=30))


def test_social_goal_reuses_goal_trajectory_and_period_math_is_neutral(db_session):
    user = get_or_create_user(db_session)
    update_social_trajectory(db_session, user, SocialTrajectoryUpdate(enabled=True, target_min=2, target_max=2),)
    state = get_social_trajectory(db_session, user, now=NOW)
    assert state.completed_count == 0 and state.remaining_to_min == 2 and state.state == "BELOW_RANGE"
    from app.social.service import log_social_activity
    log_social_activity(db_session, user, SocialActivityCreate(title="Dinner", occurred_at=NOW - timedelta(days=1), idempotency_key="one"))
    assert get_social_trajectory(db_session, user, now=NOW).remaining_to_min == 1
    log_social_activity(db_session, user, SocialActivityCreate(title="Museum", occurred_at=NOW, idempotency_key="two"))
    assert get_social_trajectory(db_session, user, now=NOW).state == "IN_RANGE"
    log_social_activity(db_session, user, SocialActivityCreate(title="Football", occurred_at=NOW, idempotency_key="three"))
    assert get_social_trajectory(db_session, user, now=NOW).state == "ABOVE_RANGE"
    assert db_session.query(Goal).filter_by(domain="social").count() == db_session.query(Trajectory).filter_by(source_domain="social").count() == 1
    state = update_social_trajectory(db_session, user, SocialTrajectoryUpdate(enabled=False, target_min=2, target_max=3))
    assert state.state == "DISABLED" and state.remaining_to_min == 0


def test_discovery_normalizes_deduplicates_and_isolates_source_failure(db_session):
    user = get_or_create_user(db_session)
    first = FakeOpportunitySource([normalized("a-1", "Aurora Live")])
    second = FakeOpportunitySource([{**normalized("b-9", "Aurora Live"), "provider": "fake"}])
    failing = FakeOpportunitySource(fail=True); failing.source_id = "failed"
    summary = run_discovery(db_session, user, [first, second, failing], context(), now=NOW)
    assert summary.fetched == 2 and summary.created == 1 and summary.deduplicated == 1
    assert summary.failed_sources == ["failed"]
    assert db_session.query(Opportunity).count() == 1 and db_session.query(OpportunityExternalId).count() == 2


def test_same_artist_different_dates_are_not_merged(db_session):
    user = get_or_create_user(db_session)
    rows = [normalized("one", "Aurora Live", starts=NOW + timedelta(days=4)), normalized("two", "Aurora Live", starts=NOW + timedelta(days=5))]
    run_discovery(db_session, user, [FakeOpportunitySource(rows)], context(), now=NOW)
    assert db_session.query(Opportunity).count() == 2


def test_filters_run_before_ranking_and_unknown_cost_stays_unknown(db_session):
    user = get_or_create_user(db_session)
    run_discovery(db_session, user, [FakeOpportunitySource([normalized("past", "Past", starts=NOW - timedelta(days=2)), normalized("far", "Far", city="Paris")])], context(), now=NOW)
    budget = discretionary_social_budget_remaining(db_session, user)
    rows = db_session.query(Opportunity).all()
    assert budget.status == "UNKNOWN" and budget.amount_remaining is None
    assert "event_ended" in hard_filter(db_session, user, rows[0], context(), budget, now=NOW)
    assert "outside_configured_city" in hard_filter(db_session, user, rows[1], context(), budget, now=NOW)
    assert rows[1].cost_min is None


def test_prospective_match_stronger_than_open_thread_and_irrelevant_stays_low(db_session):
    user = get_or_create_user(db_session)
    db_session.add_all([
        ProspectiveThread(user_id=user.id, subject="See Aurora", intent="Aurora concert", entities_json=[], domain="social",
                          trigger_type="EVENT_AVAILABLE", trigger_conditions_json={}, check_policy="ON_DISCOVERY",
                          attention_policy="MENTION_WHEN_NATURAL", status="DORMANT", source="manual", confidence=1),
        OpenThread(user_id=user.id, subject="Try pottery", intent="Pottery workshop", entities_json=[], domain="social",
                   category="interest", status="OPEN", source="manual", confidence=.8),
    ]); db_session.flush()
    rows = [normalized("aurora", "Aurora Concert"), normalized("pottery", "Pottery Workshop", kind=OpportunityType.workshop), normalized("random", "Tax Seminar", kind=OpportunityType.workshop)]
    run_discovery(db_session, user, [FakeOpportunitySource(rows)], context(), now=NOW)
    trajectory = get_social_trajectory(db_session, user, now=NOW); budget = discretionary_social_budget_remaining(db_session, user)
    scores = {row.title: rank_opportunity(db_session, user, row, trajectory, budget, now=NOW).score for row in db_session.query(Opportunity).all()}
    assert scores["Aurora Concert"] > scores["Pottery Workshop"] > scores["Tax Seminar"]


def test_finance_contract_exposes_only_typed_budget_signal(db_session):
    user = get_or_create_user(db_session)
    category = FinanceCategory(user_id=user.id, name="Social", kind="expense", active=True)
    db_session.add(category); db_session.flush()
    db_session.add(FinanceBudget(user_id=user.id, category_id=category.id, name="Social budget", amount=Decimal("40"), currency="EUR",
                                 month_start=NOW.date().replace(day=1), protected=True, active=True)); db_session.flush()
    signal = discretionary_social_budget_remaining(db_session, user)
    assert signal.status == "CONSTRAINED" and signal.amount_remaining == Decimal("40")
    assert not hasattr(signal, "transactions") and not hasattr(signal, "merchant_history")


def test_clean_and_protected_planner_checks_never_create_planblocks(db_session):
    user = get_or_create_user(db_session)
    run_discovery(db_session, user, [FakeOpportunitySource([normalized("clean", "Clean Slot")])], context(), now=NOW)
    row = db_session.query(Opportunity).one(); trajectory = get_social_trajectory(db_session, user, now=NOW)
    clean = rank_opportunity(db_session, user, row, trajectory, discretionary_social_budget_remaining(db_session, user), now=NOW)
    assert clean.feasibility.feasible and clean.feasibility.current_plan_mutated is False
    db_session.add(Commitment(user_id=user.id, title="Protected", level="hard", commitment_type="hard", status="active",
                              starts_at=row.starts_at, ends_at=row.ends_at)); db_session.flush()
    blocked = rank_opportunity(db_session, user, row, trajectory, discretionary_social_budget_remaining(db_session, user), now=NOW)
    assert not blocked.feasibility.feasible and blocked.feasibility.status == "PROTECTED_CONFLICT"
    assert db_session.query(PlanBlock).count() == 0


def test_recommendation_attention_dedup_and_selected_is_not_attended(db_session):
    user = get_or_create_user(db_session)
    db_session.add(ProspectiveThread(user_id=user.id, subject="See Aurora", intent="Aurora concert", entities_json=[], domain="social",
        trigger_type="EVENT_AVAILABLE", trigger_conditions_json={}, check_policy="ON_DISCOVERY", attention_policy="MENTION_WHEN_NATURAL",
        status="DORMANT", source="manual", confidence=1)); db_session.flush()
    run_discovery(db_session, user, [FakeOpportunitySource([normalized("aurora", "Aurora Concert"), normalized("aurora-2", "Aurora Aftershow", starts=NOW+timedelta(days=8))])], context(), now=NOW)
    first = create_opportunity_recommendation(db_session, user, now=NOW)
    second = create_opportunity_recommendation(db_session, user, now=NOW)
    assert first.id == second.id and db_session.query(AttentionItem).count() == 1
    option = first.options[0]
    selected = record_opportunity_outcome(db_session, user, OpportunityOutcomeCreate(recommendation_id=first.id, option_id=option.id, outcome="SELECTED", idempotency_key="sel"))
    assert selected.outcome == "accepted" and db_session.query(SocialActivity).count() == 0
    attended = record_opportunity_outcome(db_session, user, OpportunityOutcomeCreate(recommendation_id=first.id, option_id=option.id, outcome="EXECUTED", occurred_at=NOW, idempotency_key="att"))
    assert attended.outcome == "completed" and db_session.query(SocialActivity).count() == 1
    assert db_session.query(RecommendationOutcome).count() == 2


def test_non_event_action_is_structured_and_never_executable(db_session):
    user = get_or_create_user(db_session); trajectory = get_social_trajectory(db_session, user, now=NOW)
    candidates = social_action_candidates(free_evening=True, trajectory=trajectory, contact_refs=["contact-explicit"], urgent_study_conflict=False)
    assert candidates[0].action_type.value == "CALL_FRIEND" and candidates[0].executable is False


def test_opportunity_domain_has_no_booking_payment_or_contact_execution():
    root = Path(__file__).parents[1] / "app" / "social"
    banned_imports = {"app.skills.runtime", "app.assistant.tools", "stripe", "twilio"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert not imports.intersection(banned_imports)
        source = path.read_text(encoding="utf-8").lower()
        for forbidden in ("buy_ticket(", "reserve_restaurant(", "send_message(", "make_payment("):
            assert forbidden not in source


def test_authenticated_api_and_realtime_invalidate_other_clients(client, db_session):
    user = get_or_create_user(db_session)
    run_discovery(db_session, user, [FakeOpportunitySource([normalized("api", "API Concert")])], context(), now=NOW)
    db_session.commit()
    opportunity = db_session.query(Opportunity).filter_by(title="API Concert").one()
    before = user.world_revision
    response = client.post(f"/api/v1/opportunities/{opportunity.id}/dismiss", headers=AUTH_HEADERS)
    assert response.status_code == 200 and response.json()["user_status"] == "DISMISSED"
    db_session.refresh(user)
    assert user.world_revision > before
    catchup = RealtimeStateService().changes_since(db_session, user, after_revision=before)
    assert any("opportunities" in event.invalidates for event in catchup.events)
    assert client.get("/api/v1/opportunities").status_code == 401
