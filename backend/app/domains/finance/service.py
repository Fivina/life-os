from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from statistics import median

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    FinanceBudget,
    FinanceCategory,
    FinanceImportBatch,
    FinanceImportRow,
    FinanceTransaction,
    Goal,
    MerchantAlias,
    MerchantIdentity,
    RecurringExpense,
    UserProfile,
)
from app.domains.finance.schemas import (
    BudgetCreate,
    BudgetRead,
    CsvImportCreate,
    FinanceOverviewRead,
    GroceryBudgetContext,
    ImportBatchRead,
    ImportRowRead,
    ImportRowUpdate,
    ManualTransactionCreate,
    RecurringExpenseRead,
    SafeToSpendRead,
    TransactionRead,
)
from app.events.service import append_event

MONEY = Decimal("0.01")
DEFAULT_CATEGORIES = {
    "Groceries": "expense",
    "Dining": "expense",
    "Housing": "expense",
    "Transport": "expense",
    "Health": "expense",
    "Entertainment": "expense",
    "Shopping": "expense",
    "Subscriptions": "expense",
    "Income": "income",
    "Savings": "transfer",
    "Other": "expense",
}
HEADER_ALIASES = {
    "date": {"date", "booking date", "transaction date", "datum", "buchungstag", "valuta"},
    "description": {"description", "details", "purpose", "memo", "verwendungszweck", "text"},
    "merchant": {"merchant", "payee", "counterparty", "vendor", "empfaenger", "beguenstigter"},
    "amount": {"amount", "value", "transaction amount", "betrag", "umsatz"},
    "debit": {"debit", "withdrawal", "soll"},
    "credit": {"credit", "deposit", "haben"},
    "currency": {"currency", "waehrung"},
    "external_id": {"id", "transaction id", "reference", "referenz"},
}


