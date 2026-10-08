"""Verify a clean Life OS 2.0 install from its deterministic source archive."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4
import venv
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SAFE_DIRECTORY_NAME = "life-os-v2-clean-install"
DATABASE_PREFIX = "life_os_v2_clean_"


def _admin_url() -> str:
    explicit = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if explicit:
        return explicit
    sys.path.insert(0, str(BACKEND))
    from app.core.config import Settings

    return Settings().database_url


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _pnpm() -> str:
    executable = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if not executable:
        raise RuntimeError("pnpm is required for the clean-install smoke.")
    return executable


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_url(url: str, process: subprocess.Popen, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Process exited before {url} became available (exit {process.returncode}).")
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 400:
                    return
        except Exception as exc:  # Network startup errors are expected during polling.
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _safe_prepare(work_dir: Path) -> None:
    resolved = work_dir.resolve()
    if resolved.name != SAFE_DIRECTORY_NAME:
        raise RuntimeError(f"Clean-install work directory must be named {SAFE_DIRECTORY_NAME!r}.")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve() or resolved == ROOT.resolve():
        raise RuntimeError("Refusing unsafe clean-install work directory.")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (destination / member.filename).resolve()
            if destination != target and destination not in target.parents:
                raise RuntimeError(f"Unsafe path in source archive: {member.filename}")
        source.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".cache" / SAFE_DIRECTORY_NAME)
    args = parser.parse_args()

    work_dir = args.work_dir.resolve()
    _safe_prepare(work_dir)
    archive = work_dir / "life-os-v2.0-source.zip"
    source_dir = work_dir / "source"
    venv_dir = work_dir / "venv"
    _run([sys.executable, str(ROOT / "scripts" / "package_source.py"), str(archive)], cwd=ROOT)
    source_dir.mkdir()
    _safe_extract(archive, source_dir)

    print("Creating clean Python environment and installing backend dependencies.")
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    clean_python = _python(venv_dir)
    _run(
        [str(clean_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"],
        cwd=source_dir / "backend",
    )
    print("Installing frontend dependencies from the frozen lockfile.")
    _run([_pnpm(), "install", "--frozen-lockfile", "--config.node-linker=hoisted"], cwd=source_dir)

    admin_url = _admin_url()
    parsed = make_url(admin_url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("Clean-install verification requires a PostgreSQL admin URL.")
    database_name = f"{DATABASE_PREFIX}{uuid4().hex[:12]}"
    if not re.fullmatch(r"life_os_v2_clean_[a-f0-9]{12}", database_name):
        raise RuntimeError("Refusing to use an unsafe disposable database name.")
    database_url = parsed.set(database=database_name).render_as_string(hide_password=False)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None
    created = False
    backend_log = (work_dir / "backend.log").open("w", encoding="utf-8")
    frontend_log = (work_dir / "frontend.log").open("w", encoding="utf-8")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        created = True
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": database_url,
                "AI_ENABLED": "false",
                "LAYA_ENABLED": "false",
                "JEV_ENABLED": "false",
                "DECISION_SHADOW_ENABLED": "false",
                "MOVIE_METADATA_PROVIDER": "disabled",
                "OPPORTUNITY_DISCOVERY_ENABLED": "false",
                "DEVELOPMENT_AUTH_ENABLED": "true",
                "DEPLOYMENT_VERSION": "2.0",
            }
        )
        clean_backend = source_dir / "backend"
        _run([str(clean_python), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"], cwd=clean_backend, env=environment)
        _run([str(clean_python), "-m", "app.worker", "--once", "--limit", "1"], cwd=clean_backend, env=environment)

        backend_port = _free_port()
        backend_process = subprocess.Popen(
            [str(clean_python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
            cwd=clean_backend,
            env=environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
        )
        _wait_for_url(f"http://127.0.0.1:{backend_port}/readiness", backend_process)

        web_environment = environment.copy()
        web_environment["VITE_API_BASE_URL"] = f"http://127.0.0.1:{backend_port}"
        web_environment["npm_config_node_linker"] = "hoisted"
        _run([_pnpm(), "--dir", "apps/web", "typecheck"], cwd=source_dir, env=web_environment)
        _run([_pnpm(), "--dir", "apps/web", "build"], cwd=source_dir, env=web_environment)
        frontend_port = _free_port()
        frontend_process = subprocess.Popen(
            [_pnpm(), "--dir", "apps/web", "exec", "vite", "preview", "--host", "127.0.0.1", "--port", str(frontend_port)],
            cwd=source_dir,
            env=web_environment,
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
        )
        _wait_for_url(f"http://127.0.0.1:{frontend_port}/", frontend_process)
        print("Clean install passed: migrations, worker, backend readiness, frontend build, and frontend preview.")
        return 0
    finally:
        _stop(frontend_process)
        _stop(backend_process)
        backend_log.close()
        frontend_log.close()
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            print(f"Dropped disposable PostgreSQL database {database_name}")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
