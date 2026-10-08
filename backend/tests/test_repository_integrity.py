from __future__ import annotations

import ast
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.ai.providers import FakeAIProvider
from app.ai.types import AIMessage, AIProviderError, AIRequest
from app.core.config import Settings
from app.database.base import Base
from app.database import models  # noqa: F401


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent
MIGRATIONS_DIR = BACKEND_DIR / "migrations" / "versions"


def test_process_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://dotenv/value\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://process/value")

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8", extra="ignore")

    assert IsolatedSettings().database_url == "postgresql+psycopg://process/value"


def test_production_configuration_requires_supported_hs256_contract() -> None:
    valid = {
        "app_env": "production",
        "development_auth_enabled": False,
        "database_url": "postgresql+psycopg://user:password@example.invalid/life_os",
        "supabase_jwt_secret": "test-only-secret",
        "supabase_project_url": "https://project.example.invalid",
        "authorized_auth_subjects": "private-user-id",
        "cors_origins": "https://life.example.invalid",
    }

    settings = Settings(_env_file=None, **valid)
    assert settings.expected_supabase_issuer == "https://project.example.invalid/auth/v1"

    with pytest.raises(ValidationError, match="SUPABASE_PROJECT_URL or SUPABASE_JWT_ISSUER"):
        Settings(_env_file=None, **{**valid, "supabase_project_url": None, "supabase_jwt_issuer": None})


def test_historical_migrations_do_not_build_from_live_orm_metadata() -> None:
    forbidden_calls = ("Base.metadata.create_all", "Base.metadata.drop_all")
    forbidden_modules = {"app.database.base", "app.database.models"}

    for migration in MIGRATIONS_DIR.glob("*.py"):
        source = migration.read_text(encoding="utf-8")
        assert not any(call in source for call in forbidden_calls), migration.name
        tree = ast.parse(source, filename=str(migration))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert imported_modules.isdisjoint(forbidden_modules), migration.name


def test_alembic_has_one_expected_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == ["0030_supabase_data_api_lockdown"]


def test_legacy_kitchen_tables_are_not_owned_by_current_orm() -> None:
    legacy_tables = {
        "kitchen_meals",
        "kitchen_nutrition_logs",
        "kitchen_food_preferences",
        "kitchen_shopping_lists",
        "kitchen_shopping_list_items",
    }
    assert legacy_tables.isdisjoint(Base.metadata.tables)


def test_fake_provider_uses_canonical_ai_errors_and_has_no_legacy_gateway() -> None:
    provider = FakeAIProvider()
    request = AIRequest(
        system_instruction="Classify the request.",
        messages=[AIMessage(role="user", content="provider failure")],
        metadata={"assistant_role": "GENERAL_ASSISTANT"},
    )

    with pytest.raises(AIProviderError, match="Fake provider failure fixture"):
        provider.complete(model="life-os-fake-standard", request=request)

    providers_source = (BACKEND_DIR / "app" / "ai" / "providers.py").read_text(encoding="utf-8")
    assert "app.assistant.gateway" not in providers_source
    assert not (BACKEND_DIR / "app" / "assistant" / "gateway.py").exists()


def test_only_planning_runtime_constructs_plan_blocks() -> None:
    offenders: list[str] = []
    app_dir = BACKEND_DIR / "app"
    for source_path in app_dir.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        constructs_plan_block = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PlanBlock"
            for node in ast.walk(tree)
        )
        if constructs_plan_block and "planning" not in source_path.relative_to(app_dir).parts:
            offenders.append(str(source_path.relative_to(REPOSITORY_DIR)))
    assert offenders == []
