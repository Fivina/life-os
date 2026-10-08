from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.communication.schemas import ComposeRequest, ComposedResponse, ResponseStreamEvent
from app.communication.service import ResponseCompositionService
from app.core.config import Settings, get_settings
from app.database.models import PlanProposal, UserProfile
from app.database.session import get_db


router = APIRouter(prefix="/communication", tags=["communication"])


def get_composition_service(settings: Settings = Depends(get_settings)) -> ResponseCompositionService:
    return ResponseCompositionService(settings)


def _response_sse(event: ResponseStreamEvent) -> str:
    return f"id: {event.sequence}\nevent: {event.event_type.value}\ndata: {event.model_dump_json()}\n\n"


@router.post("/compose", response_model=ComposedResponse)
def compose_response(
    payload: ComposeRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: ResponseCompositionService = Depends(get_composition_service),
):
    result = service.compose(db, user, payload)
    if result is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    db.commit()
    return result.model_copy(update={"world_revision": user.world_revision})


@router.post("/stream")
def stream_response(
    payload: ComposeRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: ResponseCompositionService = Depends(get_composition_service),
) -> StreamingResponse:
    return StreamingResponse(
        (_response_sse(event) for event in service.stream(db, user, payload)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/plan-proposals/{proposal_id}/compose", response_model=ComposedResponse)
def compose_plan_proposal(
    proposal_id: str,
    conversation_id: str | None = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: ResponseCompositionService = Depends(get_composition_service),
) -> ComposedResponse:
    proposal = db.get(PlanProposal, proposal_id)
    if proposal is None or proposal.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan proposal not found.")
    intent = service.intent_for_plan_proposal(proposal, conversation_ref=conversation_id)
    result = service.compose(db, user, ComposeRequest(intent=intent, persist_message=True))
    if result is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The proposal attention policy is silent.")
    db.commit()
    return result.model_copy(update={"world_revision": user.world_revision})
