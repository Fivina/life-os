from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


NotebookEntryType = Literal["GENERAL", "IMPLEMENTATION_IDEA"]


class NotebookEntryCreate(BaseModel):
    entry_type: NotebookEntryType = "GENERAL"
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="manual", max_length=60)
    source_ref: str | None = Field(default=None, max_length=160)
    conversation_thread_id: str | None = None
    workspace_ref: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "content")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))


class NotebookEntryUpdate(BaseModel):
    expected_version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    tags: list[str] | None = Field(default=None, max_length=20)


class NotebookEntryRead(BaseModel):
    id: str
    entry_type: str
    title: str
    content: str
    status: str
    source: str
    source_ref: str | None
    conversation_thread_id: str | None
    workspace_ref: str | None
    tags_json: list[str]
    metadata_json: dict[str, Any]
    reviewed_at: datetime | None
    archived_at: datetime | None
    promoted_at: datetime | None
    embedding_provider: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class NotebookSearchResult(BaseModel):
    entry: NotebookEntryRead
    score: float
    lexical_score: float
    semantic_score: float | None = None


class NotebookPromotionRequest(BaseModel):
    destination_type: Literal["MANUAL_DEVELOPMENT_REVIEW"] = "MANUAL_DEVELOPMENT_REVIEW"
    destination_ref: str | None = Field(default=None, max_length=160)


class NotebookPromotionRead(BaseModel):
    id: str
    notebook_entry_id: str
    destination_type: str
    destination_ref: str | None
    created_at: datetime
    version: int

    model_config = {"from_attributes": True}
