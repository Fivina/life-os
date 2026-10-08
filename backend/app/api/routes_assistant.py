from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import UTC, datetime

from app.ai.usage import AIUsageService
from app.api.deps import get_current_user
from app.assistant.schemas import AssistantActionProposalRead, AssistantMessageRequest, AssistantResponse
from app.assistant.proposals import proposal_read, restore_message_proposals
from app.assistant.service import AssistantService
from app.assistant.streaming import stream_message
from app.conversations.schemas import (
    ConversationThreadCreate,
    ConversationThreadDetail,
    ConversationThreadRead,
)
from app.core.config import Settings, get_settings
from app.database.models import AssistantActionProposal, ConversationMessage, UserProfile
from app.database.session import get_db
from app.skills.registry import SkillConfigurationError

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/proposals/pending", response_model=list[AssistantActionProposalRead])
def pending_action_proposals(
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
) -> list[AssistantActionProposalRead]:
    """The user's current approval cards; reading never executes an action."""
    now = datetime.now(UTC)
    rows = db.scalars(select(AssistantActionProposal).where(
        AssistantActionProposal.user_id == user.id,
        AssistantActionProposal.status == "pending",
    ).order_by(AssistantActionProposal.created_at.desc()).limit(30)).all()
    proposals = [proposal_read(row, thread_id=db.scalar(select(ConversationMessage.thread_id).where(
        ConversationMessage.user_id == user.id,
        ConversationMessage.role == "assistant",
        ConversationMessage.metadata_json["proposal_id"].as_string() == row.id,
    ).order_by(ConversationMessage.created_at.desc()).limit(1))) for row in rows]
    return [proposal for proposal in proposals if proposal.expires_at > now][:10]


def get_assistant_service(settings: Settings = Depends(get_settings)) -> AssistantService:
    return AssistantService(settings)


@router.get("/threads", response_model=list[ConversationThreadRead])
def list_conversation_threads(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> list[ConversationThreadRead]:
    return [ConversationThreadRead.model_validate(row) for row in service.conversations.list_threads(db, user, limit=limit)]


@router.post("/threads", response_model=ConversationThreadRead)
def create_conversation_thread(
    payload: ConversationThreadCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> ConversationThreadRead:
    try:
        service.skills.get(payload.default_skill)
    except SkillConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    thread = service.conversations.create_thread(db, user, title=payload.title, default_skill=payload.default_skill)
    db.commit()
    db.refresh(thread)
    return ConversationThreadRead.model_validate(thread)


@router.get("/threads/{thread_id}", response_model=ConversationThreadDetail)
def get_conversation_thread(
    thread_id: str,
    message_limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> ConversationThreadDetail:
    thread = service.conversations.get_thread(db, user, thread_id)
    messages = service.conversations.messages(db, user, thread_id, limit=message_limit)
    summary = service.conversations.get_summary(db, user, thread_id)
    return ConversationThreadDetail(
        **ConversationThreadRead.model_validate(thread).model_dump(),
        messages=restore_message_proposals(db, user, messages),
        summary=summary,
    )


@router.post("/threads/{thread_id}/archive", response_model=ConversationThreadRead)
def archive_conversation_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> ConversationThreadRead:
    thread = service.conversations.archive(db, user, thread_id)
    db.commit()
    db.refresh(thread)
    return ConversationThreadRead.model_validate(thread)


@router.get("/usage")
def assistant_usage(
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    usage = AIUsageService(settings)
    budget = usage.budget_state(db, user.id)
    return {
        "monthly_spend_eur": budget.monthly_spend_eur,
        "budget_eur": budget.budget_eur,
        "warning": budget.warning,
        "economy_only": budget.economy_only,
        "optional_suppressed": budget.optional_suppressed,
        "by_provider": usage.by_provider(db, user.id),
        "by_model": usage.by_model(db, user.id),
        "by_capability": usage.by_capability(db, user.id),
        "by_skill": usage.by_skill(db, user.id),
    }


@router.get("/provider-status")
def assistant_provider_status(
    settings: Settings = Depends(get_settings),
    _user: UserProfile = Depends(get_current_user),
) -> dict:
    provider = settings.ai_provider.lower()
    return {
        "enabled": settings.ai_enabled,
        "provider": provider,
        "configured": provider == "fake" or bool(settings.gemini_api_key),
        "models": {
            "economy": settings.ai_model_economy,
            "fast": settings.ai_model_fast,
            "reasoning": settings.ai_model_reasoning,
            "embedding": settings.ai_model_embedding,
        },
    }


@router.post("/message", response_model=AssistantResponse)
def assistant_message(
    payload: AssistantMessageRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    response = service.handle_message(db, user, payload)
    db.commit()
    return response


@router.post("/message/stream")
def assistant_message_stream(
    payload: AssistantMessageRequest, db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user), service: AssistantService = Depends(get_assistant_service),
) -> StreamingResponse:
    if payload.thread_id:
        service.conversations.get_thread(db, user, payload.thread_id, include_archived=False)
    user_id = user.id
    auth_subject, email = user.auth_subject, user.email
    bind = db.get_bind()
    # Authentication can provision a first-use user; make it visible to the isolated worker.
    db.commit()
    return StreamingResponse(
        stream_message(service, bind, user_id, payload, auth_subject=auth_subject, email=email), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/proposals/{proposal_id}/confirm", response_model=AssistantResponse)
def confirm_assistant_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    response = service.confirm_proposal(db, user, proposal_id)
    db.commit()
    return response


@router.post("/proposals/{proposal_id}/cancel", response_model=AssistantResponse)
def cancel_assistant_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    response = service.cancel_proposal(db, user, proposal_id)
    db.commit()
    return response
