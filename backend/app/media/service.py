from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.types import AIImageRequest, AIProviderError
from app.core.config import Settings
from app.database.models import MediaAsset, UserProfile
from app.events.service import append_event
from app.media.schemas import MediaAssetRead, MediaGenerateRequest, MediaUploadCreate

ALLOWED_UPLOADS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _decode(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The upload is not valid base64 data.") from exc


def _validate_image(data: bytes, mime_type: str) -> None:
    valid = (
        mime_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff")
        or mime_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")
        or mime_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    )
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The file content does not match its declared image type.")


def _storage_target(settings: Settings, user: UserProfile, kind: str, digest: str, suffix: str) -> tuple[Path, str]:
    root = Path(settings.media_storage_path).resolve()
    relative = Path(user.id) / kind / f"{digest}{suffix}"
    target = (root / relative).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid media storage target.")
    return target, relative.as_posix()


def store_bytes(
    db: Session,
    user: UserProfile,
    settings: Settings,
    *,
    kind: str,
    mime_type: str,
    data: bytes,
    source: str,
    linked_entity_type: str | None = None,
    linked_entity_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    generation_version: str | None = None,
    metadata_json: dict | None = None,
) -> MediaAssetRead:
    if mime_type not in ALLOWED_UPLOADS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG, PNG, and WebP images are accepted.")
    if not data or len(data) > settings.media_max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The media file exceeds the configured upload limit.")
    _validate_image(data, mime_type)
    digest = sha256(data).hexdigest()
    existing = db.scalar(
        select(MediaAsset).where(
            MediaAsset.user_id == user.id,
            MediaAsset.kind == kind,
            MediaAsset.content_hash == digest,
            MediaAsset.deleted_at.is_(None),
        )
    )
    if existing is not None:
        existing.last_used_at = datetime.now(UTC)
        return MediaAssetRead.model_validate(existing)
    target, storage_key = _storage_target(settings, user, kind, digest, ALLOWED_UPLOADS[mime_type])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)
    row = MediaAsset(
        user_id=user.id,
        kind=kind,
        storage_provider=settings.media_storage_provider,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(data),
        content_hash=digest,
        source=source,
        provider=provider,
        model=model,
        generation_version=generation_version,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        metadata_json=metadata_json or {},
        last_used_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return MediaAssetRead.model_validate(row)


def upload(db: Session, user: UserProfile, settings: Settings, payload: MediaUploadCreate) -> MediaAssetRead:
    result = store_bytes(
        db,
        user,
        settings,
        kind=payload.kind,
        mime_type=payload.mime_type,
        data=_decode(payload.content_base64),
        source="upload",
        linked_entity_type=payload.linked_entity_type,
        linked_entity_id=payload.linked_entity_id,
        metadata_json={**payload.metadata_json, "original_filename": Path(payload.filename).name},
    )
    append_event(
        db,
        user,
        event_type="media.uploaded",
        aggregate_type="media_asset",
        aggregate_id=result.id,
        payload={"asset_id": result.id, "kind": result.kind, "content_hash": result.content_hash},
        outbox=False,
        increment_world_revision=False,
    )
    return result


def get_asset(db: Session, user: UserProfile, asset_id: str) -> MediaAsset:
    row = db.scalar(select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.user_id == user.id, MediaAsset.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found.")
    return row


def local_path(db: Session, user: UserProfile, settings: Settings, asset_id: str) -> Path:
    row = get_asset(db, user, asset_id)
    root = Path(settings.media_storage_path).resolve()
    target = (root / row.storage_key).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file is unavailable.")
    row.last_used_at = datetime.now(UTC)
    return target


def generate(db: Session, user: UserProfile, settings: Settings, payload: MediaGenerateRequest, gateway: AIGateway | None = None) -> MediaAssetRead | None:
    cached = db.scalar(
        select(MediaAsset).where(
            MediaAsset.user_id == user.id,
            MediaAsset.kind == payload.kind,
            MediaAsset.linked_entity_type == payload.linked_entity_type,
            MediaAsset.linked_entity_id == payload.linked_entity_id,
            MediaAsset.generation_version == payload.generation_version,
            MediaAsset.deleted_at.is_(None),
        )
    )
    if cached is not None:
        cached.last_used_at = datetime.now(UTC)
        return MediaAssetRead.model_validate(cached)
    try:
        response = (gateway or AIGateway(settings)).generate_image(
            db,
            user,
            request_id=f"media:{payload.linked_entity_type}:{payload.linked_entity_id}:{payload.generation_version}",
            assistant_role="MEDIA_SERVICE",
            skill_name="media-generation",
            skill_version="1.5",
            request=AIImageRequest(prompt=payload.prompt, aspect_ratio=payload.aspect_ratio),
            optional=True,
        )
        return store_bytes(
            db,
            user,
            settings,
            kind=payload.kind,
            mime_type=response.mime_type,
            data=_decode(response.data_base64),
            source="generated",
            linked_entity_type=payload.linked_entity_type,
            linked_entity_id=payload.linked_entity_id,
            provider=response.provider,
            model=response.model,
            generation_version=payload.generation_version,
            metadata_json={"prompt_version": payload.generation_version},
        )
    except AIProviderError:
        return None
