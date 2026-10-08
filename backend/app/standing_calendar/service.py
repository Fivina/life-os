from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.models import Commitment, FixtureBinding, StandingCalendarRule, UserProfile
from app.events.service import append_event
from app.integrations.credentials import IntegrationSecretStore
from app.standing_calendar.providers import FixtureProvider, FixtureProviderError, configured_provider
from app.standing_calendar.schemas import FixtureOverrideRequest, FixtureSyncSummary, NormalizedFixture


logger = logging.getLogger("life_os.standing_calendar")
SYNC_DAYS = 1
RETRY_HOURS = 6


def utcnow() -> datetime: return datetime.now(UTC)


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None: return left is right
    normalized_left = left.replace(tzinfo=UTC) if left.tzinfo is None else left.astimezone(UTC)
    normalized_right = right.replace(tzinfo=UTC) if right.tzinfo is None else right.astimezone(UTC)
    return normalized_left == normalized_right


def ensure_besiktas_rule(db: Session, user: UserProfile, *, settings: Settings | None = None, now: datetime | None = None) -> StandingCalendarRule:
    settings = settings or get_settings(); now = now or utcnow(); identity = f"team:{settings.api_football_besiktas_team_id}"
    existing = db.scalar(select(StandingCalendarRule).where(
        StandingCalendarRule.user_id == user.id, StandingCalendarRule.rule_type == "SPORTS_FIXTURE",
        StandingCalendarRule.source_provider == settings.fixture_provider, StandingCalendarRule.source_identity == identity,
    ))
    if existing is not None:
        changed = False
        source_config = dict(existing.source_config_json or {})
        if source_config.pop("lookahead_days", None) is not None:
            changed = True
        expected_source_config = {
            "team_id": settings.api_football_besiktas_team_id,
            "team_name": "Beşiktaş",
            "next": 1,
        }
        for key, value in expected_source_config.items():
            if source_config.get(key) != value:
                source_config[key] = value
                changed = True
        metadata = dict(existing.metadata_json or {})
        if metadata.get("fixture_sync_mode") != "NEXT_FIXTURE":
            metadata["fixture_sync_mode"] = "NEXT_FIXTURE"
            existing.metadata_json = metadata
            existing.next_sync_at = now
            changed = True
        if existing.sync_interval_days != SYNC_DAYS:
            existing.sync_interval_days = SYNC_DAYS
            existing.next_sync_at = now
            changed = True
        if changed:
            existing.source_config_json = source_config
            existing.version += 1
        return existing
    row = StandingCalendarRule(
        user_id=user.id, name="Beşiktaş fixtures", rule_type="SPORTS_FIXTURE", enabled=True,
        protected=True, auto_create=True, source_provider=settings.fixture_provider, source_identity=identity,
        source_config_json={"team_id": settings.api_football_besiktas_team_id, "team_name": "Beşiktaş", "next": 1},
        reconciliation_policy_json={"source_time_authoritative": True, "default_duration_minutes": 120},
        sync_interval_days=SYNC_DAYS, next_sync_at=now, last_sync_status="NEVER",
        last_sync_summary_json={}, metadata_json={"team_identity_verified_at": "2026-09-26", "fixture_sync_mode": "NEXT_FIXTURE"},
    )
    db.add(row); db.flush()
    append_event(db, user, event_type="standing_rule.created", aggregate_type="standing_calendar_rule", aggregate_id=row.id,
                 payload={"rule_id": row.id, "rule_type": row.rule_type}, outbox=True)
    return row


def list_rules(db: Session, user: UserProfile) -> list[StandingCalendarRule]:
    ensure_besiktas_rule(db, user)
    return list(db.scalars(select(StandingCalendarRule).where(StandingCalendarRule.user_id == user.id).order_by(StandingCalendarRule.created_at)).all())


def get_rule(db: Session, user: UserProfile, rule_id: str) -> StandingCalendarRule:
    row = db.scalar(select(StandingCalendarRule).where(StandingCalendarRule.id == rule_id, StandingCalendarRule.user_id == user.id))
    if row is None: raise HTTPException(status_code=404, detail="Standing calendar rule not found.")
    return row


def set_enabled(db: Session, user: UserProfile, rule_id: str, *, enabled: bool, expected_version: int) -> StandingCalendarRule:
    row = get_rule(db, user, rule_id)
    if row.version != expected_version: raise HTTPException(status_code=409, detail=f"Standing rule version conflict. Current version is {row.version}.")
    if row.enabled == enabled: return row
    row.enabled = enabled; row.version += 1
    if enabled and row.next_sync_at is None: row.next_sync_at = utcnow()
    append_event(db, user, event_type="standing_rule.enabled" if enabled else "standing_rule.disabled",
                 aggregate_type="standing_calendar_rule", aggregate_id=row.id, payload={"rule_id": row.id, "enabled": enabled}, outbox=True)
    return row


