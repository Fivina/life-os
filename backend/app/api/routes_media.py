from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.media import service
from app.media.schemas import MediaAssetRead, MediaGenerateRequest, MediaUploadCreate

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=MediaAssetRead)
def upload_media(payload: MediaUploadCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    result = service.upload(db, user, settings, payload)
    db.commit()
    return result


@router.post("/generate", response_model=MediaAssetRead | None)
def generate_media(payload: MediaGenerateRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    result = service.generate(db, user, settings, payload)
    db.commit()
    return result


@router.get("/{asset_id}/content")
def media_content(asset_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    row = service.get_asset(db, user, asset_id)
    path = service.local_path(db, user, settings, asset_id)
    db.commit()
    return FileResponse(path, media_type=row.mime_type, filename=f"{row.kind}{path.suffix}")
