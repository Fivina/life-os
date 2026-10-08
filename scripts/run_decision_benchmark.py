"""Run the versioned synthetic Life OS decision benchmark and write JSON output."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import Settings  # noqa: E402
from app.decision.benchmark import run_provider_benchmark  # noqa: E402
from app.decision.providers.fake import FakeDecisionProvider  # noqa: E402
from app.decision.providers.jev import JevProvider  # noqa: E402
from app.decision.providers.laya import LayaLocalProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / ".cache" / "benchmarks" / "life-os-decisions-v1.json"),
    )
    args = parser.parse_args()
    settings = Settings()
    providers = [FakeDecisionProvider()]
    laya = LayaLocalProvider(settings)
    jev = JevProvider(settings)
    if laya.capabilities().available:
        providers.append(laya)
    if jev.capabilities().available:
        providers.append(jev)
    try:
        report = run_provider_benchmark(tuple(providers))
    finally:
        jev.close()
    destination = Path(args.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote {destination} ({len(report.results)} provider-case results).")


if __name__ == "__main__":
    main()
