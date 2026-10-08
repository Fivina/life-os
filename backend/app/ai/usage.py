from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.routing import AIBudgetState
from app.ai.types import AICapability, AIUsageMetadata
from app.core.config import Settings
from app.database.models import AIActionAudit, UserIntelligenceSettings, UserProfile


class AIUsageService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def estimate_cost(self, *, model: str, usage: AIUsageMetadata) -> tuple[float, bool]:
        try:
            pricing = json.loads(self.settings.ai_model_pricing_json or "{}")
        except json.JSONDecodeError:
            pricing = {}
        rates = pricing.get(model) or {}
        if not rates:
            return 0.0, True
        input_rate = float(rates.get("input_per_million_eur", 0))
        output_rate = float(rates.get("output_per_million_eur", 0))
        cached_rate = float(rates.get("cached_input_per_million_eur", input_rate))
        uncached_input = max(0, usage.input_tokens - usage.cached_tokens)
        cost = (uncached_input * input_rate + usage.cached_tokens * cached_rate + usage.output_tokens * output_rate) / 1_000_000
        return round(cost, 8), usage.estimated

    def record(
        self,
        db: Session,
        user: UserProfile,
        *,
        request_id: str,
        assistant_role: str,
        provider: str,
        model: str | None,
        capability: AICapability,
        skill_name: str,
        skill_version: str,
        prompt_version: str,
        status: str,
        usage: AIUsageMetadata | None = None,
        conversation_thread_id: str | None = None,
        tool_call_count: int = 0,
        latency_ms: int | None = None,
        error_category: str | None = None,
    ) -> AIActionAudit:
        usage = usage or AIUsageMetadata(estimated=True)
        cost, estimated = self.estimate_cost(model=model or "", usage=usage)
        audit = AIActionAudit(
            user_id=user.id,
            assistant_role=assistant_role,
            request_id=request_id,
            provider=provider,
            model=model,
            model_tier=capability.value,
            capability=capability.value,
            skill_name=skill_name,
            skill_version=skill_version,
            prompt_version=prompt_version,
            conversation_thread_id=conversation_thread_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cached_tokens,
            tool_call_count=tool_call_count,
            estimated_cost=cost,
            cost_estimated=estimated,
            status=status,
            error_code=error_category,
            error_category=error_category,
            duration_ms=latency_ms,
            metadata_json={"usage_estimated": usage.estimated, "finish_total_tokens": usage.total_tokens},
        )
        db.add(audit)
        db.flush()
        return audit

    def current_month_total(self, db: Session, user_id: str) -> float:
        now = datetime.now(UTC)
        month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        value = db.scalar(select(func.coalesce(func.sum(AIActionAudit.estimated_cost), 0.0)).where(
            AIActionAudit.user_id == user_id,
            AIActionAudit.created_at >= month_start,
        ))
        return float(value or 0)

    def grouped(self, db: Session, user_id: str, field: str) -> dict[str, float]:
        column = getattr(AIActionAudit, field)
        rows = db.execute(select(column, func.coalesce(func.sum(AIActionAudit.estimated_cost), 0.0)).where(
            AIActionAudit.user_id == user_id,
        ).group_by(column)).all()
        return {str(key or "unknown"): float(value or 0) for key, value in rows}

    def by_skill(self, db: Session, user_id: str) -> dict[str, float]:
        return self.grouped(db, user_id, "skill_name")

    def by_model(self, db: Session, user_id: str) -> dict[str, float]:
        return self.grouped(db, user_id, "model")

    def by_capability(self, db: Session, user_id: str) -> dict[str, float]:
        return self.grouped(db, user_id, "capability")

    def by_provider(self, db: Session, user_id: str) -> dict[str, float]:
        return self.grouped(db, user_id, "provider")

    def budget_state(self, db: Session, user_id: str) -> AIBudgetState:
        spend = self.current_month_total(db, user_id)
        user_settings = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user_id))
        budget = (
            float(user_settings.monthly_ai_budget_eur)
            if user_settings is not None and user_settings.monthly_ai_budget_eur is not None
            else self.settings.ai_monthly_budget_eur
        )
        if user_settings is not None and user_settings.monthly_ai_budget_eur is not None:
            warning_threshold = budget * 0.80
            economy_threshold = budget * 0.90
            restrict_threshold = budget
        else:
            warning_threshold = self.settings.ai_warning_threshold_eur
            economy_threshold = self.settings.ai_economy_threshold_eur
            restrict_threshold = self.settings.ai_restrict_optional_threshold_eur
        return AIBudgetState(
            monthly_spend_eur=spend,
            budget_eur=budget,
            warning=spend >= warning_threshold,
            economy_only=spend >= economy_threshold,
            optional_suppressed=spend >= restrict_threshold,
        )
