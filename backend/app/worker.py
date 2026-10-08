from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import text

from app.database.session import SessionLocal
from app.ai.gateway import AIGateway
from app.core.config import get_settings
from app.events.outbox import process_pending_outbox
from app.memory.consolidation import MemoryConsolidator
from app.memory.embeddings import EmbeddingService
from app.memory.jobs import MemoryJobProcessor
from app.memory.learning_bridge import LearningBridgeService
from app.notifications.service import PushOutboxHandler
from app.planning.automation import MorningPlanner
from app.domains.orchestration import DomainOutboxHandler
from app.standing_calendar.service import FixtureSyncWorker
from app.social.service import OpportunityDiscoveryWorker

logger = logging.getLogger("life_os.worker")


def run_once(limit: int) -> int:
    with SessionLocal() as db:
        processed = process_pending_outbox(db, DomainOutboxHandler(db, PushOutboxHandler(db)), limit=limit)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(text("select set_config('app.worker', 'true', true)"))
        settings = get_settings()
        memory_jobs = MemoryJobProcessor(settings).process_pending(db, limit=limit)
        consolidator = MemoryConsolidator(settings, EmbeddingService(settings, AIGateway(settings)))
        consolidated = consolidator.consolidate_due(db)
        bridge_snapshots = LearningBridgeService().refresh_due(db)
        morning_plans = MorningPlanner().run_due(db)
        fixture_rules = FixtureSyncWorker().run_due(db, limit=limit)
        opportunity_sources = OpportunityDiscoveryWorker(settings).run_due(db, limit=limit)
        db.commit()
        logger.info("worker_cycle", extra={"outbox_processed": processed, "memory_jobs_processed": memory_jobs, "users_consolidated": consolidated, "learning_bridge_snapshots": bridge_snapshots, "morning_plans_generated": morning_plans, "fixture_rules_synced": fixture_rules, "opportunity_sources_synced": opportunity_sources})
        return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Life OS outbox worker")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=5.0)
    args = parser.parse_args()

    if args.once:
        run_once(args.limit)
        return

    while True:
        run_once(args.limit)
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
