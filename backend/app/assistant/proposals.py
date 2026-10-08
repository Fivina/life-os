from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.schemas import AssistantActionProposalRead, AssistantRole
from app.assistant.tools import ToolDefinition
from app.conversations.schemas import ConversationMessageRead
from app.database.models import AssistantActionProposal, ConversationMessage, UserProfile


PROPOSAL_TTL_MINUTES = 15


def create_action_proposal(
    db: Session, user: UserProfile, *, role: AssistantRole, tool: ToolDefinition,
    args: BaseModel, summary: str | None = None,
) -> AssistantActionProposal:
    proposal = AssistantActionProposal(
        user_id=user.id,
        assistant_role=role,
        tool_name=tool.name,
        arguments_json=args.model_dump(mode="json", exclude_none=True),
        summary=summary or f"Run {tool.name}",
        consequence_category="consequential",
        expected_world_revision=user.world_revision,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=PROPOSAL_TTL_MINUTES),
        confirmation_required=True,
        idempotency_key=f"assistant-proposal:{uuid4()}",
    )
    db.add(proposal)
    db.flush()
    return proposal


def proposal_read(proposal: AssistantActionProposal, *, thread_id: str | None = None) -> AssistantActionProposalRead:
    expiry = proposal.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return AssistantActionProposalRead(
        id=proposal.id, tool_name=proposal.tool_name, arguments=proposal.arguments_json,
        summary=proposal.summary, consequence_category=proposal.consequence_category,
        expected_world_revision=proposal.expected_world_revision, status=proposal.status,
        expires_at=expiry, confirmation_required=proposal.confirmation_required,
        version=proposal.version,
        thread_id=thread_id,
    )


def restore_message_proposals(
    db: Session, user: UserProfile, messages: list[ConversationMessage],
) -> list[ConversationMessageRead]:
    """Project current proposal state into saved messages without applying actions."""
    proposal_ids = {
        proposal_id for message in messages
        if message.user_id == user.id and message.role == "assistant"
        and isinstance(proposal_id := (message.metadata_json or {}).get("proposal_id"), str)
    }
    proposals = {} if not proposal_ids else {
        proposal.id: proposal for proposal in db.scalars(select(AssistantActionProposal).where(
            AssistantActionProposal.user_id == user.id,
            AssistantActionProposal.id.in_(proposal_ids),
        ))
    }
    now = datetime.now(UTC)
    restored = []
    for message in messages:
        read = ConversationMessageRead.model_validate(message)
        metadata = dict(read.metadata_json)
        metadata.pop("proposed_action", None)
        proposal_id = metadata.get("proposal_id")
        proposal = proposals.get(proposal_id) if (
            message.user_id == user.id and message.role == "assistant" and isinstance(proposal_id, str)
        ) else None
        if proposal is not None:
            action = proposal_read(proposal)
            expiry = proposal.expires_at
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if action.status == "pending" and expiry < now:
                action = action.model_copy(update={"status": "expired"})
            metadata["proposed_action"] = action.model_copy(update={"thread_id": message.thread_id}).model_dump(mode="json")
        restored.append(read.model_copy(update={"metadata_json": metadata}))
    return restored
