from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, set_request_db_context
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.models import UserProfile
from app.database.session import SessionLocal, get_db
from app.realtime.schemas import RealtimeCatchup, RealtimeStateEvent
from app.realtime.service import RealtimeStateService


router = APIRouter(prefix="/realtime", tags=["realtime"])
logger = get_logger(__name__)


def _sse(event: RealtimeStateEvent) -> str:
    return f"id: {event.world_revision}\nevent: {event.event_kind.value}\ndata: {event.model_dump_json()}\n\n"


@router.get("/events", response_model=RealtimeCatchup)
def events_since(
    after_revision: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=10, le=2000),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RealtimeCatchup:
    return RealtimeStateService().changes_since(
        db,
        user,
        after_revision=after_revision,
        limit=limit or settings.realtime_history_limit,
    )


@router.get("/stream")
async def state_stream(
    request: Request,
    after_revision: int = Query(default=0, ge=0),
    once: bool = Query(default=False),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if not settings.realtime_state_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Realtime state is disabled.")
    cursor = after_revision
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    identity = {"id": user.id, "auth_subject": user.auth_subject, "email": user.email}
    service = RealtimeStateService()

    async def generate():
        nonlocal cursor
        logger.info("realtime_client_connected", extra={"user_id": identity["id"], "after_revision": cursor})
        heartbeat_counter = 0
        try:
            while True:
                if once:
                    catchup = service.changes_since(
                        db,
                        user,
                        after_revision=cursor,
                        limit=settings.realtime_history_limit,
                    )
                else:
                    with SessionLocal() as poll_db:
                        set_request_db_context(
                            poll_db,
                            auth_subject=identity["auth_subject"],
                            email=identity["email"],
                            user_id=identity["id"],
                        )
                        poll_user = poll_db.get(UserProfile, identity["id"])
                        if poll_user is None:
                            return
                        catchup = service.changes_since(
                            poll_db,
                            poll_user,
                            after_revision=cursor,
                            limit=settings.realtime_history_limit,
                        )
                if catchup.resync_required:
                    logger.warning("client_resync_required", extra={"user_id": identity["id"], "reason_code": catchup.reason_code})
                    yield _sse(service.resync_event(catchup.current_revision, catchup.reason_code or "revision_gap"))
                    cursor = catchup.current_revision
                elif catchup.events:
                    for event in catchup.events:
                        yield _sse(event)
                        cursor = event.world_revision
                else:
                    heartbeat_counter += 1
                    if once or heartbeat_counter >= 15:
                        yield _sse(service.heartbeat(catchup.current_revision))
                        heartbeat_counter = 0
                if once or await request.is_disconnected():
                    return
                await asyncio.sleep(settings.realtime_poll_seconds)
        finally:
            logger.info("realtime_client_disconnected", extra={"user_id": identity["id"], "last_revision": cursor})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