def _money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _parse_money(raw: str | None) -> Decimal | None:
    if raw is None or not raw.strip():
        return None
    cleaned = re.sub(r"[^0-9,.-]", "", raw.strip())
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".") if cleaned.rfind(",") > cleaned.rfind(".") else cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return _money(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {raw}") from exc


def _parse_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    value = raw.strip().split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {raw}")


def normalize_merchant(value: str | None) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", (value or "").upper())
    text = re.sub(r"\b(?:SAGT DANKE|MARKT|STORE|FILIALE|EC|CARD|POS)\b", " ", text)
    text = re.sub(r"\b\d{3,}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip() or "UNKNOWN"


def _category(db: Session, user: UserProfile, name: str, kind: str | None = None) -> FinanceCategory:
    row = db.scalar(select(FinanceCategory).where(FinanceCategory.user_id == user.id, func.lower(FinanceCategory.name) == name.lower()))
    if row is None:
        row = FinanceCategory(user_id=user.id, name=name, kind=kind or DEFAULT_CATEGORIES.get(name, "expense"), active=True)
        db.add(row)
        db.flush()
    return row


def ensure_categories(db: Session, user: UserProfile) -> None:
    for name, kind in DEFAULT_CATEGORIES.items():
        _category(db, user, name, kind)


def _merchant(db: Session, user: UserProfile, raw: str | None) -> MerchantIdentity | None:
    if not raw:
        return None
    alias_key = normalize_merchant(raw)
    alias = db.scalar(select(MerchantAlias).where(MerchantAlias.user_id == user.id, MerchantAlias.normalized_alias == alias_key))
    if alias is not None:
        return db.get(MerchantIdentity, alias.merchant_id)
    row = db.scalar(select(MerchantIdentity).where(MerchantIdentity.user_id == user.id, MerchantIdentity.normalized_name == alias_key))
    if row is None:
        row = MerchantIdentity(user_id=user.id, name=alias_key.title(), normalized_name=alias_key)
        db.add(row)
        db.flush()
    db.add(MerchantAlias(user_id=user.id, merchant_id=row.id, alias=raw, normalized_alias=alias_key, source="observed"))
    db.flush()
    return row


def _deterministic_category(db: Session, user: UserProfile, merchant: MerchantIdentity | None, text: str, direction: str) -> tuple[FinanceCategory, float]:
    if direction == "income":
        return _category(db, user, "Income", "income"), 0.98
    if merchant and merchant.default_category_id:
        known = db.get(FinanceCategory, merchant.default_category_id)
        if known is not None:
            return known, 0.99
    normalized = f"{merchant.normalized_name if merchant else ''} {text}".lower()
    rules = {
        "Groceries": ("rewe", "aldi", "lidl", "edeka", "kaufland", "supermarket", "grocery"),
        "Dining": ("restaurant", "cafe", "lieferando", "mcdonald", "burger", "pizza"),
        "Housing": ("rent", "miete", "utility", "electric", "strom"),
        "Transport": ("bahn", "uber", "fuel", "tankstelle", "transport"),
        "Health": ("pharmacy", "apotheke", "doctor"),
        "Subscriptions": ("netflix", "spotify", "subscription", "abo"),
        "Entertainment": ("cinema", "kino", "steam"),
    }
    for name, terms in rules.items():
        if any(term in normalized for term in terms):
            return _category(db, user, name), 0.92
    return _category(db, user, "Other"), 0.45


def _fingerprint(occurred_on: date, amount: Decimal, currency: str, direction: str, merchant: MerchantIdentity | None, description: str | None, external_id: str | None) -> str:
    if external_id:
        material = f"external|{external_id.strip().lower()}|{currency.upper()}"
    else:
        material = "|".join((occurred_on.isoformat(), str(_money(amount)), currency.upper(), direction, merchant.normalized_name if merchant else "", re.sub(r"\s+", " ", (description or "").lower()).strip()))
    return sha256(material.encode("utf-8")).hexdigest()


def _transaction_read(db: Session, row: FinanceTransaction) -> TransactionRead:
    merchant = db.get(MerchantIdentity, row.merchant_id) if row.merchant_id else None
    category = db.get(FinanceCategory, row.category_id) if row.category_id else None
    return TransactionRead(
        id=row.id, occurred_on=row.occurred_on, amount=row.amount, currency=row.currency, direction=row.direction,
        merchant_raw=row.merchant_raw, merchant_name=merchant.name if merchant else None, description=row.description,
        category_name=category.name if category else None, source=row.source, external_id=row.external_id,
        receipt_import_id=row.receipt_import_id, import_batch_id=row.import_batch_id, version=row.version,
    )


def _row_read(db: Session, row: FinanceImportRow) -> ImportRowRead:
    merchant = db.get(MerchantIdentity, row.merchant_id) if row.merchant_id else None
    category = db.get(FinanceCategory, row.category_id) if row.category_id else None
    return ImportRowRead(
        id=row.id, row_number=row.row_number, occurred_on=row.occurred_on, amount=row.amount, currency=row.currency,
        direction=row.direction, merchant_raw=row.merchant_raw, merchant_name=merchant.name if merchant else None,
        description=row.description, category_name=category.name if category else None, external_id=row.external_id,
        confidence=row.confidence, review_required=row.review_required, status=row.status, error=row.error,
        raw_json=row.raw_json or {}, version=row.version,
    )


def _batch_read(db: Session, batch: FinanceImportBatch) -> ImportBatchRead:
    rows = list(db.scalars(select(FinanceImportRow).where(FinanceImportRow.batch_id == batch.id, FinanceImportRow.user_id == batch.user_id).order_by(FinanceImportRow.row_number)).all())
    return ImportBatchRead(
        id=batch.id, filename=batch.filename, status=batch.status, currency=batch.currency, mapping_json=batch.mapping_json,
        row_count=batch.row_count, ready_count=batch.ready_count, review_count=batch.review_count,
        duplicate_count=batch.duplicate_count, error_count=batch.error_count, confirmed_at=batch.confirmed_at,
        rows=[_row_read(db, row) for row in rows], version=batch.version,
    )


def _refresh_batch_counts(db: Session, batch: FinanceImportBatch) -> None:
    rows = list(db.scalars(select(FinanceImportRow).where(FinanceImportRow.batch_id == batch.id)).all())
    batch.row_count = len(rows)
    batch.ready_count = sum(row.status == "ready" and not row.review_required for row in rows)
    batch.review_count = sum(row.review_required and row.status not in {"ignored", "duplicate"} for row in rows)
    batch.duplicate_count = sum(row.status in {"duplicate", "reconciled"} for row in rows)
    batch.error_count = sum(row.status == "error" for row in rows)
    batch.status = "review_required" if batch.review_count else "draft"


def _detect_mapping(fieldnames: list[str], supplied: dict[str, str]) -> dict[str, str]:
    mapping = dict(supplied)
    lowered = {name.strip().lower(): name for name in fieldnames}
    for target, aliases in HEADER_ALIASES.items():
        if target not in mapping:
            match = next((lowered[name] for name in aliases if name in lowered), None)
            if match:
                mapping[target] = match
    return mapping


def create_csv_import(db: Session, user: UserProfile, payload: CsvImportCreate) -> ImportBatchRead:
    digest = sha256(payload.content.encode("utf-8-sig")).hexdigest()
    existing = db.scalar(select(FinanceImportBatch).where(FinanceImportBatch.user_id == user.id, FinanceImportBatch.content_hash == digest))
    if existing is not None:
        return _batch_read(db, existing)
    ensure_categories(db, user)
    reader = csv.DictReader(io.StringIO(payload.content.lstrip("\ufeff")))
    fields = reader.fieldnames or []
    mapping = _detect_mapping(fields, payload.mapping)
    batch = FinanceImportBatch(user_id=user.id, filename=payload.filename.split("/")[-1].split("\\")[-1], content_hash=digest, status="draft", currency=payload.currency.upper(), mapping_json=mapping)
    db.add(batch)
    db.flush()
    if "date" not in mapping or not ({"amount", "debit", "credit"} & set(mapping)):
        batch.status = "mapping_required"
        batch.error_count = 1
        return _batch_read(db, batch)
    for number, raw in enumerate(reader, start=2):
        row = FinanceImportRow(user_id=user.id, batch_id=batch.id, row_number=number, currency=(raw.get(mapping.get("currency", "")) or payload.currency).upper(), raw_json=raw)
        try:
            row.occurred_on = _parse_date(raw.get(mapping["date"]))
            amount_value = _parse_money(raw.get(mapping.get("amount", ""))) if mapping.get("amount") else None
            debit = _parse_money(raw.get(mapping.get("debit", ""))) if mapping.get("debit") else None
            credit = _parse_money(raw.get(mapping.get("credit", ""))) if mapping.get("credit") else None
            if amount_value is not None:
                row.direction = "expense" if amount_value < 0 else "income"
                row.amount = abs(amount_value)
            elif debit not in {None, Decimal("0.00")}:
                row.direction, row.amount = "expense", abs(debit)
            elif credit not in {None, Decimal("0.00")}:
                row.direction, row.amount = "income", abs(credit)
            else:
                raise ValueError("Missing transaction amount")
            row.description = raw.get(mapping.get("description", "")) or None
            row.merchant_raw = raw.get(mapping.get("merchant", "")) or row.description
            row.external_id = raw.get(mapping.get("external_id", "")) or None
            merchant = _merchant(db, user, row.merchant_raw)
            row.merchant_id = merchant.id if merchant else None
            category, confidence = _deterministic_category(db, user, merchant, row.description or "", row.direction)
            row.category_id, row.confidence = category.id, confidence
            row.review_required = confidence < 0.7
            row.fingerprint = _fingerprint(row.occurred_on, row.amount, row.currency, row.direction, merchant, row.description, row.external_id)
            row.status = "duplicate" if db.scalar(select(FinanceTransaction.id).where(FinanceTransaction.user_id == user.id, FinanceTransaction.fingerprint == row.fingerprint)) else "ready"
        except (ValueError, InvalidOperation) as exc:
            row.status, row.review_required, row.error, row.confidence = "error", True, str(exc), 0
        db.add(row)
    db.flush()
    _refresh_batch_counts(db, batch)
    append_event(db, user, event_type="finance.import.drafted", aggregate_type="finance_import_batch", aggregate_id=batch.id, payload={"batch_id": batch.id, "rows": batch.row_count, "review": batch.review_count}, outbox=False, increment_world_revision=False)
    return _batch_read(db, batch)


def get_import(db: Session, user: UserProfile, batch_id: str) -> ImportBatchRead:
    batch = db.scalar(select(FinanceImportBatch).where(FinanceImportBatch.id == batch_id, FinanceImportBatch.user_id == user.id))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finance import not found.")
    return _batch_read(db, batch)


def update_import_row(db: Session, user: UserProfile, row_id: str, payload: ImportRowUpdate) -> ImportBatchRead:
    row = db.scalar(select(FinanceImportRow).where(FinanceImportRow.id == row_id, FinanceImportRow.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import row not found.")
    if payload.occurred_on is not None: row.occurred_on = payload.occurred_on
    if payload.amount is not None: row.amount = abs(_money(payload.amount))
    if payload.direction is not None: row.direction = payload.direction
    if payload.description is not None: row.description = payload.description
    if payload.merchant is not None:
        row.merchant_raw = payload.merchant
        merchant = _merchant(db, user, payload.merchant)
        row.merchant_id = merchant.id if merchant else None
    merchant = db.get(MerchantIdentity, row.merchant_id) if row.merchant_id else None
    if payload.category:
        category = _category(db, user, payload.category)
        row.category_id = category.id
        if merchant:
            merchant.default_category_id = category.id
    if payload.accept and row.occurred_on and row.amount is not None and row.direction:
        row.fingerprint = _fingerprint(row.occurred_on, row.amount, row.currency, row.direction, merchant, row.description, row.external_id)
        row.review_required, row.status, row.error, row.confidence = False, "ready", None, 1
    elif not payload.accept:
        row.review_required, row.status = False, "ignored"
    batch = db.get(FinanceImportBatch, row.batch_id)
    _refresh_batch_counts(db, batch)
    return _batch_read(db, batch)


def _matching_receipt_transaction(db: Session, user: UserProfile, occurred_on: date, amount: Decimal, currency: str, merchant: MerchantIdentity | None) -> FinanceTransaction | None:
    candidates = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.occurred_on == occurred_on, FinanceTransaction.amount == amount, FinanceTransaction.currency == currency, FinanceTransaction.direction == "expense")).all())
    return next((row for row in candidates if row.receipt_import_id and (not merchant or row.merchant_id == merchant.id)), None)


def confirm_import(db: Session, user: UserProfile, batch_id: str) -> ImportBatchRead:
    batch = db.scalar(select(FinanceImportBatch).where(FinanceImportBatch.id == batch_id, FinanceImportBatch.user_id == user.id))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finance import not found.")
    if batch.status == "confirmed":
        return _batch_read(db, batch)
    rows = list(db.scalars(select(FinanceImportRow).where(FinanceImportRow.batch_id == batch.id).order_by(FinanceImportRow.row_number)).all())
    unresolved = [row for row in rows if row.review_required or row.status == "error"]
    if unresolved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resolve or dismiss ambiguous CSV rows before confirmation.")
    imported = 0
    for row in rows:
        if row.status in {"ignored", "duplicate", "reconciled"}:
            continue
        merchant = db.get(MerchantIdentity, row.merchant_id) if row.merchant_id else None
        existing = db.scalar(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.fingerprint == row.fingerprint))
        if existing is None and row.direction == "expense":
            existing = _matching_receipt_transaction(db, user, row.occurred_on, row.amount, row.currency, merchant)
        if existing is not None:
            existing.import_batch_id = batch.id
            existing.external_id = existing.external_id or row.external_id
            existing.metadata_json = {**(existing.metadata_json or {}), "csv_reconciled": True}
            row.status = "reconciled"
            continue
        db.add(FinanceTransaction(user_id=user.id, occurred_on=row.occurred_on, amount=row.amount, currency=row.currency, direction=row.direction, merchant_raw=row.merchant_raw, merchant_id=row.merchant_id, description=row.description, category_id=row.category_id, source="csv", external_id=row.external_id, fingerprint=row.fingerprint, import_batch_id=batch.id, metadata_json={"import_row_id": row.id}))
        row.status = "imported"
        imported += 1
    batch.status, batch.confirmed_at = "confirmed", datetime.now(UTC)
    _refresh_batch_counts(db, batch)
    batch.status = "confirmed"
    append_event(db, user, event_type="finance.transaction_imported", aggregate_type="finance_import_batch", aggregate_id=batch.id, payload={"batch_id": batch.id, "imported": imported, "reconciled": sum(row.status == "reconciled" for row in rows)}, outbox=True)
    return _batch_read(db, batch)


