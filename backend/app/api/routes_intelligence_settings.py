from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.embeddings import EmbeddingSettingsService
from app.intelligence_settings.schemas import (
    AgentModelSettingsUpdate,
    AgentProfileUpdate,
    AgentSettingsRead,
    EmbeddingConnectionTestRead,
    EmbeddingConnectionTestRequest,
    EmbeddingSettingsRead,
    EmbeddingSettingsUpdate,
    IntelligenceControlSurface,
    IntelligenceSettingsRead,
    IntelligenceSettingsUpdate,
    JevDecisionTestRead,
    OpenAIChatTestRead,
    ProviderCredentialWrite,
    ProviderCredentialWriteResult,
    ProviderModelsRead,
)
from app.intelligence_settings.service import IntelligenceSettingsService
from app.intelligence_settings.provider_models import ProviderModelCatalog
from app.intelligence_settings.provider_tests import ProviderCapabilityTestService


router = APIRouter(prefix="/settings/intelligence", tags=["intelligence-settings"])


@router.get("", response_model=IntelligenceControlSurface)
def intelligence_control_surface(
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = IntelligenceSettingsService(settings).control_surface(db, user)
    db.commit()
    return result


@router.patch("", response_model=IntelligenceSettingsRead)
def update_intelligence_settings(
    payload: IntelligenceSettingsUpdate, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = IntelligenceSettingsService(settings).update(db, user, payload)
    db.commit()
    return result


@router.put("/providers/{provider}/credential", response_model=ProviderCredentialWriteResult)
async def save_provider_credential(
    provider: str, request: Request, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    # Validate manually so FastAPI's validation response can never echo a submitted secret.
    try:
        payload = ProviderCredentialWrite.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(status_code=422, detail="The provider API key format is invalid.") from None

    def persist_credential() -> None:
        store = ProviderSecretStore()
        try:
            store.save(db, user, provider, payload.api_key.get_secret_value())
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(status_code=503, detail="Provider secret storage is temporarily unavailable.") from None

    await run_in_threadpool(persist_credential)
    return ProviderCredentialWriteResult(provider=provider, configured=True)


@router.delete("/providers/{provider}/credential", response_model=ProviderCredentialWriteResult)
def delete_provider_credential(
    provider: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
):
    store = ProviderSecretStore()
    try:
        store.delete(db, user, provider)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Provider secret storage is temporarily unavailable.") from None
    return ProviderCredentialWriteResult(provider=provider, configured=False)


@router.get("/providers/{provider}/models", response_model=ProviderModelsRead)
def provider_models(
    provider: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user),
):
    models = ProviderModelCatalog().list_models(db, user, provider)
    return ProviderModelsRead(provider=provider, models=models)


@router.post("/providers/openai/test", response_model=OpenAIChatTestRead)
def test_openai_chat_provider(
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    try:
        result = ProviderCapabilityTestService(settings).test_openai_chat(db, user)
        db.commit()
        return result
    except HTTPException:
        db.commit()
        raise


@router.post("/providers/jev/test", response_model=JevDecisionTestRead)
def test_jev_decision_provider(
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    try:
        result = ProviderCapabilityTestService(settings).test_jev_decision(db, user)
        db.commit()
        return result
    except HTTPException:
        db.commit()
        raise


@router.patch("/agents", response_model=list[AgentSettingsRead])
def update_agent_models(
    payload: AgentModelSettingsUpdate, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = IntelligenceSettingsService(settings).update_agent_models(db, user, payload)
    db.commit()
    return result


@router.patch("/agents/{skill_name}/profile", response_model=AgentSettingsRead)
async def update_agent_profile(
    skill_name: str, request: Request, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    try:
        payload = AgentProfileUpdate.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid agent profile. Use a single-line name, up to 1200 instruction characters, and no provider secrets.") from None

    def persist():
        result = IntelligenceSettingsService(settings).update_agent_profile(db, user, skill_name, payload)
        db.commit()
        return result
    return await run_in_threadpool(persist)


@router.get("/embeddings", response_model=EmbeddingSettingsRead)
def embedding_settings(
    db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = EmbeddingSettingsService(settings).read(db, user)
    db.commit()
    return result


@router.patch("/embeddings", response_model=EmbeddingSettingsRead)
def update_embedding_settings(
    payload: EmbeddingSettingsUpdate, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = EmbeddingSettingsService(settings).update(db, user, payload)
    db.commit()
    return result


@router.post("/embeddings/test", response_model=EmbeddingConnectionTestRead)
def test_embedding_provider(
    payload: EmbeddingConnectionTestRequest, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings),
):
    result = EmbeddingSettingsService(settings).test(db, user, payload)
    db.commit()
    return result
