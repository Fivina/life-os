from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConversationThreadCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    default_skill: str = Field(default="self-core", min_length=1, max_length=120)


class ConversationThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    default_skill: str
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    role: str
    content: str
    skill_name: str | None
    request_id: str | None
    sequence_number: int
    metadata_json: dict[str, Any]
    created_at: datetime


class ConversationSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    covered_message_count: int
    covers_until_message_id: str | None
    updated_at: datetime


class ConversationThreadDetail(ConversationThreadRead):
    messages: list[ConversationMessageRead] = Field(default_factory=list)
    summary: ConversationSummaryRead | None = None
