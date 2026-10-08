from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CategoryRead(BaseModel):
    id: str
    name: str
    kind: str
    active: bool
    version: int
    model_config = {"from_attributes": True}


class TransactionRead(BaseModel):
    id: str
    occurred_on: date
    amount: Decimal
    currency: str
    direction: str
    merchant_raw: str | None
    merchant_name: str | None = None
    description: str | None
    category_name: str | None = None
    source: str
    external_id: str | None
    receipt_import_id: str | None
    import_batch_id: str | None
    version: int


class ManualTransactionCreate(BaseModel):
    occurred_on: date
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    merchant: str | None = Field(default=None, max_length=255)
    category: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=180)


class CsvImportCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=5_000_000)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    mapping: dict[str, str] = Field(default_factory=dict)


class ImportRowUpdate(BaseModel):
    occurred_on: date | None = None
    amount: Decimal | None = None
    direction: str | None = None
    merchant: str | None = None
    category: str | None = None
    description: str | None = None
    accept: bool = True


class ImportRowRead(BaseModel):
    id: str
    row_number: int
    occurred_on: date | None
    amount: Decimal | None
    currency: str
    direction: str | None
    merchant_raw: str | None
    merchant_name: str | None = None
    description: str | None
    category_name: str | None = None
    external_id: str | None
    confidence: float
    review_required: bool
    status: str
    error: str | None
    raw_json: dict
    version: int


class ImportBatchRead(BaseModel):
    id: str
    filename: str
    status: str
    currency: str
    mapping_json: dict
    row_count: int
    ready_count: int
    review_count: int
    duplicate_count: int
    error_count: int
    confirmed_at: datetime | None
    rows: list[ImportRowRead] = Field(default_factory=list)
    version: int


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0)
    category: str | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    month_start: date
    protected: bool = False

    @field_validator("month_start")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        return value.replace(day=1)


class BudgetRead(BaseModel):
    id: str
    name: str
    category_name: str | None = None
    amount: Decimal
    spent: Decimal
    remaining: Decimal
    currency: str
    month_start: date
    protected: bool
    active: bool
    version: int


class RecurringExpenseRead(BaseModel):
    id: str
    name: str
    typical_amount: Decimal
    currency: str
    interval_days: int
    next_expected_on: date | None
    confidence: float
    evidence_count: int
    status: str
    version: int
    model_config = {"from_attributes": True}


class SafeToSpendRead(BaseModel):
    currency: str
    income_to_date: Decimal
    spending_to_date: Decimal
    upcoming_recurring: Decimal
    protected_budget_remaining: Decimal
    planned_savings: Decimal
    safe_to_spend: Decimal
    assumptions: list[str]


class GroceryBudgetContext(BaseModel):
    currency: str
    monthly_budget: Decimal | None
    spent_to_date: Decimal
    remaining_budget: Decimal | None
    safe_next_trip_amount: Decimal
    state: str
    confidence: float


class FinanceOverviewRead(BaseModel):
    month_start: date
    currency: str
    income: Decimal
    spending: Decimal
    category_totals: dict[str, Decimal]
    budgets: list[BudgetRead]
    recurring_expenses: list[RecurringExpenseRead]
    safe_to_spend: SafeToSpendRead
    recent_transactions: list[TransactionRead]
    savings_goals: list[dict]
