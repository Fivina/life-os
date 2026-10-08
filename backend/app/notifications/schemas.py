from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=16)
    auth: str = Field(min_length=8)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4000)
    keys: PushSubscriptionKeys
    device_label: str | None = Field(default=None, max_length=120)


class PushSubscriptionRead(BaseModel):
    id: str
    endpoint: str
    device_label: str | None = None
    status: str
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int
    version: int

    class Config:
        from_attributes = True


class TestNotificationCreate(BaseModel):
    title: str = Field(default="Life OS", min_length=1, max_length=180)
    body: str = Field(default="Test notification from Life OS.", min_length=1, max_length=500)
    dedupe_key: str | None = Field(default=None, max_length=180)
    expires_in_minutes: int = Field(default=15, ge=1, le=1440)


class NotificationIntentRead(BaseModel):
    id: str
    intent_type: str
    priority: str
    title: str | None = None
    body: str | None = None
    payload: dict
    status: str
    scheduled_for: datetime | None = None
    expires_at: datetime | None = None
    dedupe_key: str | None = None
    delivered_at: datetime | None = None
    suppressed_reason: str | None = None
    version: int

    class Config:
        from_attributes = True
