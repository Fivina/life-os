from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaUploadCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=60)
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=4)
    linked_entity_type: str | None = Field(default=None, max_length=80)
    linked_entity_id: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class MediaGenerateRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=60)
    prompt: str = Field(min_length=1, max_length=4000)
    linked_entity_type: str = Field(min_length=1, max_length=80)
    linked_entity_id: str
    generation_version: str = Field(default="v1", max_length=80)
    aspect_ratio: str = Field(default="1:1", max_length=20)


class MediaAssetRead(BaseModel):
    id: str
    kind: str
    storage_provider: str
    mime_type: str
    size_bytes: int
    content_hash: str
    source: str
    provider: str | None
    model: str | None
    generation_version: str | None
    linked_entity_type: str | None
    linked_entity_id: str | None
    width: int | None
    height: int | None
    metadata_json: dict
    created_at: datetime
    last_used_at: datetime | None
    version: int

    model_config = {"from_attributes": True}
