"""Rehearse a real PostgreSQL backup and restore using disposable databases."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATABASE_PREFIX = "life_os_v2_backup_"


def _admin_url() -> str:
    explicit = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if explicit:
        return explicit
    sys.path.insert(0, str(BACKEND))
    from app.core.config import Settings

    return Settings().database_url


def _postgres_tool(name: str) -> str:
    configured = os.getenv("POSTGRES_BIN")
    candidates = [Path(configured) / f"{name}.exe"] if configured else []
    resolved = shutil.which(f"{name}.exe" if os.name == "nt" else name)
    if resolved:
        candidates.append(Path(resolved))
    if os.name == "nt":
        candidates.extend(
            Path(rf"C:\Program Files\PostgreSQL\{version}\bin\{name}.exe")
            for version in (18, 17, 16, 15, 14)
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        f"{name} was not found. Set POSTGRES_BIN to a PostgreSQL client bin directory."
    )


def _run(
    command: list[str],
    *,
    database_url: str | None = None,
    cwd: Path = ROOT,
    extra_env: dict[str, str] | None = None,
) -> str:
    environment = os.environ.copy()
    if database_url:
        environment["DATABASE_URL"] = database_url
        environment.update({"AI_ENABLED": "false", "LAYA_ENABLED": "false", "JEV_ENABLED": "false"})
    if extra_env:
        environment.update(extra_env)
    try:
        completed = subprocess.run(command, cwd=cwd, env=environment, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        output = "\n".join(part.strip() for part in (exc.stdout, exc.stderr) if part and part.strip())
        if output:
            print(output)
        raise
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if output:
        print(output)
    return output


def _alembic(database_url: str, *arguments: str) -> str:
    return _run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        database_url=database_url,
        cwd=BACKEND,
    )


def _postgres_cli_connection(database_url: str) -> tuple[str, dict[str, str]]:
    parsed = make_url(database_url)
    password = parsed.password or ""
    cli_url = parsed.set(drivername="postgresql", password=None).render_as_string(hide_password=False)
    return cli_url, {"PGPASSWORD": password}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ".cache" / "release")
    args = parser.parse_args()

    pg_dump = _postgres_tool("pg_dump")
    pg_restore = _postgres_tool("pg_restore")
    admin_url = _admin_url()
    parsed = make_url(admin_url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("Backup/restore verification requires a PostgreSQL admin URL.")

    suffix = uuid4().hex[:12]
    source_name = f"{DATABASE_PREFIX}source_{suffix}"
    restored_name = f"{DATABASE_PREFIX}restore_{suffix}"
    safe_pattern = r"life_os_v2_backup_(?:source|restore)_[a-f0-9]{12}"
    if not re.fullmatch(safe_pattern, source_name) or not re.fullmatch(safe_pattern, restored_name):
        raise RuntimeError("Refusing to use unsafe disposable database names.")
    source_url = parsed.set(database=source_name).render_as_string(hide_password=False)
    restored_url = parsed.set(database=restored_name).render_as_string(hide_password=False)
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    dump_path = artifact_dir / f"{source_name}.dump"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    created: list[str] = []

    print(f"Creating disposable PostgreSQL databases {source_name} and {restored_name}")
    try:
        with admin_engine.connect() as connection:
            for name in (source_name, restored_name):
                connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
                created.append(name)

        _alembic(source_url, "upgrade", "head")
        _run(
            [sys.executable, str(ROOT / "scripts" / "verify_v2_postgres.py"), "--existing", "--skip-performance"],
            database_url=source_url,
        )
        source_cli_url, source_password = _postgres_cli_connection(source_url)
        restored_cli_url, restored_password = _postgres_cli_connection(restored_url)
        _run(
            [pg_dump, "--format=custom", "--no-owner", "--no-acl", "--file", str(dump_path), source_cli_url],
            extra_env=source_password,
        )
        if not dump_path.is_file() or dump_path.stat().st_size == 0:
            raise AssertionError("PostgreSQL backup artifact was not created.")
        _run(
            [pg_restore, "--no-owner", "--no-acl", "--exit-on-error", "--dbname", restored_cli_url, str(dump_path)],
            extra_env=restored_password,
        )
        current = _alembic(restored_url, "current")
        if "0027_capture_review_settings" not in current:
            raise AssertionError("Restored database is not at the expected Alembic head.")
        _run(
            [sys.executable, str(ROOT / "scripts" / "verify_v2_postgres.py"), "--validate-restored"],
            database_url=restored_url,
        )
        print(f"PostgreSQL backup/restore rehearsal passed ({dump_path.stat().st_size} bytes).")
        return 0
    finally:
        if dump_path.exists():
            dump_path.unlink()
        for name in reversed(created):
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            print(f"Dropped disposable PostgreSQL database {name}")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