def create_receipt_transaction(db: Session, user: UserProfile, *, receipt_import_id: str, occurred_on: date, amount: Decimal, currency: str, merchant_raw: str | None) -> FinanceTransaction:
    ensure_categories(db, user)
    existing_by_receipt = db.scalar(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.receipt_import_id == receipt_import_id))
    if existing_by_receipt is not None:
        return existing_by_receipt
    merchant = _merchant(db, user, merchant_raw)
    match = _matching_receipt_transaction(db, user, occurred_on, _money(amount), currency, merchant)
    if match is None:
        candidates = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.occurred_on == occurred_on, FinanceTransaction.amount == _money(amount), FinanceTransaction.currency == currency, FinanceTransaction.direction == "expense")).all())
        match = next((row for row in candidates if not merchant or row.merchant_id == merchant.id), None)
    if match is not None:
        match.receipt_import_id = receipt_import_id
        match.metadata_json = {**(match.metadata_json or {}), "receipt_reconciled": True}
        return match
    category = _category(db, user, "Groceries")
    fingerprint = _fingerprint(occurred_on, _money(amount), currency, "expense", merchant, "grocery receipt", None)
    row = FinanceTransaction(user_id=user.id, occurred_on=occurred_on, amount=_money(amount), currency=currency, direction="expense", merchant_raw=merchant_raw, merchant_id=merchant.id if merchant else None, description="Grocery receipt", category_id=category.id, source="receipt", fingerprint=fingerprint, receipt_import_id=receipt_import_id, metadata_json={})
    db.add(row)
    db.flush()
    return row


