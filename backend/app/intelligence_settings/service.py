from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.usage import AIUsageService
from app.agents.catalog import DEFAULT_AGENT_MODELS, default_model
from app.agents.profiles import agent_profile
from app.assistant.tools import ToolRegistry
from app.core.config import Settings
from app.database.models import ConversationThread, MemoryItem, PatternEvidence, UserIntelligenceSettings, UserProfile
from app.events.service import append_event
from app.intelligence_settings.provider_credentials import ProviderSecretStore
from app.intelligence_settings.schemas import AgentModelSettingsUpdate, AgentProfileUpdate, AgentSettingsRead, IntelligenceControlSurface, IntelligenceSettingsRead, IntelligenceSettingsUpdate
from app.skills.registry import SkillRegistry


def _read(row: UserIntelligenceSettings) -> IntelligenceSettingsRead:
    return IntelligenceSettingsRead(
        schema_version=row.schema_version, proactivity_mode=row.proactivity_mode,
        memory_visible=row.memory_visible, patterns_visible=row.patterns_visible,
        passive_suggestions_enabled=row.passive_suggestions_enabled,
        questions_enabled=row.questions_enabled, interruptions_enabled=row.interruptions_enabled,
        prospective_resurfacing_enabled=row.prospective_resurfacing_enabled,
        opportunity_suggestions_enabled=row.opportunity_suggestions_enabled,
        monthly_ai_budget_eur=row.monthly_ai_budget_eur,
        disabled_skills=sorted(set(row.disabled_skills_json or [])), version=row.version,
    )


