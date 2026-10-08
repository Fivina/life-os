from sqlalchemy.orm import Session

from app.database.models import UserProfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select

from app.database.models import FinanceBudget, FinanceTransaction
from app.domains.finance.schemas import GroceryBudgetContext


def grocery_budget_context(db: Session, user: UserProfile) -> GroceryBudgetContext:
    from app.domains.finance.service import grocery_context

    return grocery_context(db, user)


@dataclass(frozen=True)
class SocialBudgetSignal:
    status: str
    amount_remaining: Decimal | None
    currency: str | None
    window: str
    source_ref: str | None


@dataclass(frozen=True)
class GroceryBudgetSignal:
    grocery_budget_remaining: Decimal | None
    currency: str | None
    budget_window: str
    status: str
    as_of: datetime
    source_ref: str | None


def grocery_budget_signal(db: Session, user: UserProfile) -> GroceryBudgetSignal:
    """Return only the grocery signal Chef needs, never Finance transaction history."""
    context = grocery_budget_context(db, user)
    status = {
        "tight": "LIMITED" if context.remaining_budget and context.remaining_budget > 0 else "EXHAUSTED",
        "bounded": "COMFORTABLE",
        "unknown": "UNKNOWN",
    }.get(context.state, "UNKNOWN")
    return GroceryBudgetSignal(
        grocery_budget_remaining=context.remaining_budget,
        currency=context.currency if context.remaining_budget is not None else None,
        budget_window="MONTH",
        status=status,
        as_of=datetime.now(UTC),
        source_ref=None,
    )


def discretionary_social_budget_remaining(db: Session, user: UserProfile) -> SocialBudgetSignal:
    """Expose one bounded signal; opportunity intelligence never receives transactions."""
    row = db.scalar(
        select(FinanceBudget)
        .where(
            FinanceBudget.user_id == user.id,
            FinanceBudget.active.is_(True),
            or_(FinanceBudget.name.ilike("%social%"), FinanceBudget.name.ilike("%leisure%")),
        )
        .order_by(FinanceBudget.month_start.desc())
        .limit(1)
    )
    if row is None:
        return SocialBudgetSignal("UNKNOWN", None, None, "MONTH", None)
    if row.category_id is None:
        return SocialBudgetSignal("UNKNOWN", None, row.currency, "MONTH", row.id)
    next_month = date(row.month_start.year + (1 if row.month_start.month == 12 else 0), 1 if row.month_start.month == 12 else row.month_start.month + 1, 1)
    spent = db.scalar(select(func.coalesce(func.sum(FinanceTransaction.amount), 0)).where(
        FinanceTransaction.user_id == user.id,
        FinanceTransaction.category_id == row.category_id,
        FinanceTransaction.direction == "expense",
        FinanceTransaction.currency == row.currency,
        FinanceTransaction.occurred_on >= row.month_start,
        FinanceTransaction.occurred_on < next_month,
    )) or Decimal("0")
    remaining = max(Decimal("0"), row.amount - Decimal(spent))
    return SocialBudgetSignal("CONSTRAINED" if row.protected or remaining <= 0 else "AVAILABLE", remaining, row.currency, "MONTH", row.id)
