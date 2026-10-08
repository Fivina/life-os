from __future__ import annotations

from app.assistant.schemas import AssistantRole, ModelTier
from app.database.models import AIActionAudit, UserProfile
from sqlalchemy.orm import Session


def record_ai_audit(
    db: Session,
    user: UserProfile,
    *,
    assistant_role: AssistantRole,
    request_id: str,
    provider: str | None,
    model: str | None,
    model_tier: ModelTier,
    status: str,
    tool_name: str | None = None,
    proposal_id: str | None = None,
    mutation_id: str | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
    metadata: dict | None = None,
) -> AIActionAudit:
    audit = AIActionAudit(
        user_id=user.id,
        assistant_role=assistant_role,
        request_id=request_id,
        provider=provider or "none",
        model=model,
        model_tier=model_tier.value,
        tool_name=tool_name,
        proposal_id=proposal_id,
        mutation_id=mutation_id,
        status=status,
        error_code=error_code,
        duration_ms=duration_ms,
        metadata_json=metadata or {},
    )
    db.add(audit)
    db.flush()
    return audit