class IntelligenceSettingsService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def get_model(self, db: Session, user: UserProfile) -> UserIntelligenceSettings:
        row = db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        if row is None:
            row = UserIntelligenceSettings(user_id=user.id)
            db.add(row)
            db.flush()
        return row

    def get(self, db: Session, user: UserProfile) -> IntelligenceSettingsRead:
        return _read(self.get_model(db, user))

    def update(self, db: Session, user: UserProfile, payload: IntelligenceSettingsUpdate) -> IntelligenceSettingsRead:
        row = self.get_model(db, user)
        if payload.expected_version is not None and payload.expected_version != row.version:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Intelligence settings changed after they were loaded.")
        data = payload.model_dump(exclude={"expected_version"}, exclude_unset=True, mode="json")
        if "disabled_skills" in data:
            known = set(SkillRegistry(self.settings, ToolRegistry()).load().skills)
            unknown = set(data["disabled_skills"] or []) - known
            if unknown:
                from fastapi import HTTPException, status
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown skills: {', '.join(sorted(unknown))}")
            row.disabled_skills_json = sorted(set(data.pop("disabled_skills") or []))
        for name, value in data.items():
            setattr(row, name, value)
        row.version += 1
        db.flush()
        append_event(
            db, user, event_type="intelligence_settings.updated", aggregate_type="user_intelligence_settings",
            aggregate_id=row.id, payload={"settings_id": row.id, "fields": sorted(payload.model_fields_set - {"expected_version"})},
            outbox=True,
        )
        return _read(row)

    def update_agent_models(self, db: Session, user: UserProfile, payload: AgentModelSettingsUpdate) -> list[AgentSettingsRead]:
        row = self.get_model(db, user)
        if payload.expected_version is not None and payload.expected_version != row.version:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Intelligence settings changed after they were loaded.")
        registry = SkillRegistry(self.settings, ToolRegistry()).load()
        known = {name for name, skill in registry.skills.items() if skill.manifest.assistant_roles}
        unknown = set(payload.agents) - known
        if unknown:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown agents: {', '.join(sorted(unknown))}")

        metadata = dict(row.metadata_json or {})
        preferences = dict(metadata.get("agent_model_preferences") or {})
        preferences.update({name: model.model_dump(mode="json") for name, model in payload.agents.items()})
        metadata["agent_model_preferences"] = preferences
        metadata["live_agents_enabled"] = True
        row.metadata_json = metadata
        row.version += 1
        db.flush()
        append_event(
            db, user, event_type="intelligence_settings.agent_models_updated",
            aggregate_type="user_intelligence_settings", aggregate_id=row.id,
            payload={"settings_id": row.id, "agents": sorted(payload.agents), "live_agents_enabled": True}, outbox=True,
        )
        return self._agent_settings(db, user, row, registry)

    def update_agent_profile(self, db: Session, user: UserProfile, skill_name: str, payload: AgentProfileUpdate) -> AgentSettingsRead:
        from fastapi import HTTPException

        registry = SkillRegistry(self.settings, ToolRegistry()).load()
        if skill_name not in registry.skills or not registry.skills[skill_name].manifest.assistant_roles:
            raise HTTPException(status_code=404, detail="Agent not found.")
        self.get_model(db, user)
        row = db.scalar(select(UserIntelligenceSettings).where(
            UserIntelligenceSettings.user_id == user.id,
        ).with_for_update().execution_options(populate_existing=True))
        if payload.expected_version is not None and payload.expected_version != row.version:
            raise HTTPException(status_code=409, detail="Intelligence settings changed after they were loaded.")
        metadata = dict(row.metadata_json or {})
        profiles = dict(metadata.get("agent_profiles") or {})
        profiles[skill_name] = payload.model_dump(exclude={"expected_version"}, mode="json")
        metadata["agent_profiles"] = profiles
        row.metadata_json = metadata
        row.version += 1
        db.flush()
        append_event(
            db, user, event_type="intelligence_settings.agent_profile_updated",
            aggregate_type="user_intelligence_settings", aggregate_id=row.id,
            payload={"settings_id": row.id, "agent": skill_name, "version": row.version}, outbox=True,
        )
        return next(item for item in self._agent_settings(db, user, row, registry) if item.skill_name == skill_name)

    @staticmethod
    def live_agents_enabled(db: Session, user: UserProfile, row: UserIntelligenceSettings | None = None) -> bool:
        row = row or db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        if row is None:
            return False
        metadata = row.metadata_json or {}
        preferences = metadata.get("agent_model_preferences") or {}
        return bool(metadata.get("live_agents_enabled") and preferences)

    @staticmethod
    def live_agents_ready(db: Session, user: UserProfile, row: UserIntelligenceSettings | None = None) -> bool:
        row = row or db.scalar(select(UserIntelligenceSettings).where(UserIntelligenceSettings.user_id == user.id))
        if not IntelligenceSettingsService.live_agents_enabled(db, user, row):
            return False
        preferences = (row.metadata_json or {}).get("agent_model_preferences") or {}
        secret_store = ProviderSecretStore()
        providers = {preference.get("provider") for preference in preferences.values() if isinstance(preference, dict)}
        return any(
            provider in {"openai", "gemini"} and secret_store.configured(db, user, provider)
            for provider in providers
        )

    def _agent_settings(self, db: Session, user: UserProfile, row: UserIntelligenceSettings, registry=None) -> list[AgentSettingsRead]:
        registry = registry or SkillRegistry(self.settings, ToolRegistry()).load()
        counts = dict(db.execute(
            select(MemoryItem.domain, func.count(MemoryItem.id)).where(
                MemoryItem.user_id == user.id, MemoryItem.deleted_at.is_(None),
                MemoryItem.status.in_(["candidate", "active", "uncertain"]),
            ).group_by(MemoryItem.domain)
        ).all())
        secret_store = ProviderSecretStore()
        available = secret_store.available(db)
        stored = (row.metadata_json or {}).get("agent_model_preferences") or {}
        default_provider = self.settings.agent_provider
        if available and not secret_store.configured(db, user, default_provider):
            default_provider = next((provider for provider in ("openai", "gemini") if secret_store.configured(db, user, provider)), default_provider)
        domains = {
            "chef": "kitchen", "fitness-coach": "fitness", "learning-coach": "learning",
            "home-manager": "home", "finance": "finance", "self-core": "general",
        }
        result = []
        for skill in registry.skills.values():
            if not skill.manifest.assistant_roles:
                continue
            preference = stored.get(skill.manifest.name) or {}
            provider = preference.get("provider", default_provider)
            configured = secret_store.configured(db, user, provider) if available else False
            provider_defaults = DEFAULT_AGENT_MODELS.get(provider, DEFAULT_AGENT_MODELS["openai"])
            def tier(name: str) -> str:
                return preference.get(name) or provider_defaults[name.removesuffix("_model").upper()]
            domain = domains.get(skill.manifest.name, "general")
            result.append(AgentSettingsRead(
                skill_name=skill.manifest.name,
                name=skill.manifest.name.replace("-", " ").title(),
                description=skill.manifest.description,
                roles=skill.manifest.assistant_roles,
                provider=provider,
                economy_model=tier("economy_model"),
                fast_model=tier("fast_model"),
                reasoning_model=tier("reasoning_model"),
                memory_scopes=skill.manifest.memory_scopes,
                memory_domain=domain,
                memory_count=int(counts.get(domain, 0) or 0),
                credential_configured=configured,
                profile=agent_profile(row.metadata_json, skill.manifest.name),
            ))
        return result

    def skill_enabled(self, db: Session, user: UserProfile, skill_name: str) -> bool:
        return skill_name not in set(self.get_model(db, user).disabled_skills_json or [])

    def control_surface(self, db: Session, user: UserProfile) -> IntelligenceControlSurface:
        row = self.get_model(db, user)
        registry = SkillRegistry(self.settings, ToolRegistry()).load()
        disabled = set(row.disabled_skills_json or [])
        usage = AIUsageService(self.settings)
        budget = usage.budget_state(db, user.id)
        memory_counts = dict(db.execute(select(MemoryItem.status, func.count(MemoryItem.id)).where(
            MemoryItem.user_id == user.id,
        ).group_by(MemoryItem.status)).all())
        pattern_counts = dict(db.execute(select(PatternEvidence.status, func.count(PatternEvidence.id)).where(
            PatternEvidence.user_id == user.id,
        ).group_by(PatternEvidence.status)).all())
        conversation_counts = dict(db.execute(select(ConversationThread.status, func.count(ConversationThread.id)).where(
            ConversationThread.user_id == user.id,
        ).group_by(ConversationThread.status)).all())
        skills = [{
            "name": item.manifest.name,
            "description": item.manifest.description,
            "version": item.manifest.version,
            "enabled": item.manifest.enabled and item.manifest.name not in disabled,
            "configured_enabled": item.manifest.enabled,
            "capabilities": [item.manifest.default_capability.value, item.manifest.max_capability.value],
            "roles": item.manifest.assistant_roles,
        } for item in registry.skills.values()]
        providers = self._provider_states(db, user)
        agents = self._agent_settings(db, user, row, registry)
        vault_ready = ProviderSecretStore.available(db)
        return IntelligenceControlSurface(
            settings=_read(row),
            memory={"visible": row.memory_visible, "counts": memory_counts, "controls": ["pin", "correct", "forget", "provenance"]},
            patterns={"visible": row.patterns_visible, "counts": pattern_counts, "controls": ["inspect", "correct"]},
            conversations={"counts": conversation_counts, "controls": ["inspect", "archive", "export"], "delete_semantics": "Archive removes the conversation from active history; canonical domain state is retained."},
            skills=skills, providers=providers, agents=agents,
            active_agent_runtime="sdk" if self.live_agents_enabled(db, user, row) else self.settings.agent_runtime,
            live_agents_enabled=self.live_agents_ready(db, user, row),
            credential_management_available=vault_ready,
            usage={
                "monthly_spend_eur": budget.monthly_spend_eur, "budget_eur": budget.budget_eur,
                "warning": budget.warning, "economy_only": budget.economy_only,
                "optional_suppressed": budget.optional_suppressed,
                "by_provider": usage.by_provider(db, user.id), "by_model": usage.by_model(db, user.id),
                "by_capability": usage.by_capability(db, user.id), "by_skill": usage.by_skill(db, user.id),
            },
            privacy={
                "export_endpoint": "/api/v1/export", "memory_forget_endpoint": "/api/v1/memories/{id}/forget",
                "memory_correct_endpoint": "/api/v1/memories/{id}",
                "conversation_archive_endpoint": "/api/v1/assistant/threads/{id}/archive",
                "account_delete_supported": False,
            },
        )

    def _provider_states(self, db: Session, user: UserProfile) -> list[dict]:
        ai_provider = self.settings.ai_provider.lower()
        ai_configured = ai_provider == "fake" or (ai_provider == "gemini" and bool(self.settings.gemini_api_key))
        secret_store = ProviderSecretStore()
        vault_ready = secret_store.available(db)
        jev_credential_storage_ready = secret_store.provider_available(db, "jev")
        credential_states = {
            provider: (jev_credential_storage_ready if provider == "jev" else vault_ready)
            and secret_store.configured(db, user, provider)
            for provider in ("openai", "gemini", "jev")
        }
        providers = [
            {
                "id": ai_provider, "kind": "generation", "enabled": self.settings.ai_enabled,
                "configured": ai_configured,
                "state": "disabled" if not self.settings.ai_enabled else "available" if ai_configured else "not_configured",
                "capabilities": ["ECONOMY", "FAST", "REASONING", "VISION", "EMBEDDING"],
                "models": [self.settings.ai_model_economy, self.settings.ai_model_fast, self.settings.ai_model_reasoning, self.settings.ai_model_embedding],
            },
            *[
                {
                    "id": provider, "kind": "agent", "enabled": self.settings.ai_enabled,
                    "configured": credential_states[provider],
                    "credential_configured": credential_states[provider],
                    "credential_source": "supabase_vault",
                    "state": "available" if credential_states[provider] else "not_configured" if vault_ready else "disabled",
                    "capabilities": ["ECONOMY", "FAST", "REASONING", "EMBEDDING"],
                    "models": list(DEFAULT_AGENT_MODELS[provider].values()),
                }
                for provider in ("openai", "gemini")
            ],
            {
                "id": "laya_local", "kind": "decision", "enabled": self.settings.laya_enabled,
                "configured": self.settings.laya_enabled,
                "state": "available" if self.settings.laya_enabled else "disabled",
                "capabilities": ["categorical_decision"], "models": [self.settings.laya_model],
            },
            {
                "id": "jev", "kind": "decision", "enabled": self.settings.jev_enabled,
                "configured": credential_states.get("jev", False),
                "credential_configured": credential_states.get("jev", False),
                "credential_source": "supabase_vault",
                "credential_storage_available": jev_credential_storage_ready,
                "state": "available" if self.settings.jev_enabled and credential_states["jev"] else "not_configured" if self.settings.jev_enabled and vault_ready else "disabled",
                "capabilities": ["typed_decision"], "models": [self.settings.jev_model],
            },
        ]
        return providers
