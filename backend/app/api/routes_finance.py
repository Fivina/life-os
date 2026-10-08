from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.finance import service
from app.domains.finance.schemas import BudgetCreate, BudgetRead, CsvImportCreate, FinanceOverviewRead, GroceryBudgetContext, ImportBatchRead, ImportRowUpdate, RecurringExpenseRead, TransactionRead

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/overview", response_model=FinanceOverviewRead)
def finance_overview(month_start: date | None = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.overview(db, user, month_start)


@router.get("/transactions", response_model=list[TransactionRead])
def finance_transactions(limit: int = 100, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_transactions(db, user, min(500, max(1, limit)))


@router.post("/imports", response_model=ImportBatchRead)
def create_import(payload: CsvImportCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.create_csv_import(db, user, payload)
    db.commit()
    return result


@router.get("/imports/{batch_id}", response_model=ImportBatchRead)
def get_import(batch_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_import(db, user, batch_id)


@router.patch("/imports/rows/{row_id}", response_model=ImportBatchRead)
def update_import_row(row_id: str, payload: ImportRowUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.update_import_row(db, user, row_id, payload)
    db.commit()
    return result


@router.post("/imports/{batch_id}/confirm", response_model=ImportBatchRead)
def confirm_import(batch_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.confirm_import(db, user, batch_id)
    db.commit()
    return result


@router.post("/budgets", response_model=BudgetRead)
def save_budget(payload: BudgetCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.create_budget(db, user, payload)
    db.commit()
    return result


@router.get("/grocery-budget", response_model=GroceryBudgetContext)
def grocery_budget(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.grocery_context(db, user)


@router.post("/recurring/refresh", response_model=list[RecurringExpenseRead])
def refresh_recurring(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.refresh_recurring(db, user)
    db.commit()
    return result
