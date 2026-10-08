from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


REPOSITORY = Path(__file__).resolve().parents[2]
REQUIRED_SCENARIOS = {
    "MORNING_START",
    "MISSED_STUDY_RECOVERY",
    "COOK_AND_UPDATE_INVENTORY",
    "WORKOUT_EXECUTION",
    "FINANCE_QUICK_CAPTURE",
    "UNCERTAIN_CAPTURE_REVIEW",
    "IMPLEMENTATION_IDEA_PARKING",
    "MOVIE_PROSPECTIVE_RESURFACE",
    "SOCIAL_OPPORTUNITY_FILTER",
    "PLAN_PROPOSAL_ACCEPT",
    "RESTART_ACTIVE_WORKSPACE",
    "TWO_CLIENT_REALTIME",
    "AI_OUTAGE",
}


def test_release_version_is_consistent() -> None:
    root_package = json.loads((REPOSITORY / "package.json").read_text(encoding="utf-8"))
    web_package = json.loads((REPOSITORY / "apps" / "web" / "package.json").read_text(encoding="utf-8"))
    settings = Settings(_env_file=None)
    assert root_package["version"] == web_package["version"] == "2.0.0"
    assert settings.deployment_version == "2.0"
    assert create_app(settings).version == "2.0"


def test_all_named_golden_scenarios_resolve_to_real_tests() -> None:
    manifest = json.loads((REPOSITORY / "scripts" / "v2_golden_scenarios.json").read_text(encoding="utf-8"))
    assert set(manifest) == REQUIRED_SCENARIOS
    assert len(set(manifest.values())) == len(REQUIRED_SCENARIOS)
    for node_id in manifest.values():
        relative_path, function_name = node_id.split("::", 1)
        source_path = REPOSITORY / "backend" / relative_path
        assert source_path.is_file(), node_id
        assert f"def {function_name}(" in source_path.read_text(encoding="utf-8"), node_id


def test_release_has_no_voice_runtime_or_frontend_dependency() -> None:
    backend_modules = {path.stem.lower() for path in (REPOSITORY / "backend" / "app").rglob("*.py")}
    dependencies = {
        **json.loads((REPOSITORY / "package.json").read_text(encoding="utf-8")).get("dependencies", {}),
        **json.loads((REPOSITORY / "apps" / "web" / "package.json").read_text(encoding="utf-8")).get("dependencies", {}),
    }
    assert not {"voice", "stt", "tts", "vad"}.intersection(backend_modules)
    assert not any(token in dependency.lower() for dependency in dependencies for token in ("speech", "voice", "microphone"))


def test_minimal_configuration_keeps_optional_providers_off_without_startup_failure() -> None:
    settings = Settings(
        _env_file=None,
        ai_enabled=False,
        gemini_api_key=None,
        laya_enabled=False,
        laya_cache_path=None,
        jev_enabled=False,
        jev_api_key=None,
        tmdb_api_token=None,
        ticketmaster_api_key=None,
        api_football_api_key=None,
    )
    assert settings.ai_enabled is False
    assert settings.laya_enabled is False and settings.jev_enabled is False
    assert settings.tmdb_api_token is None and settings.ticketmaster_api_key is None


def test_postgresql_release_smoke_is_part_of_the_full_gate() -> None:
    release_script = (REPOSITORY / "scripts" / "verify_v2_release.py").read_text(encoding="utf-8")
    smoke_script = REPOSITORY / "scripts" / "verify_v2_postgres.py"
    assert smoke_script.is_file()
    assert "verify_v2_postgres.py" in release_script
    source = smoke_script.read_text(encoding="utf-8")
    assert "CREATE DATABASE" in source and "DROP DATABASE IF EXISTS" in source
    assert "QuickCaptureService" in source and "ActiveWorkspaceService" in source


def test_backup_restore_rehearsal_is_part_of_the_full_gate() -> None:
    release_script = (REPOSITORY / "scripts" / "verify_v2_release.py").read_text(encoding="utf-8")
    rehearsal = REPOSITORY / "scripts" / "verify_backup_restore.py"
    assert rehearsal.is_file() and "verify_backup_restore.py" in release_script
    source = rehearsal.read_text(encoding="utf-8")
    assert "pg_dump" in source and "pg_restore" in source
    assert "--validate-restored" in source


def test_clean_install_rehearses_worker_backend_and_frontend() -> None:
    release_script = (REPOSITORY / "scripts" / "verify_v2_release.py").read_text(encoding="utf-8")
    rehearsal = REPOSITORY / "scripts" / "verify_clean_install.py"
    assert rehearsal.is_file() and "verify_clean_install.py" in release_script
    source = rehearsal.read_text(encoding="utf-8")
    assert '"app.worker", "--once"' in source
    assert '"uvicorn", "app.main:app"' in source
    assert '"vite", "preview"' in source
