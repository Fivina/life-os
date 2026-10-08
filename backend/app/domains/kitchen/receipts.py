from __future__ import annotations

import base64
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AIBinaryInput, AICapability, AIMessage, AIProviderError, AIRequest
from app.core.config import Settings
from app.database.models import InventoryItem, InventoryLot, MediaAsset, ReceiptImport, ReceiptLine, ShoppingNeed, ShoppingNeedItem, UserProfile
from app.domains.finance.service import create_receipt_transaction
from app.domains.kitchen.normalization import normalize_name, resolve_ingredient
from app.domains.kitchen.receipt_schemas import ReceiptImportRead, ReceiptLineRead, ReceiptReviewUpdate, ReceiptUploadCreate
from app.events.service import append_event
from app.media import service as media_service
from app.media.schemas import MediaAssetRead, MediaUploadCreate


class ExtractedReceiptLine(BaseModel):
    raw_text: str
    normalized_name: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    unit_price: Decimal | None = Field(default=None, ge=0)
    line_total: Decimal | None = Field(default=None, ge=0)
    category: str = "other"
    confidence_name: float = Field(default=0, ge=0, le=1)
    confidence_quantity: float = Field(default=0, ge=0, le=1)
    confidence_price: float = Field(default=0, ge=0, le=1)


class ExtractedReceipt(BaseModel):
    merchant: str | None = None
    transaction_at: datetime | None = None
    currency: str = "EUR"
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    items: list[ExtractedReceiptLine] = Field(default_factory=list)


def _read(db: Session, user: UserProfile, row: ReceiptImport) -> ReceiptImportRead:
    asset = db.scalar(select(MediaAsset).where(MediaAsset.id == row.asset_id, MediaAsset.user_id == user.id))
    lines = list(db.scalars(select(ReceiptLine).where(ReceiptLine.receipt_import_id == row.id, ReceiptLine.user_id == user.id).order_by(ReceiptLine.line_number)).all())
    return ReceiptImportRead(
        id=row.id,
        asset=MediaAssetRead.model_validate(asset),
        merchant=row.merchant_raw,
        transaction_at=row.transaction_at,
        currency=row.currency,
        subtotal=row.subtotal,
        tax=row.tax,
        total=row.total,
        status=row.status,
        confidence=row.confidence,
        extraction_provider=row.extraction_provider,
        extraction_model=row.extraction_model,
        failure_reason=row.failure_reason,
        finance_transaction_id=row.finance_transaction_id,
        confirmed_at=row.confirmed_at,
        review_count=sum(line.review_required for line in lines),
        lines=[ReceiptLineRead.model_validate(line) for line in lines],
        version=row.version,
    )


