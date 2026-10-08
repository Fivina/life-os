from __future__ import annotations

import re

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.core.logging import get_logger
from app.ai.types import AICapability, AIMessage, AIProviderError, AIRequest
from app.database.models import ConversationThread, UserProfile
from app.memory.schemas import MemoryExtraction
from app.memory.service import MemoryService


MEMORY_SIGNAL = re.compile(
    r"\b(remember|i (?:really )?(?:like|love|prefer|dislike|hate)|i (?:do not|don't) like|i always|i never|please always|please never|keep (?:answers|responses)|don't ask|do not ask)\b",
    re.IGNORECASE,
)
logger = get_logger(__name__)


class MemoryCurator:
    def __init__(self, gateway: AIGateway, memories: MemoryService):
        self.gateway = gateway
        self.memories = memories

    def should_inspect(self, message: str) -> bool:
        return bool(MEMORY_SIGNAL.search(message))

    def capture(
        self,
        db: Session,
        user: UserProfile,
        thread: ConversationThread | None,
        *,
        message_id: str,
        message: str,
        request_id: str,
        source_type: str = "conversation_message",
        source_kind: str | None = None,
    ) -> list[str]:
        if not self.should_inspect(message):
            return []
        try:
            response = self.gateway.complete(
                db,
                user,
                request_id=request_id,
                assistant_role="MEMORY_SYSTEM",
                skill_name="memory-curator",
                skill_version="1.0.0",
                capability=AICapability.economy,
                conversation_thread_id=thread.id if thread is not None else None,
                optional=True,
                request=AIRequest(
                    system_instruction=(
                        "Extract only durable personal preferences, routines, interaction preferences, and stable personal facts. "
                        "Exclude current tasks, calendar facts, plans, transient mood/state, medical inference, and canonical Life OS state. "
                        "Use a subject-level normalized_key so opposite preferences share a key. Never mark anything pinned."
                    ),
                    messages=[AIMessage(role="user", content=message)],
                    response_schema=MemoryExtraction.model_json_schema(),
                    temperature=0.0,
                    metadata={"mode": "memory_extraction"},
                ),
            )
            extraction = MemoryExtraction.model_validate_json(response.text or "{}")
        except (AIProviderError, ValidationError):
            return []
        captured: list[str] = []
        for candidate in extraction.candidates:
            try:
                memory = self.memories.remember(
                    db,
                    user,
                    candidate,
                    source_type=source_type,
                    source_id=message_id,
                    source_kind=source_kind or ("explicit_user" if candidate.explicit else "conversation_inference"),
                    evidence_kind="user_statement" if candidate.explicit else "conversation",
                    user_confirmed=candidate.explicit,
                    request_id=request_id,
                )
                captured.append(memory.id)
            except Exception as exc:
                from fastapi import HTTPException

                if isinstance(exc, HTTPException):
                    logger.warning(
                        "Memory candidate was rejected without affecting the assistant request",
                        extra={"user_id": user.id, "request_id": request_id, "error_type": type(exc).__name__},
                    )
                    continue
                raise
        return captured