def create_manual_transaction(db: Session, user: UserProfile, payload: ManualTransactionCreate) -> TransactionRead:
    """Create one user-confirmed transaction through Finance canonical rules."""
    existing = db.scalar(select(FinanceTransaction).where(
        FinanceTransaction.user_id == user.id,
        FinanceTransaction.source == "quick_capture",
        FinanceTransaction.external_id == payload.idempotency_key,
    ))
    if existing is not None:
        return _transaction_read(db, existing)
    ensure_categories(db, user)
    merchant = _merchant(db, user, payload.merchant)
    category = _category(db, user, payload.category)
    amount = _money(payload.amount)
    fingerprint = _fingerprint(payload.occurred_on, amount, payload.currency.upper(), "expense", merchant, payload.description, payload.idempotency_key)
    duplicate = db.scalar(select(FinanceTransaction).where(
        FinanceTransaction.user_id == user.id,
        FinanceTransaction.fingerprint == fingerprint,
    ))
    if duplicate is not None:
        return _transaction_read(db, duplicate)
    row = FinanceTransaction(
        user_id=user.id, occurred_on=payload.occurred_on, amount=amount,
        currency=payload.currency.upper(), direction="expense", merchant_raw=payload.merchant,
        merchant_id=merchant.id if merchant else None, description=payload.description,
        category_id=category.id, source="quick_capture", external_id=payload.idempotency_key,
        fingerprint=fingerprint, metadata_json={"capture_source": True},
    )
    db.add(row)
    db.flush()
    append_event(
        db, user, event_type="finance.transaction_created", aggregate_type="finance_transaction",
        aggregate_id=row.id, payload={"transaction_id": row.id, "source": "quick_capture", "category": category.name},
        outbox=True,
    )
    return _transaction_read(db, row)


