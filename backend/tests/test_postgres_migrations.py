from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_ADMIN_URL"),
    reason="Set TEST_POSTGRES_ADMIN_URL to run the isolated PostgreSQL migration cycle.",
)
def test_empty_postgres_upgrade_downgrade_reupgrade() -> None:
    repository_dir = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(repository_dir / "scripts" / "verify_migrations.py")],
        cwd=repository_dir,
        check=True,
        env=os.environ.copy(),
    )
