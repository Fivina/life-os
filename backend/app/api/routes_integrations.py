from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.integrations.schemas import CredentialWrite, CredentialResult, ConnectionTestResult, IntegrationList
from app.integrations.service import IntegrationService


router = APIRouter(prefix="/settings/integrations", tags=["integrations"])


def _transaction(db, action):
    try:
        result = action()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Integration storage is temporarily unavailable.") from None


@router.get("", response_model=IntegrationList)
def list_integrations(scope: str = "tenant", db: Session = Depends(get_db),
                      user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return _transaction(db, lambda: IntegrationService(settings).list(db, user, scope))


@router.put("/{provider}/credentials", response_model=CredentialResult)
async def save_credentials(provider: str, request: Request, db: Session = Depends(get_db),
                           user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    # Manual parsing prevents FastAPI/Pydantic errors from reflecting submitted secrets.
    try:
        payload = CredentialWrite.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(422, "Invalid integration credential request.") from None
    return await run_in_threadpool(_transaction, db, lambda: IntegrationService(settings).save(db, user, provider, payload))


@router.delete("/{provider}/credentials", response_model=CredentialResult)
def delete_credentials(provider: str, scope: str = "tenant", db: Session = Depends(get_db),
                       user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return _transaction(db, lambda: IntegrationService(settings).delete(db, user, provider, scope))


@router.post("/{provider}/test", response_model=ConnectionTestResult)
def test_connection(provider: str, scope: str = "tenant", db: Session = Depends(get_db),
                    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return _transaction(db, lambda: IntegrationService(settings).test(db, user, provider, scope))
