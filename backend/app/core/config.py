from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Runtime configuration for the modular monolith backend."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Life OS"
    app_env: str = Field(default="development", description="development, test, or production")
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./life_os_dev.db"
    development_auth_enabled: bool = True
    development_auth_token: str = "dev-local-token"
    supabase_jwt_secret: str | None = None
    supabase_project_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = "authenticated"
    authorized_auth_subjects: str = ""
    integration_installation_admin_subjects: str = Field(default="", description="Explicit auth-subject allowlist for shared installation credentials; empty denies access.")
    frontend_base_url: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    log_level: str = "INFO"
    deployment_version: str = "2.0"
    planner_version: str = "v1.5-domain-intelligence"
    agent_prompt_version: str = "v1.5"
    learning_model_version: str = "v0"
    ai_enabled: bool = True
    agent_runtime: Literal["legacy", "sdk"] = "legacy"
    agent_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    agent_model_economy: str = ""
    agent_model_fast: str = ""
    agent_model_reasoning: str = ""
    agent_max_turns: int = Field(default=6, ge=1, le=6)
    agent_trace_export_enabled: bool = False
    ai_provider: str = "fake"
    ai_model_default: str = "life-os-fake-standard"
    ai_model_strong: str = "life-os-fake-strong"
    ai_model_economy: str = "life-os-fake-standard"
    ai_model_fast: str = "life-os-fake-standard"
    ai_model_reasoning: str = "life-os-fake-strong"
    ai_model_embedding: str = "life-os-fake-embedding"
    ai_model_vision: str = "life-os-fake-vision"
    ai_model_image: str = "life-os-fake-image"
    ai_model_pricing_json: str = "{}"
    gemini_api_key: str | None = None
    ai_timeout_seconds: int = 15
    ai_monthly_budget_eur: float = 12.0
    ai_warning_threshold_eur: float = 10.0
    ai_economy_threshold_eur: float = 10.5
    ai_restrict_optional_threshold_eur: float = 11.0
    ai_context_max_chars: int = 24000
    decision_infra_enabled: bool = False
    decision_provider: str = "fake"
    decision_tracing_enabled: bool = True
    decision_policy_version: str = "decision-policy-v1"
    decision_routing_mode: str = "AUTO"
    decision_routing_policy_version: str = "decision-routing-v1"
    decision_confidence_thresholds_json: str = (
        '{"attention":0.72,"context_relevance":0.70,"contributor_activation":0.68,'
        '"curiosity":0.72,"memory":0.72,"prospective":0.72,"default":0.72}'
    )
    laya_enabled: bool = False
    laya_model: str = "auto"
    laya_device: str = "auto"
    laya_cache_path: str | None = None
    laya_max_choices: int = Field(default=16, ge=2, le=255)
    laya_max_context_bytes: int = Field(default=16_384, ge=1024, le=1_048_576)
    jev_enabled: bool = True
    jev_api_key: str | None = None
    jev_base_url: str = "https://api.typesafe.ai"
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = Field(default=5.0, ge=0.1, le=60)
    jev_max_retries: int = Field(default=1, ge=0, le=2)
    jev_daily_budget_eur: float = Field(default=1.0, ge=0)
    decision_shadow_enabled: bool = False
    decision_shadow_provider: str = "laya_local"
    decision_shadow_sample_rate: float = Field(default=0.05, ge=0, le=1)
    decision_shadow_families: str = ""
    decision_shadow_daily_budget_eur: float = Field(default=0.25, ge=0)
    decision_live_provider_tests: bool = False
    cognitive_workspace_enabled: bool = False
    attention_policy_enabled: bool = False
    intelligence_feedback_enabled: bool = False
    feedback_max_questions: int = Field(default=4, ge=1, le=4)
    response_composer_enabled: bool = True
    response_composer_generative_enabled: bool = True
    realtime_state_enabled: bool = True
    realtime_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    realtime_history_limit: int = Field(default=250, ge=10, le=2000)
    conversation_compaction_threshold: int = 24
    conversation_recent_window: int = 10
    embedding_dimensions: int = Field(default=768, ge=128, le=3072)
    memory_retrieval_limit: int = Field(default=6, ge=1, le=20)
    episode_retrieval_limit: int = Field(default=3, ge=1, le=10)
    pattern_context_limit: int = Field(default=6, ge=1, le=20)
    memory_context_max_chars: int = Field(default=6000, ge=1000, le=24000)
    memory_min_relevance: float = 0.30
    memory_semantic_merge_threshold: float = 0.88
    memory_candidate_gate_enabled: bool = True
    memory_consolidation_event_threshold: int = 3
    memory_consolidation_lookback_hours: int = 30
    planner_horizon_days: int = Field(default=10, ge=7, le=14)
    planner_slot_granularity_minutes: int = Field(default=15, ge=5, le=60)
    planner_freeze_window_minutes: int = Field(default=45, ge=0, le=240)
    planner_max_candidates: int = Field(default=100, ge=10, le=500)
    planner_max_slots_per_candidate: int = Field(default=96, ge=12, le=300)
    planner_capacity_floor: float = Field(default=0.65, ge=0.4, le=1.0)
    planner_capacity_ceiling: float = Field(default=1.15, ge=1.0, le=1.5)
    planner_morning_hour: int = Field(default=5, ge=0, le=12)
    skills_directory: str = str(BACKEND_DIR / "skills")
    media_storage_provider: str = "local"
    media_storage_path: str = str(BACKEND_DIR / "var" / "media")
    media_max_upload_bytes: int = Field(default=10_000_000, ge=100_000, le=25_000_000)
    finance_default_currency: str = "EUR"
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    push_subject: str | None = None
    push_delivery_mode: str = "mock"
    outbox_max_attempts: int = 5
    outbox_base_backoff_seconds: int = 60
    outbox_max_backoff_seconds: int = 3600
    fixture_provider: str = "api_football"
    api_football_api_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"
    api_football_besiktas_team_id: str = "549"
    fixture_sync_timeout_seconds: float = Field(default=10.0, ge=1, le=60)
    leisure_movies_enabled: bool = True
    movie_metadata_provider: str = "disabled"
    tmdb_api_token: str | None = None
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    movie_metadata_language: str = "en-US"
    movie_metadata_timeout_seconds: float = Field(default=10.0, ge=1, le=60)
    movie_default_city: str | None = None
    opportunity_discovery_enabled: bool = True
    opportunity_default_city: str | None = None
    opportunity_default_country_code: str | None = None
    chef_intent_enabled: bool = True
    chef_intent_generative_enabled: bool = True
    opportunity_source_cadence_minutes: int = Field(default=360, ge=15, le=10_080)
    opportunity_discovery_horizon_days: int = Field(default=30, ge=1, le=180)
    opportunity_max_results_per_source: int = Field(default=100, ge=1, le=200)
    opportunity_source_timeout_seconds: float = Field(default=10.0, ge=1, le=60)
    ticketmaster_api_key: str | None = None
    ticketmaster_api_base_url: str = "https://app.ticketmaster.com/discovery/v2"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        is_production = self.app_env.lower() == "production"
        if is_production and self.development_auth_enabled:
            raise ValueError("DEVELOPMENT_AUTH_ENABLED must be false in production.")
        if is_production and "*" in self.allowed_origins:
            raise ValueError("CORS_ORIGINS must not contain '*' in production.")
        if is_production and not self.supabase_jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET is required in production.")
        if is_production and not self.expected_supabase_issuer:
            raise ValueError("SUPABASE_PROJECT_URL or SUPABASE_JWT_ISSUER is required in production.")
        if is_production and not self.authorized_subject_set:
            raise ValueError("AUTHORIZED_AUTH_SUBJECTS must include the private Supabase user id in production.")
        if is_production and self.decision_infra_enabled and self.decision_provider == "fake":
            if self.decision_routing_mode.upper() == "FAKE":
                raise ValueError("Fake decision routing cannot be enabled as production intelligence.")
        if self.decision_routing_mode.upper() not in {"FAKE", "LAYA_ONLY", "JEV_ONLY", "AUTO", "SHADOW"}:
            raise ValueError("DECISION_ROUTING_MODE must be FAKE, LAYA_ONLY, JEV_ONLY, AUTO, or SHADOW.")
        if self.laya_device.lower() not in {"auto", "cpu", "cuda", "mps"}:
            raise ValueError("LAYA_DEVICE must be auto, cpu, cuda, or mps.")
        try:
            thresholds = json.loads(self.decision_confidence_thresholds_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("DECISION_CONFIDENCE_THRESHOLDS_JSON must be a JSON object.") from exc
        if not isinstance(thresholds, dict) or not thresholds or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1
            for value in thresholds.values()
        ):
            raise ValueError("Decision confidence thresholds must be numbers between 0 and 1.")
        if is_production and self.push_delivery_mode == "webpush" and not (self.vapid_public_key and self.vapid_private_key and self.push_subject):
            raise ValueError("VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, and PUSH_SUBJECT are required for webpush delivery.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def authorized_subject_set(self) -> set[str]:
        return {subject.strip() for subject in self.authorized_auth_subjects.split(",") if subject.strip()}

    @property
    def expected_supabase_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer.rstrip("/")
        if self.supabase_project_url:
            return f"{self.supabase_project_url.rstrip('/')}/auth/v1"
        return None

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def decision_confidence_thresholds(self) -> dict[str, float]:
        return {key: float(value) for key, value in json.loads(self.decision_confidence_thresholds_json).items()}

    @property
    def shadow_family_set(self) -> set[str]:
        return {family.strip() for family in self.decision_shadow_families.split(",") if family.strip()}


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(f"Invalid Life OS configuration: {exc}") from exc


settings = get_settings()