def list_transactions(db: Session, user: UserProfile, limit: int = 100) -> list[TransactionRead]:
    rows = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id).order_by(FinanceTransaction.occurred_on.desc(), FinanceTransaction.created_at.desc()).limit(limit)).all())
    return [_transaction_read(db, row) for row in rows]


def create_budget(db: Session, user: UserProfile, payload: BudgetCreate) -> BudgetRead:
    category = _category(db, user, payload.category) if payload.category else None
    row = db.scalar(select(FinanceBudget).where(FinanceBudget.user_id == user.id, FinanceBudget.name == payload.name, FinanceBudget.month_start == payload.month_start))
    if row is None:
        row = FinanceBudget(user_id=user.id, category_id=category.id if category else None, name=payload.name, amount=_money(payload.amount), currency=payload.currency, period="monthly", month_start=payload.month_start, protected=payload.protected, active=True)
        db.add(row)
    else:
        row.amount, row.category_id, row.protected, row.active = _money(payload.amount), category.id if category else None, payload.protected, True
        row.version += 1
    db.flush()
    append_event(db, user, event_type="finance.budget_updated", aggregate_type="finance_budget", aggregate_id=row.id, payload={"budget_id": row.id, "name": row.name}, outbox=False)
    return _budget_read(db, row)


def _budget_read(db: Session, row: FinanceBudget) -> BudgetRead:
    category = db.get(FinanceCategory, row.category_id) if row.category_id else None
    end = (row.month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    query = select(func.coalesce(func.sum(FinanceTransaction.amount), 0)).where(FinanceTransaction.user_id == row.user_id, FinanceTransaction.direction == "expense", FinanceTransaction.currency == row.currency, FinanceTransaction.occurred_on >= row.month_start, FinanceTransaction.occurred_on < end)
    if row.category_id: query = query.where(FinanceTransaction.category_id == row.category_id)
    spent = _money(db.scalar(query) or 0)
    return BudgetRead(id=row.id, name=row.name, category_name=category.name if category else None, amount=row.amount, spent=spent, remaining=max(Decimal("0.00"), row.amount - spent), currency=row.currency, month_start=row.month_start, protected=row.protected, active=row.active, version=row.version)


def list_budgets(db: Session, user: UserProfile, month_start: date) -> list[BudgetRead]:
    rows = list(db.scalars(select(FinanceBudget).where(FinanceBudget.user_id == user.id, FinanceBudget.month_start == month_start.replace(day=1), FinanceBudget.active.is_(True)).order_by(FinanceBudget.name)).all())
    return [_budget_read(db, row) for row in rows]


def refresh_recurring(db: Session, user: UserProfile) -> list[RecurringExpenseRead]:
    rows = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.direction == "expense", FinanceTransaction.merchant_id.is_not(None)).order_by(FinanceTransaction.merchant_id, FinanceTransaction.occurred_on)).all())
    grouped: dict[str, list[FinanceTransaction]] = defaultdict(list)
    for row in rows: grouped[row.merchant_id].append(row)
    for merchant_id, samples in grouped.items():
        if len(samples) < 3: continue
        intervals = [(samples[index].occurred_on - samples[index - 1].occurred_on).days for index in range(1, len(samples))]
        typical_interval = round(median(intervals))
        amounts = [Decimal(item.amount) for item in samples]
        typical_amount = _money(sum(amounts) / len(amounts))
        amount_spread = max(amounts) - min(amounts)
        regular = 25 <= typical_interval <= 35 or 6 <= typical_interval <= 8 or 350 <= typical_interval <= 380
        confidence = min(0.95, 0.45 + len(samples) * 0.1 + (0.15 if regular else 0) - float(amount_spread / max(typical_amount, Decimal("1"))) * 0.15)
        if confidence < 0.55: continue
        merchant = db.get(MerchantIdentity, merchant_id)
        recurring = db.scalar(select(RecurringExpense).where(RecurringExpense.user_id == user.id, RecurringExpense.merchant_id == merchant_id))
        if recurring is None:
            recurring = RecurringExpense(user_id=user.id, merchant_id=merchant_id, category_id=samples[-1].category_id, name=merchant.name if merchant else "Recurring expense", typical_amount=typical_amount, currency=samples[-1].currency, interval_days=typical_interval, confidence=confidence, evidence_count=len(samples), status="likely")
            db.add(recurring)
        recurring.typical_amount, recurring.interval_days, recurring.next_expected_on = typical_amount, typical_interval, samples[-1].occurred_on + timedelta(days=typical_interval)
        recurring.confidence, recurring.evidence_count, recurring.status = round(confidence, 3), len(samples), "likely"
    db.flush()
    result = list(db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id).order_by(RecurringExpense.next_expected_on)).all())
    return [RecurringExpenseRead.model_validate(row) for row in result]


