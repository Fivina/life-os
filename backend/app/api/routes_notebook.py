from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import UserProfile
from app.database.session import get_db
from app.notebook.schemas import NotebookEntryCreate, NotebookEntryRead, NotebookEntryUpdate, NotebookPromotionRead, NotebookPromotionRequest, NotebookSearchResult
from app.notebook import service


router = APIRouter(prefix="/notebook", tags=["notebook"])


@router.post("", response_model=NotebookEntryRead)
def create(payload: NotebookEntryCreate, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
           db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.create_entry(db, user, payload, idempotency_key=idempotency_key); db.commit(); return row


@router.get("", response_model=list[NotebookEntryRead])
def list_all(entry_type: str | None = None, status: str | None = None, limit: int = Query(100, ge=1, le=200),
             db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_entries(db, user, entry_type=entry_type, status_filter=status, limit=limit)


@router.get("/search", response_model=list[NotebookSearchResult])
def search(q: str = Query(min_length=1, max_length=500), limit: int = Query(20, ge=1, le=50),
           db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.search_entries(db, user, q, limit=limit)


@router.get("/{entry_id}", response_model=NotebookEntryRead)
def get(entry_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_entry(db, user, entry_id)


@router.patch("/{entry_id}", response_model=NotebookEntryRead)
def update(entry_id: str, payload: NotebookEntryUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.update_entry(db, user, entry_id, payload); db.commit(); return row


@router.post("/{entry_id}/review", response_model=NotebookEntryRead)
def review(entry_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.review_entry(db, user, entry_id); db.commit(); return row


@router.post("/{entry_id}/archive", response_model=NotebookEntryRead)
def archive(entry_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    row = service.archive_entry(db, user, entry_id); db.commit(); return row


@router.post("/{entry_id}/promote", response_model=NotebookPromotionRead)
def promote(entry_id: str, payload: NotebookPromotionRequest,
            idempotency_key: Annotated[str, Header(alias="Idempotency-Key")], db: Session = Depends(get_db),
            user: UserProfile = Depends(get_current_user)):
    _, promotion = service.promote_entry(db, user, entry_id, payload, idempotency_key=idempotency_key); db.commit(); return promotion
