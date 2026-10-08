from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.media.schemas import MediaAssetRead


class ReceiptUploadCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str
    content_base64: str = Field(min_length=4)
    process: bool = True


class ReceiptLineUpdate(BaseModel):
    normalized_name: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    line_total: Decimal | None = Field(default=None, ge=0)
    category: str | None = None
    accepted: bool | None = None
    review_required: bool | None = None
    expires_at: datetime | None = None


class ReceiptReviewUpdate(BaseModel):
    merchant: str | None = None
    transaction_at: datetime | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    total: Decimal | None = Field(default=None, ge=0)
    lines: dict[str, ReceiptLineUpdate] = Field(default_factory=dict)


class ReceiptLineRead(BaseModel):
    id: str
    line_number: int
    raw_text: str
    normalized_name: str | None
    quantity: float | None
    unit: str | None
    unit_price: Decimal | None
    line_total: Decimal | None
    category: str
    confidence_name: float
    confidence_quantity: float
    confidence_price: float
    review_required: bool
    accepted: bool
    ingredient_id: str | None
    inventory_item_id: str | None
    inventory_lot_id: str | None
    shopping_need_item_id: str | None
    metadata_json: dict
    version: int
    model_config = {"from_attributes": True}


class ReceiptImportRead(BaseModel):
    id: str
    asset: MediaAssetRead
    merchant: str | None
    transaction_at: datetime | None
    currency: str
    subtotal: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    status: str
    confidence: float
    extraction_provider: str | None
    extraction_model: str | None
    failure_reason: str | None
    finance_transaction_id: str | None
    confirmed_at: datetime | None
    review_count: int
    lines: list[ReceiptLineRead]
    version: int