def _commitment_values(fixture: NormalizedFixture, binding: FixtureBinding | None, rule: StandingCalendarRule) -> dict:
    protected = rule.protected and not (binding and binding.protection_overridden)
    active = fixture.status in {"SCHEDULED", "CONFIRMED"}
    duration = int(rule.reconciliation_policy_json.get("default_duration_minutes", 120))
    return {
        "title": f"{fixture.home_team} vs {fixture.away_team}",
        "description": f"{fixture.competition or 'Football'} fixture imported from {fixture.provider}.",
        "level": "hard" if protected else "optional", "commitment_type": "hard" if protected else "semi_fixed",
        "starts_at": fixture.kickoff_at, "ends_at": fixture.kickoff_at + timedelta(minutes=duration) if fixture.kickoff_at else None,
        "timezone": "UTC", "all_day": False, "location": fixture.venue, "recurrence": {},
        "status": "active" if active else fixture.status.lower(), "source": "standing_calendar_fixture",
        "notes": f"Source identity: {fixture.provider}:{fixture.source_fixture_id}",
    }


def _new_commitment(db: Session, user: UserProfile, fixture: NormalizedFixture, rule: StandingCalendarRule) -> Commitment:
    row = Commitment(user_id=user.id, **_commitment_values(fixture, None, rule)); db.add(row); db.flush(); return row


def _emit_fixture_event(db: Session, user: UserProfile, kind: str, binding: FixtureBinding, commitment: Commitment | None) -> None:
    append_event(db, user, event_type=f"fixture.{kind}", aggregate_type="commitment", aggregate_id=commitment.id if commitment else binding.id,
                 payload={"fixture_binding_id": binding.id, "commitment_id": commitment.id if commitment else None,
                          "source_fixture_id": binding.source_fixture_id, "fixture_status": binding.fixture_status}, outbox=True)


def reconcile_fixture(db: Session, user: UserProfile, rule: StandingCalendarRule, fixture: NormalizedFixture, *, now: datetime) -> str:
    binding = db.scalar(select(FixtureBinding).where(
        FixtureBinding.user_id == user.id, FixtureBinding.source_provider == fixture.provider,
        FixtureBinding.source_fixture_id == fixture.source_fixture_id,
    ).with_for_update())
    if binding is None:
        commitment = _new_commitment(db, user, fixture, rule) if rule.auto_create else None
        binding = FixtureBinding(
            user_id=user.id, standing_rule_id=rule.id, commitment_id=commitment.id if commitment else None,
            source_provider=fixture.provider, source_fixture_id=fixture.source_fixture_id, fixture_status=fixture.status,
            kickoff_at=fixture.kickoff_at, raw_hash=fixture.raw_hash, normalized_json=fixture.model_dump(mode="json"),
            suppressed=False, protection_overridden=False, source_updated_at=fixture.source_updated_at, last_seen_at=now,
            metadata_json={},
        )
        db.add(binding); db.flush(); _emit_fixture_event(db, user, "created", binding, commitment)
        return "created"
    binding.last_seen_at = now
    if binding.suppressed:
        binding.normalized_json = fixture.model_dump(mode="json"); binding.raw_hash = fixture.raw_hash
        binding.fixture_status = fixture.status; binding.kickoff_at = fixture.kickoff_at; binding.source_updated_at = fixture.source_updated_at
        return "suppressed"
    commitment = db.get(Commitment, binding.commitment_id) if binding.commitment_id else None
    changed = binding.raw_hash != fixture.raw_hash or binding.fixture_status != fixture.status or not _same_instant(binding.kickoff_at, fixture.kickoff_at)
    if not changed and commitment is not None:
        # Backfill newly normalized artwork even when the raw provider payload is
        # unchanged; this does not change the protected calendar commitment.
        normalized = fixture.model_dump(mode="json")
        if any((binding.normalized_json or {}).get(key) != normalized[key]
               for key in ("home_team_logo_url", "away_team_logo_url")):
            binding.normalized_json = normalized
            binding.version += 1
        return "noop"
    if commitment is None and rule.auto_create:
        commitment = _new_commitment(db, user, fixture, rule); binding.commitment_id = commitment.id
    elif commitment is not None:
        for key, value in _commitment_values(fixture, binding, rule).items(): setattr(commitment, key, value)
        commitment.version += 1
    binding.fixture_status = fixture.status; binding.kickoff_at = fixture.kickoff_at; binding.raw_hash = fixture.raw_hash
    binding.normalized_json = fixture.model_dump(mode="json"); binding.source_updated_at = fixture.source_updated_at; binding.version += 1
    kind = "cancelled" if fixture.status == "CANCELLED" else "updated"
    _emit_fixture_event(db, user, kind, binding, commitment)
    return kind


