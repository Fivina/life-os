from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Event as ThreadEvent

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.activity import activity_sink
from app.api.deps import set_request_db_context
from app.database.models import UserProfile


async def stream_message(service, bind, user_id: str, payload, *, auth_subject: str | None = None, email: str | None = None) -> AsyncIterator[str]:
    """Stream actual host activity around the existing transactional assistant service."""
    import json

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=68)
    stopped = ThreadEvent()

    def publish(event: dict) -> None:
        if not stopped.is_set():
            loop.call_soon_threadsafe(queue.put_nowait, event)

    def run() -> None:
        # The request Session is never shared with the worker thread.
        with Session(bind=bind, expire_on_commit=False) as db:
            def on_activity(activity) -> None:
                if stopped.is_set():
                    raise RuntimeError("Assistant stream disconnected")
                publish({"event_type": "activity", "activity": activity.model_dump(mode="json")})
            token = activity_sink.set(on_activity)
            try:
                set_request_db_context(db, user_id=user_id, auth_subject=auth_subject, email=email)
                user = db.get(UserProfile, user_id)
                if user is None:
                    raise HTTPException(status_code=401, detail="User unavailable")
                response = service.handle_message(db, user, payload)
                if stopped.is_set():
                    db.rollback()
                    return
                db.commit()
                publish({"event_type": "complete", "response": response.model_dump(mode="json")})
            except Exception:
                db.rollback()
                publish({"event_type": "error", "error_code": "assistant_stream_failed"})
            finally:
                activity_sink.reset(token)

    yield 'event: start\ndata: {"event_type":"start"}\n\n'
    task = asyncio.create_task(asyncio.to_thread(run))
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            yield f"event: {event['event_type']}\ndata: {json.dumps(event, ensure_ascii=True)}\n\n"
            if event["event_type"] in {"complete", "error"}:
                break
        await task
    finally:
        stopped.set()
        # Cancellation cannot kill a provider HTTP request; it remains timeout-bounded.
        if not task.done():
            task.add_done_callback(lambda finished: finished.exception() if not finished.cancelled() else None)