def safe_to_spend(db: Session, user: UserProfile, month_start: date | None = None, currency: str = "EUR") -> SafeToSpendRead:
    first = (month_start or date.today()).replace(day=1)
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    tx = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.currency == currency, FinanceTransaction.occurred_on >= first, FinanceTransaction.occurred_on < end)).all())
    income = _money(sum((row.amount for row in tx if row.direction == "income"), Decimal("0")))
    spending = _money(sum((row.amount for row in tx if row.direction == "expense"), Decimal("0")))
    recurring = [RecurringExpenseRead.model_validate(row) for row in db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id, RecurringExpense.status == "likely")).all()]
    today = date.today()
    upcoming = _money(sum((row.typical_amount for row in recurring if row.next_expected_on and today <= row.next_expected_on < end), Decimal("0")))
    protected = _money(sum((item.remaining for item in list_budgets(db, user, first) if item.protected), Decimal("0")))
    savings = Decimal("0.00")
    safe = max(Decimal("0.00"), _money(income - spending - upcoming - protected - savings))
    return SafeToSpendRead(currency=currency, income_to_date=income, spending_to_date=spending, upcoming_recurring=upcoming, protected_budget_remaining=protected, planned_savings=savings, safe_to_spend=safe, assumptions=["Uses recorded transactions in the selected month.", "Subtracts likely recurring expenses still expected this month.", "Subtracts remaining protected budgets; unknown expenses are not predicted."])


