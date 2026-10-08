from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RealtimeStateEventType(str, Enum):
    state_changed = "STATE_CHANGED"
    resync_required = "RESYNC_REQUIRED"
    heartbeat = "HEARTBEAT"


class RealtimeStateEvent(BaseModel):
    event_kind: RealtimeStateEventType = RealtimeStateEventType.state_changed
    event_id: str
    world_revision: int = Field(ge=0)
    occurred_at: datetime
    event_type: str
    domain: str
    entity_type: str
    entity_id: str
    operation: str
    invalidates: tuple[str, ...]
    patch: dict[str, Any] | None = None
    conversation_id: str | None = None
    workspace_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None


class RealtimeCatchup(BaseModel):
    after_revision: int = Field(ge=0)
    current_revision: int = Field(ge=0)
    events: list[RealtimeStateEvent]
    resync_required: bool = False
    reason_code: str | None = None
