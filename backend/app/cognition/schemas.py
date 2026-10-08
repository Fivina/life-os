from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.attention.schemas import AttentionAction


class CognitiveCycleStatus(str, Enum):
    completed = "COMPLETED"
    degraded = "DEGRADED"
    disabled = "DISABLED"


class CognitiveCycleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cycle_id: str
    status: CognitiveCycleStatus
    situation_snapshot_ref: str | None = None
    activated_contributors: tuple[str, ...] = Field(default=(), max_length=4)
    truncated_contributors: tuple[str, ...] = ()
    question_refs: tuple[str, ...] = Field(default=(), max_length=12)
    trace_refs: tuple[str, ...] = Field(default=(), max_length=12)
    attention_action: AttentionAction
    attention_reason_code: str
    attention_item_ref: str | None = None
    eligible_prospective_thread_refs: tuple[str, ...] = Field(default=(), max_length=8)
    state_mutation_refs: tuple[str, ...] = Field(default=(), max_length=8)
    errors: tuple[str, ...] = Field(default=(), max_length=12)
