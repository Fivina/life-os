from __future__ import annotations

from app.database.models import Event
from app.decision.schemas import CognitiveEvent, EntityReference


def cognitive_event_from_domain_event(
    event: Event,
    *,
    domains: tuple[str, ...] = (),
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> CognitiveEvent:
    """Create a reference-oriented cognitive envelope without copying canonical state."""
    return CognitiveEvent(
        event_id=f"domain-event:{event.id}",
        event_type=event.event_type,
        source="domain_event",
        occurred_at=event.occurred_at,
        domains=domains,
        entity_refs=(EntityReference(entity_type=event.aggregate_type, entity_id=event.aggregate_id, role="aggregate"),),
        source_event_id=event.id,
        world_revision=event.world_revision,
        correlation_id=correlation_id,
        causation_id=causation_id,
        metadata={"payload_keys": sorted(event.payload.keys())},
    )
