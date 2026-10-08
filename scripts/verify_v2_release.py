"""Run the deterministic Life OS 2.0 release gate without duplicating test logic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WEB = ROOT / "apps" / "web"
SCENARIOS_PATH = ROOT / "scripts" / "v2_golden_scenarios.json"


def run(label: str, command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"\n[{label}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def python_command(*arguments: str) -> list[str]:
    return [sys.executable, *arguments]


def pnpm_command(*arguments: str) -> list[str]:
    executable = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if not executable:
        raise RuntimeError("pnpm is required for the release gate.")
    return [executable, *arguments]


def package_twice(artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    first = artifact_dir / "life-os-v2.0-source-a.zip"
    second = artifact_dir / "life-os-v2.0-source-b.zip"
    for destination in (first, second):
        run("source package", python_command(str(ROOT / "scripts" / "package_source.py"), str(destination)))
    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    second_hash = hashlib.sha256(second.read_bytes()).hexdigest()
    if first_hash != second_hash:
        raise RuntimeError("Deterministic source package hashes differ.")
    final = artifact_dir / "life-os-v2.0-source.zip"
    shutil.copyfile(first, final)
    first.unlink()
    second.unlink()
    print(f"Deterministic package: {final} sha256={first_hash}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Run named golden scenarios instead of every test/build check.")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ".cache" / "release")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip disposable PostgreSQL migration verification.")
    parser.add_argument("--skip-clean-install", action="store_true", help="Skip the isolated dependency/install/startup rehearsal.")
    args = parser.parse_args()

    scenarios: dict[str, str] = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    run("backend compile", python_command("-m", "compileall", "-q", "app", "tests", "../scripts"), cwd=BACKEND)
    if args.quick:
        run("golden scenarios", python_command("-m", "pytest", "-q", *scenarios.values()), cwd=BACKEND)
        run("repository integrity", python_command("-m", "pytest", "-q", "tests/test_repository_integrity.py"), cwd=BACKEND)
        run("frontend typecheck", pnpm_command("--dir", str(WEB), "typecheck"))
    else:
        run("backend tests", python_command("-m", "pytest", "-q"), cwd=BACKEND)
        run("frontend typecheck", pnpm_command("--dir", str(WEB), "typecheck"))
        run("frontend tests", pnpm_command("--dir", str(WEB), "test"))
        run("frontend build", pnpm_command("--dir", str(WEB), "build"))

    run("alembic heads", python_command("-m", "alembic", "-c", "alembic.ini", "heads"), cwd=BACKEND)
    run("alembic current", python_command("-m", "alembic", "-c", "alembic.ini", "current"), cwd=BACKEND)
    if not args.skip_migrations:
        run("disposable PostgreSQL migrations", python_command(str(ROOT / "scripts" / "verify_migrations.py")))
        run("PostgreSQL integration smoke", python_command(str(ROOT / "scripts" / "verify_v2_postgres.py")))
        run(
            "PostgreSQL backup/restore",
            python_command(str(ROOT / "scripts" / "verify_backup_restore.py"), "--artifact-dir", str(args.artifact_dir.resolve())),
        )
    if not args.quick:
        if not args.skip_clean_install:
            run(
                "clean install",
                python_command(
                    str(ROOT / "scripts" / "verify_clean_install.py"),
                    "--work-dir",
                    str((args.artifact_dir.resolve() / "life-os-v2-clean-install")),
                ),
            )
        package_twice(args.artifact_dir.resolve())
    print("\nLife OS 2.0 release gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