def sync_rule(db: Session, user: UserProfile, rule: StandingCalendarRule, *, provider: FixtureProvider | None = None,
              settings: Settings | None = None, now: datetime | None = None) -> FixtureSyncSummary:
    settings = settings or get_settings(); now = (now or utcnow()).astimezone(UTC)
    if not rule.enabled:
        return FixtureSyncSummary(rule_id=rule.id, status="SKIPPED")
    try:
        # A provider/Vault/database failure must not partially update Calendar or
        # leave the surrounding manual/worker transaction unusable.
        with db.begin_nested():
            if provider is None:
                secret = IntegrationSecretStore(settings).fixture_runtime_key(db, user, settings.fixture_credential_scope)
                runtime_settings = settings.model_copy(update={"api_football_api_key": secret})
                provider = configured_provider(runtime_settings)
            fixtures = provider.fetch(team_id=str(rule.source_config_json["team_id"]))
            counts = {"created": 0, "updated": 0, "cancelled": 0, "noop": 0, "suppressed": 0}
            for fixture in fixtures: counts[reconcile_fixture(db, user, rule, fixture, now=now)] += 1
            summary = FixtureSyncSummary(rule_id=rule.id, status="SUCCESS", fetched=len(fixtures), **counts)
            metadata = dict(rule.metadata_json or {})
            metadata["fixture_sync_mode"] = "NEXT_FIXTURE"
            metadata["current_next_fixture_id"] = fixtures[0].source_fixture_id if fixtures else None
            rule.metadata_json = metadata
            rule.last_sync_at = now; rule.next_sync_at = now + timedelta(days=SYNC_DAYS); rule.last_sync_status = "SUCCESS"
            rule.last_sync_summary_json = summary.model_dump(mode="json"); rule.last_error = None; rule.version += 1
            append_event(db, user, event_type="standing_rule.sync_completed", aggregate_type="standing_calendar_rule", aggregate_id=rule.id,
                         payload=summary.model_dump(mode="json"), outbox=True)
        logger.info("fixture_sync_completed", extra={"sync_summary": summary.model_dump(mode="json")})
        return summary
    except Exception as exc:
        reason = str(exc) if isinstance(exc, FixtureProviderError) else "Fixture synchronization is unavailable."
        summary = FixtureSyncSummary(rule_id=rule.id, status="FAILED", error=reason)
        transient = isinstance(exc, FixtureProviderError) and exc.transient
        retry_after = timedelta(hours=RETRY_HOURS) if transient else timedelta(days=SYNC_DAYS)
        rule.last_sync_at = now; rule.next_sync_at = now + retry_after; rule.last_sync_status = "FAILED"
        rule.last_sync_summary_json = summary.model_dump(mode="json"); rule.last_error = reason; rule.version += 1
        append_event(db, user, event_type="standing_rule.sync_failed", aggregate_type="standing_calendar_rule", aggregate_id=rule.id,
                     payload={"rule_id": rule.id, "reason_code": "PROVIDER_UNAVAILABLE"}, outbox=True)
        logger.warning("fixture_sync_failed", extra={"rule_id": rule.id, "reason": reason})
        return summary


def list_bindings(db: Session, user: UserProfile, rule_id: str) -> list[FixtureBinding]:
    get_rule(db, user, rule_id)
    return list(db.scalars(select(FixtureBinding).where(FixtureBinding.user_id == user.id, FixtureBinding.standing_rule_id == rule_id).order_by(FixtureBinding.kickoff_at)).all())


def override_fixture(db: Session, user: UserProfile, binding_id: str, payload: FixtureOverrideRequest) -> FixtureBinding:
    binding = db.scalar(select(FixtureBinding).where(FixtureBinding.id == binding_id, FixtureBinding.user_id == user.id))
    if binding is None: raise HTTPException(status_code=404, detail="Fixture binding not found.")
    commitment = db.get(Commitment, binding.commitment_id) if binding.commitment_id else None
    if payload.protected is not None:
        binding.protection_overridden = not payload.protected
        if commitment: commitment.level = "hard" if payload.protected else "optional"; commitment.commitment_type = "hard" if payload.protected else "semi_fixed"; commitment.version += 1
    if payload.suppressed is not None:
        binding.suppressed = payload.suppressed
        if commitment and payload.suppressed: commitment.status = "cancelled"; commitment.version += 1
    binding.version += 1
    append_event(db, user, event_type="fixture.override_updated", aggregate_type="fixture_binding", aggregate_id=binding.id,
                 payload={"fixture_binding_id": binding.id, "protected": payload.protected, "suppressed": payload.suppressed}, outbox=True)
    return binding


class FixtureSyncWorker:
    def run_due(self, db: Session, *, now: datetime | None = None, provider: FixtureProvider | None = None, limit: int = 25) -> int:
        now = now or utcnow(); users = list(db.scalars(select(UserProfile)).all())
        for user in users: ensure_besiktas_rule(db, user, now=now)
        due = list(db.scalars(select(StandingCalendarRule).where(
            StandingCalendarRule.enabled.is_(True), StandingCalendarRule.next_sync_at <= now
        ).order_by(StandingCalendarRule.next_sync_at).limit(limit).with_for_update(skip_locked=True)).all())
        for rule in due:
            user = db.get(UserProfile, rule.user_id)
            if user: sync_rule(db, user, rule, provider=provider, now=now)
        return len(due)
