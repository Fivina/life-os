from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models import ProspectiveThread
from app.threads.schemas import (
    DateApproachingTriggerConditions,
    ExternalObservationTriggerConditions,
    GoalStateChangedTriggerConditions,
    LocationRelevantTriggerConditions,
    ProspectiveEligibility,
    ProspectiveEvaluationContext,
    ProspectiveThreadStatus,
    ProspectiveTriggerType,
    validate_trigger_conditions,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ProspectiveThreadEligibilityService:
    """Pure deterministic trigger evaluation; external observations must be supplied explicitly."""

    policy_version = "prospective-eligibility-v1"

    def evaluate(
        self,
        thread: ProspectiveThread,
        context: ProspectiveEvaluationContext,
    ) -> ProspectiveEligibility:
        now = _aware(context.now)
        earliest = _aware(thread.earliest_relevance)
        latest = _aware(thread.latest_relevance)
        if thread.status != ProspectiveThreadStatus.open.value:
            return self._result(thread, now, False, "lifecycle_not_open")
        if latest is not None and now > latest:
            return self._result(thread, now, False, "relevance_window_expired", expired=True)
        if earliest is not None and now < earliest:
            return self._result(thread, now, False, "before_earliest_relevance")

        trigger_type = ProspectiveTriggerType(thread.trigger_type)
        conditions = validate_trigger_conditions(trigger_type, thread.trigger_conditions_json)
        if trigger_type == ProspectiveTriggerType.manual:
            return self._result(thread, now, context.manual, "manual_triggered" if context.manual else "manual_waiting")
        if trigger_type == ProspectiveTriggerType.date_approaching:
            typed = DateApproachingTriggerConditions.model_validate(conditions)
            eligible_at = _aware(typed.target_at) - timedelta(minutes=typed.lead_minutes) if typed.target_at else earliest
            eligible = eligible_at is None or now >= eligible_at
            return self._result(thread, now, eligible, "date_window_open" if eligible else "date_not_approaching")
        if trigger_type == ProspectiveTriggerType.goal_state_changed:
            typed = GoalStateChangedTriggerConditions.model_validate(conditions)
            eligible = context.goal_states.get(typed.goal_ref) == typed.target_state
            return self._result(thread, now, eligible, "goal_state_matched" if eligible else "goal_state_waiting")
        if trigger_type == ProspectiveTriggerType.location_relevant:
            typed = LocationRelevantTriggerConditions.model_validate(conditions)
            eligible = bool(context.location and context.location.upper() == typed.location.upper())
            return self._result(thread, now, eligible, "location_matched" if eligible else "location_waiting")

        typed = ExternalObservationTriggerConditions.model_validate(conditions)
        if typed.observation_key not in context.trigger_observations:
            return self._result(thread, now, False, "external_observation_missing")
        observed = context.trigger_observations[typed.observation_key]
        eligible = bool(observed) if typed.expected_value is None else observed == typed.expected_value
        return self._result(
            thread,
            now,
            eligible,
            "external_observation_matched" if eligible else "external_observation_waiting",
            observation_ref=typed.observation_key,
        )

    @staticmethod
    def _result(
        thread: ProspectiveThread,
        now: datetime,
        eligible: bool,
        reason_code: str,
        *,
        expired: bool = False,
        observation_ref: str | None = None,
    ) -> ProspectiveEligibility:
        return ProspectiveEligibility(
            thread_id=thread.id,
            eligible=eligible,
            reason_code=reason_code,
            evaluated_at=now,
            expired=expired,
            observation_ref=observation_ref,
        )
