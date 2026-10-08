from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.standing_calendar import service
from app.standing_calendar.schemas import FixtureBindingRead, FixtureOverrideRequest, FixtureSyncSummary, RuleEnabledUpdate, StandingRuleRead


router = APIRouter(prefix="/standing-calendar-rules", tags=["standing-calendar"])


@router.get("", response_model=list[StandingRuleRead])
def list_all(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    rows = service.list_rules(db, user); db.commit(); return rows


@router.get("/{rule_id}", response_model=StandingRuleRead)
def get(rule_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_rule(db, user, rule_id)


@router.patch("/{rule_id}/enabled", response_model=StandingRuleRead)
def enabled(rule_id: str, payload: RuleEnabledUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.set_enabled(db, user, rule_id, enabled=payload.enabled, expected_version=payload.expected_version); db.commit(); return row


@router.post("/{rule_id}/sync", response_model=FixtureSyncSummary)
def sync(rule_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.sync_rule(db, user, service.get_rule(db, user, rule_id)); db.commit(); return result


@router.get("/{rule_id}/fixtures", response_model=list[FixtureBindingRead])
def fixtures(rule_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_bindings(db, user, rule_id)


@router.patch("/fixtures/{binding_id}/override", response_model=FixtureBindingRead)
def override(binding_id: str, payload: FixtureOverrideRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.override_fixture(db, user, binding_id, payload); db.commit(); return row