def grocery_context(db: Session, user: UserProfile) -> GroceryBudgetContext:
    first = date.today().replace(day=1)
    groceries = db.scalar(select(FinanceCategory).where(FinanceCategory.user_id == user.id, func.lower(FinanceCategory.name) == "groceries"))
    budget = db.scalar(select(FinanceBudget).where(FinanceBudget.user_id == user.id, FinanceBudget.category_id == groceries.id, FinanceBudget.month_start == first, FinanceBudget.active.is_(True))) if groceries else None
    spent = _money(db.scalar(select(func.coalesce(func.sum(FinanceTransaction.amount), 0)).where(FinanceTransaction.user_id == user.id, FinanceTransaction.category_id == groceries.id, FinanceTransaction.direction == "expense", FinanceTransaction.occurred_on >= first)) or 0) if groceries else Decimal("0.00")
    remaining = max(Decimal("0.00"), budget.amount - spent) if budget else None
    safe = safe_to_spend(db, user)
    next_trip = min(remaining, safe.safe_to_spend) if remaining is not None else safe.safe_to_spend
    return GroceryBudgetContext(currency=budget.currency if budget else "EUR", monthly_budget=budget.amount if budget else None, spent_to_date=spent, remaining_budget=remaining, safe_next_trip_amount=max(Decimal("0.00"), next_trip), state="tight" if remaining is not None and remaining < Decimal("50") else "bounded" if budget else "unknown", confidence=0.9 if budget else 0.45)


def overview(db: Session, user: UserProfile, month_start: date | None = None) -> FinanceOverviewRead:
    first = (month_start or date.today()).replace(day=1)
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    rows = list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id, FinanceTransaction.occurred_on >= first, FinanceTransaction.occurred_on < end).order_by(FinanceTransaction.occurred_on.desc())).all())
    income = _money(sum((row.amount for row in rows if row.direction == "income"), Decimal("0")))
    spending = _money(sum((row.amount for row in rows if row.direction == "expense"), Decimal("0")))
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if row.direction != "expense": continue
        category = db.get(FinanceCategory, row.category_id) if row.category_id else None
        totals[category.name if category else "Uncategorized"] += row.amount
    goals = list(db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.domain == "finance", Goal.active.is_(True))).all())
    recurring = [RecurringExpenseRead.model_validate(row) for row in db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id).order_by(RecurringExpense.next_expected_on)).all()]
    return FinanceOverviewRead(month_start=first, currency="EUR", income=income, spending=spending, category_totals={key: _money(value) for key, value in totals.items()}, budgets=list_budgets(db, user, first), recurring_expenses=recurring, safe_to_spend=safe_to_spend(db, user, first), recent_transactions=[_transaction_read(db, row) for row in rows[:20]], savings_goals=[{"id": goal.id, "title": goal.title, "target_date": goal.target_date, "progress": goal.manual_progress} for goal in goals])
