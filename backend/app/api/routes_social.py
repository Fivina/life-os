from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import OpportunitySourceState, SocialActivity, UserProfile
from app.database.session import get_db
from app.social.schemas import (
    DiscoveryContext, DiscoverySummary, OpportunityOutcomeCreate, OpportunityRead, OpportunitySourceRead,
    OpportunitySourceUpdate, OpportunityType, SocialActivityCreate, SocialActivityRead,
    SocialTrajectoryRead, SocialTrajectoryUpdate,
)
from app.social.service import (
    configure_source, create_opportunity_recommendation, dismiss_opportunity, get_opportunity,
    get_social_trajectory, list_opportunities, list_sources, log_social_activity, record_opportunity_outcome,
    run_discovery, source_for, update_social_trajectory,
)


router = APIRouter(tags=["social"])


@router.get("/social/trajectory", response_model=SocialTrajectoryRead)
def trajectory(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = get_social_trajectory(db, user)
    db.commit()
    return result


@router.put("/social/trajectory", response_model=SocialTrajectoryRead)
def trajectory_update(payload: SocialTrajectoryUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = update_social_trajectory(db, user, payload)
    db.commit()
    return result


@router.get("/social/activities", response_model=list[SocialActivityRead])
def activities(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return list(db.scalars(select(SocialActivity).where(SocialActivity.user_id == user.id).order_by(SocialActivity.occurred_at.desc()).limit(limit)))


@router.post("/social/activities", response_model=SocialActivityRead, status_code=201)
def activity_create(payload: SocialActivityCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = log_social_activity(db, user, payload)
    db.commit()
    return result


@router.get("/opportunities", response_model=list[OpportunityRead])
def opportunities(category: OpportunityType | None = None, starts_after: datetime | None = None, status: str = "ACTIVE",
                  relevant: bool = False, limit: int = Query(default=50, ge=1, le=100),
                  db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return list_opportunities(db, user, category=category, starts_after=starts_after, status=status, relevant=relevant, limit=limit)


@router.post("/opportunities/recommendations")
def recommend(limit: int = Query(default=5, ge=2, le=5), db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = create_opportunity_recommendation(db, user, limit=limit)
    db.commit()
    return result


@router.post("/opportunities/recommendations/outcomes")
def outcome(payload: OpportunityOutcomeCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    try:
        result = record_opportunity_outcome(db, user, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityRead)
def opportunity(opportunity_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    try:
        return get_opportunity(db, user, opportunity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/opportunities/{opportunity_id}/dismiss", response_model=OpportunityRead)
def opportunity_dismiss(opportunity_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    try:
        result = dismiss_opportunity(db, user, opportunity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/opportunity-sources", response_model=list[OpportunitySourceRead])
def sources(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = list_sources(db, user)
    db.commit()
    return result


@router.put("/opportunity-sources/{source_id}", response_model=OpportunitySourceRead)
def source_update(source_id: str, payload: OpportunitySourceUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    if source_id != "ticketmaster":
        raise HTTPException(status_code=404, detail="Unknown opportunity source.")
    result = configure_source(db, user, source_id, payload)
    db.commit()
    return result


@router.post("/opportunity-sources/{source_id}/discover", response_model=DiscoverySummary)
def source_discover(source_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    state = db.scalar(select(OpportunitySourceState).where(OpportunitySourceState.user_id == user.id, OpportunitySourceState.source_id == source_id))
    if state is None:
        raise HTTPException(status_code=404, detail="Configure the source first.")
    source = source_for(state, settings)
    if source is None:
        raise HTTPException(status_code=409, detail="This source is not configured with valid credentials.")
    now = datetime.now().astimezone()
    context = DiscoveryContext(
        city=state.city, region=state.region, country_code=state.country_code, window_start=now,
        window_end=now + timedelta(days=state.horizon_days),
        categories=tuple(OpportunityType(item) for item in state.categories_json or []),
        max_results=settings.opportunity_max_results_per_source,
    )
    result = run_discovery(db, user, [source], context, source_states={source_id: state}, now=now)
    db.commit()
    return result
