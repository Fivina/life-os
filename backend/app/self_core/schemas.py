from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SelfCoreReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_type: str
    ref_id: str
    title: str
    status: str | None = None
    starts_at: datetime | None = None
    detail: str | None = None


class MorningBriefingContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    generated_at: datetime
    fingerprint: str
    plan_id: str
    plan_version: int
    world_revision: int
    first_block: SelfCoreReference | None = None
    important_blocks: tuple[SelfCoreReference, ...] = Field(default=(), max_length=5)
    protected_commitments: tuple[SelfCoreReference, ...] = Field(default=(), max_length=4)
    trajectory_changes: tuple[SelfCoreReference, ...] = Field(default=(), max_length=4)
    active_proposals: tuple[SelfCoreReference, ...] = Field(default=(), max_length=3)
    attention_items: tuple[SelfCoreReference, ...] = Field(default=(), max_length=4)
    active_workspace: SelfCoreReference | None = None
    kitchen_signals: tuple[SelfCoreReference, ...] = Field(default=(), max_length=3)
    finance_signal: dict[str, Any] | None = None
    omitted_categories: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = Field(default=(), max_length=24)
    briefing_policy_version: Literal["morning-briefing-v1"] = "morning-briefing-v1"


class MorningBriefingResponse(BaseModel):
    context: MorningBriefingContext
    message: str
    reused: bool
    plan_created: bool


class SelfCoreSurface(BaseModel):
    morning: MorningBriefingResponse
    conversation_thread_id: str | None = None