def _get(db: Session, user: UserProfile, receipt_id: str) -> ReceiptImport:
    row = db.scalar(select(ReceiptImport).where(ReceiptImport.id == receipt_id, ReceiptImport.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt import not found.")
    return row


def create_import(db: Session, user: UserProfile, settings: Settings, payload: ReceiptUploadCreate, gateway: AIGateway | None = None) -> ReceiptImportRead:
    asset = media_service.upload(db, user, settings, MediaUploadCreate(kind="receipt", filename=payload.filename, mime_type=payload.mime_type, content_base64=payload.content_base64))
    existing = db.scalar(select(ReceiptImport).where(ReceiptImport.user_id == user.id, ReceiptImport.asset_id == asset.id))
    if existing is not None:
        return _read(db, user, existing)
    row = ReceiptImport(user_id=user.id, asset_id=asset.id, status="uploaded", currency=settings.finance_default_currency, confidence=0, metadata_json={"filename": Path(payload.filename).name})
    db.add(row)
    db.flush()
    append_event(db, user, event_type="receipt.uploaded", aggregate_type="receipt_import", aggregate_id=row.id, payload={"receipt_import_id": row.id, "asset_id": asset.id}, outbox=True, increment_world_revision=False)
    if payload.process:
        process_import(db, user, settings, row.id, gateway=gateway)
    return _read(db, user, row)


def process_import(db: Session, user: UserProfile, settings: Settings, receipt_id: str, gateway: AIGateway | None = None) -> ReceiptImportRead:
    row = _get(db, user, receipt_id)
    if row.status in {"extracted", "review_required", "confirmed"}:
        return _read(db, user, row)
    asset = media_service.get_asset(db, user, row.asset_id)
    data = media_service.local_path(db, user, settings, asset.id).read_bytes()
    schema = ExtractedReceipt.model_json_schema()
    try:
        response = (gateway or AIGateway(settings)).complete(
            db,
            user,
            request_id=f"receipt:{row.id}:vision",
            assistant_role="RECEIPT_SERVICE",
            skill_name="receipt-vision",
            skill_version="1.5",
            capability=AICapability.vision,
            request=AIRequest(
                system_instruction="Extract only visible receipt facts. Return null for missing fields. Classify each line as food, household, deposit, or other. Never infer quantities that are not visible.",
                messages=[AIMessage(role="user", content="Extract this receipt into the required schema.")],
                attachments=[AIBinaryInput(mime_type=asset.mime_type, data_base64=base64.b64encode(data).decode("ascii"))],
                response_schema=schema,
                temperature=0,
                metadata={"mode": "receipt_extraction", "receipt_import_id": row.id},
            ),
            optional=False,
        )
        extracted = ExtractedReceipt.model_validate_json(response.text or "{}")
    except (AIProviderError, ValueError) as exc:
        row.status = "pending_vision"
        row.failure_reason = getattr(exc, "message", str(exc))
        row.version += 1
        return _read(db, user, row)
    for existing in db.scalars(select(ReceiptLine).where(ReceiptLine.receipt_import_id == row.id)).all():
        db.delete(existing)
    db.flush()
    row.merchant_raw = extracted.merchant
    row.transaction_at = extracted.transaction_at
    row.currency = extracted.currency.upper()
    row.subtotal, row.tax, row.total = extracted.subtotal, extracted.tax, extracted.total
    row.confidence = extracted.confidence
    row.extraction_provider, row.extraction_model = response.provider, response.model
    row.failure_reason = None
    review_count = 0
    allowed_categories = {"food", "household", "deposit", "other"}
    for index, item in enumerate(extracted.items, start=1):
        category = item.category if item.category in allowed_categories else "other"
        normalized = normalize_name(item.normalized_name or item.raw_text) or None
        requires_review = item.confidence_name < 0.75 or item.confidence_price < 0.65 or (category == "food" and (item.quantity is None or not item.unit or item.confidence_quantity < 0.7))
        review_count += int(requires_review)
        db.add(ReceiptLine(user_id=user.id, receipt_import_id=row.id, line_number=index, raw_text=item.raw_text, normalized_name=normalized, quantity=item.quantity, unit=item.unit.lower() if item.unit else None, unit_price=item.unit_price, line_total=item.line_total, category=category, confidence_name=item.confidence_name, confidence_quantity=item.confidence_quantity, confidence_price=item.confidence_price, review_required=requires_review, accepted=True, metadata_json={}))
    row.status = "review_required" if review_count else "extracted"
    row.version += 1
    db.flush()
    append_event(db, user, event_type="receipt.extracted", aggregate_type="receipt_import", aggregate_id=row.id, payload={"receipt_import_id": row.id, "line_count": len(extracted.items), "review_count": review_count}, outbox=False, increment_world_revision=False)
    if review_count:
        from app.review.service import ReviewQueueService
        ReviewQueueService().sync_receipt_uncertainty(db, user, row.id)
    return _read(db, user, row)


def update_review(db: Session, user: UserProfile, receipt_id: str, payload: ReceiptReviewUpdate) -> ReceiptImportRead:
    row = _get(db, user, receipt_id)
    if row.status == "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A confirmed receipt cannot be edited.")
    if payload.merchant is not None: row.merchant_raw = payload.merchant
    if payload.transaction_at is not None: row.transaction_at = payload.transaction_at
    if payload.currency is not None: row.currency = payload.currency.upper()
    if payload.total is not None: row.total = payload.total
    for line_id, update in payload.lines.items():
        line = db.scalar(select(ReceiptLine).where(ReceiptLine.id == line_id, ReceiptLine.receipt_import_id == row.id, ReceiptLine.user_id == user.id))
        if line is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Receipt line {line_id} not found.")
        values = update.model_dump(exclude_unset=True)
        expires_at = values.pop("expires_at", None)
        for name, value in values.items(): setattr(line, name, value)
        if expires_at is not None: line.metadata_json = {**(line.metadata_json or {}), "expires_at": expires_at.isoformat()}
        if update.review_required is None: line.review_required = False
        line.version += 1
    remaining = db.scalar(select(ReceiptLine.id).where(ReceiptLine.receipt_import_id == row.id, ReceiptLine.review_required.is_(True)).limit(1))
    row.status = "review_required" if remaining else "extracted"
    row.version += 1
    db.flush()
    return _read(db, user, row)


def _inventory_item(db: Session, user: UserProfile, line: ReceiptLine, merchant: str | None) -> InventoryItem:
    ingredient = resolve_ingredient(db, user, line.normalized_name or line.raw_text, merchant=merchant, default_unit=line.unit, category="food", source="receipt")
    line.ingredient_id = ingredient.id
    item = db.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.ingredient_id == ingredient.id, InventoryItem.active.is_(True)))
    if item is None:
        item = InventoryItem(user_id=user.id, ingredient_id=ingredient.id, ingredient_name=ingredient.name, quantity=0, unit=line.unit or ingredient.default_unit or "count", source="receipt", category="food", canonical_unit=line.unit or ingredient.default_unit or "count", default_storage_location="fridge", active=True)
        db.add(item)
        db.flush()
    line.inventory_item_id = item.id
    return item


