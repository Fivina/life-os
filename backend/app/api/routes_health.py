from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "life-os-backend",
        "version": settings.deployment_version,
        "environment": settings.app_env,
    }


@router.get("/status")
def runtime_status(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    provider_ready = settings.ai_provider == "fake" or bool(settings.gemini_api_key)
    return {
        "status": "ok",
        "version": settings.deployment_version,
        "ai": {
            "enabled": settings.ai_enabled,
            "provider": settings.ai_provider,
            "capabilities": {
                "text": {"configured": provider_ready, "model": settings.ai_model_fast},
                "embedding": {"configured": provider_ready, "model": settings.ai_model_embedding},
                "vision": {"configured": provider_ready, "model": settings.ai_model_vision},
                "image": {"configured": provider_ready, "model": settings.ai_model_image},
            },
        },
        "media": {"provider": settings.media_storage_provider, "max_upload_bytes": settings.media_max_upload_bytes},
        "finance": {"default_currency": settings.finance_default_currency},
    }


@router.get("/readiness", status_code=status.HTTP_200_OK)
def readiness(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    db.execute(text("select 1"))
    auth_ready = settings.development_auth_enabled or bool(settings.supabase_jwt_secret)
    return {
        "status": "ready" if auth_ready else "degraded",
        "database": "reachable",
        "auth": "configured" if auth_ready else "missing",
        "environment": settings.app_env,
    }
