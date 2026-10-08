from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.kitchen import receipts
from app.domains.kitchen.receipt_schemas import ReceiptImportRead, ReceiptReviewUpdate, ReceiptUploadCreate

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("", response_model=ReceiptImportRead)
def create_receipt(payload: ReceiptUploadCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    result = receipts.create_import(db, user, settings, payload)
    db.commit()
    return result


@router.get("", response_model=list[ReceiptImportRead])
def list_receipts(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return receipts.list_imports(db, user)


@router.get("/{receipt_id}", response_model=ReceiptImportRead)
def get_receipt(receipt_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return receipts.get_import(db, user, receipt_id)


@router.post("/{receipt_id}/process", response_model=ReceiptImportRead)
def process_receipt(receipt_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    result = receipts.process_import(db, user, settings, receipt_id)
    db.commit()
    return result


@router.patch("/{receipt_id}", response_model=ReceiptImportRead)
def review_receipt(receipt_id: str, payload: ReceiptReviewUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = receipts.update_review(db, user, receipt_id, payload)
    db.commit()
    return result


@router.post("/{receipt_id}/confirm", response_model=ReceiptImportRead)
def confirm_receipt(receipt_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = receipts.confirm_import(db, user, receipt_id)
    db.commit()
    return result