def _reconcile_shopping(db: Session, user: UserProfile, line: ReceiptLine) -> None:
    target = normalize_name(line.normalized_name or line.raw_text)
    candidates = list(db.scalars(select(ShoppingNeedItem).join(ShoppingNeed, ShoppingNeed.id == ShoppingNeedItem.shopping_need_id).where(ShoppingNeedItem.user_id == user.id, ShoppingNeed.status == "active", ShoppingNeedItem.satisfied.is_(False))).all())
    match = next((item for item in candidates if normalize_name(item.ingredient_name) == target), None)
    if match is not None:
        match.satisfied, match.status = True, "purchased"
        match.purchased_quantity = line.quantity or match.quantity
        match.version += 1
        line.shopping_need_item_id = match.id


def _prior_manual_purchase(db: Session, user: UserProfile, line: ReceiptLine) -> ShoppingNeedItem | None:
    target = normalize_name(line.normalized_name or line.raw_text)
    candidates = list(db.scalars(select(ShoppingNeedItem).join(ShoppingNeed, ShoppingNeed.id == ShoppingNeedItem.shopping_need_id).where(ShoppingNeedItem.user_id == user.id, ShoppingNeed.status == "active", ShoppingNeedItem.status == "purchased", ShoppingNeedItem.source_type == "manual_purchase")).all())
    return next((item for item in candidates if normalize_name(item.ingredient_name) == target and item.inventory_item_id), None)


def confirm_import(db: Session, user: UserProfile, receipt_id: str) -> ReceiptImportRead:
    row = _get(db, user, receipt_id)
    if row.status == "confirmed":
        return _read(db, user, row)
    lines = list(db.scalars(select(ReceiptLine).where(ReceiptLine.receipt_import_id == row.id, ReceiptLine.user_id == user.id).order_by(ReceiptLine.line_number)).all())
    if any(line.accepted and line.review_required for line in lines):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resolve uncertain receipt lines before confirmation.")
    if row.total is None or row.transaction_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receipt date and total are required before confirmation.")
    for line in lines:
        if not line.accepted or line.category != "food" or line.inventory_lot_id:
            continue
        if line.quantity is None or not line.unit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Quantity and unit are required for food line {line.line_number}.")
        prior_purchase = _prior_manual_purchase(db, user, line)
        if prior_purchase is not None:
            line.inventory_item_id = prior_purchase.inventory_item_id
            line.shopping_need_item_id = prior_purchase.id
            line.metadata_json = {**(line.metadata_json or {}), "inventory_reconciled_from_manual_purchase": True}
            continue
        item = _inventory_item(db, user, line, row.merchant_raw)
        expires_at = None
        if (line.metadata_json or {}).get("expires_at"):
            expires_at = datetime.fromisoformat(line.metadata_json["expires_at"])
        lot = InventoryLot(user_id=user.id, inventory_item_id=item.id, quantity=line.quantity, unit=line.unit, purchased_at=row.transaction_at, expires_at=expires_at, storage_location=item.default_storage_location or "fridge", source="receipt", source_reference_type="receipt_line", source_reference_id=line.id, confidence=min(line.confidence_name, line.confidence_quantity), status="active")
        db.add(lot)
        db.flush()
        line.inventory_lot_id = lot.id
        item.quantity = float(item.quantity or 0) + line.quantity
        item.version += 1
        _reconcile_shopping(db, user, line)
    transaction = create_receipt_transaction(db, user, receipt_import_id=row.id, occurred_on=row.transaction_at.astimezone(UTC).date() if row.transaction_at.tzinfo else row.transaction_at.date(), amount=row.total, currency=row.currency, merchant_raw=row.merchant_raw)
    db.flush()
    row.finance_transaction_id = transaction.id
    row.status, row.confirmed_at = "confirmed", datetime.now(UTC)
    row.version += 1
    append_event(db, user, event_type="receipt.confirmed", aggregate_type="receipt_import", aggregate_id=row.id, payload={"receipt_import_id": row.id, "finance_transaction_id": transaction.id, "food_lines": sum(line.accepted and line.category == "food" for line in lines), "non_food_lines": sum(line.accepted and line.category != "food" for line in lines)}, outbox=True)
    return _read(db, user, row)


def get_import(db: Session, user: UserProfile, receipt_id: str) -> ReceiptImportRead:
    return _read(db, user, _get(db, user, receipt_id))


def list_imports(db: Session, user: UserProfile, limit: int = 30) -> list[ReceiptImportRead]:
    rows = list(db.scalars(select(ReceiptImport).where(ReceiptImport.user_id == user.id).order_by(ReceiptImport.created_at.desc()).limit(limit)).all())
    return [_read(db, user, row) for row in rows]
