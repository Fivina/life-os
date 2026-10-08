"""Exercise the Life OS 2.0 core against a disposable PostgreSQL database."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATABASE_PREFIX = "life_os_v2_smoke_"
SAMPLE_SIZE = 20


def _admin_url() -> str:
    explicit = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if explicit:
        return explicit
    sys.path.insert(0, str(BACKEND))
    from app.core.config import Settings

    return Settings().database_url


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=BACKEND,
        env=environment,
        check=True,
    )


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _measure(operation, *, samples: int = SAMPLE_SIZE) -> tuple[float, float]:
    durations: list[float] = []
    for _ in range(samples):
        started = perf_counter()
        operation()
        durations.append((perf_counter() - started) * 1000)
    return statistics.median(durations), _percentile(durations, 0.95)


def _configure_test_process(database_url: str) -> None:
    os.environ.update(
        {
            "DATABASE_URL": database_url,
            "AI_ENABLED": "false",
            "LAYA_ENABLED": "false",
            "JEV_ENABLED": "false",
            "DECISION_SHADOW_ENABLED": "false",
            "MOVIE_METADATA_PROVIDER": "disabled",
            "OPPORTUNITY_DISCOVERY_ENABLED": "false",
            "DEVELOPMENT_AUTH_ENABLED": "true",
        }
    )
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app.core.config import get_settings

    get_settings.cache_clear()


def _exercise(database_url: str, *, measure_performance: bool = True) -> dict[str, tuple[float, float]]:
    _configure_test_process(database_url)

    from fastapi.testclient import TestClient

    from app.api.deps import get_or_create_user
    from app.capture.schemas import QuickCaptureCreate
    from app.capture.service import QuickCaptureService
    from app.core.config import Settings
    from app.database.models import (
        ActiveWorkspace,
        Event,
        FinanceTransaction,
        Plan,
        ReviewItem,
        UserProfile,
        WorldRevision,
    )
    from app.main import create_app
    from app.planning.automation import MorningPlanner
    from app.realtime.service import RealtimeStateService
    from app.review.schemas import ReviewAction
    from app.review.service import ReviewQueueService
    from app.self_core.morning import MorningBriefingBuilder
    from app.workspaces.schemas import StudyWorkspacePayload, WorkspaceType
    from app.workspaces.service import ActiveWorkspaceService
    from app.workspaces.situation import GlobalWorkspaceBuilder

    settings = Settings(
        _env_file=None,
        database_url=database_url,
        ai_enabled=False,
        laya_enabled=False,
        jev_enabled=False,
        decision_shadow_enabled=False,
        movie_metadata_provider="disabled",
        opportunity_discovery_enabled=False,
        development_auth_enabled=True,
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    metrics: dict[str, tuple[float, float]] = {}

    try:
        with Session() as db:
            user = get_or_create_user(db, email="v2-release-smoke@life-os.local", auth_subject="v2-release-smoke")
            initial_revision = user.world_revision
            captures = QuickCaptureService(settings)

            finance = captures.capture(
                db,
                user,
                QuickCaptureCreate(text="I paid 18 euros at Rewe."),
                idempotency_key="v2-smoke-finance",
            )
            replay = captures.capture(
                db,
                user,
                QuickCaptureCreate(text="I paid 18 euros at Rewe."),
                idempotency_key="v2-smoke-finance",
            )
            if replay.id != finance.id:
                raise AssertionError("Quick Capture idempotency failed on PostgreSQL.")
            applied = captures.apply(db, user, finance.id)
            if db.get(FinanceTransaction, applied.canonical_entity_id) is None:
                raise AssertionError("Finance capture did not reach canonical storage.")

            uncertain = captures.capture(
                db,
                user,
                QuickCaptureCreate(text="I paid 27.80 euros at Amazon."),
                idempotency_key="v2-smoke-review",
            )
            if not uncertain.review_item_id:
                raise AssertionError("Uncertain Finance capture did not enter Review Queue.")
            queue = ReviewQueueService()
            review = queue.get(db, user, uncertain.review_item_id)
            resolved = queue.resolve(
                db,
                user,
                review.id,
                action=ReviewAction.edit_and_accept,
                edited_values={"category": "Shopping"},
                expected_version=review.version,
            )
            if db.get(FinanceTransaction, resolved.canonical_entity_id) is None:
                raise AssertionError("Reviewed Finance capture did not reach canonical storage.")

            workspace_service = ActiveWorkspaceService()
            workspace = workspace_service.start_workspace(
                db,
                user,
                workspace_type=WorkspaceType.study,
                payload=StudyWorkspacePayload(
                    course_ref="algorithms",
                    topic_ref="shortest-paths",
                    current_question_ref="question:7",
                    current_question_content="Dijkstra question 7",
                    session_phase="practice",
                ),
                current_phase="practice",
                current_step="Question 7",
                idempotency_key="v2-smoke-study",
            )
            plan, created = MorningPlanner().ensure(db, user, timezone_name="Europe/Berlin")
            repeated_plan, repeated_created = MorningPlanner().ensure(db, user, timezone_name="Europe/Berlin")
            if not created or repeated_created or plan.id != repeated_plan.id:
                raise AssertionError("Morning plan generation is not idempotent.")
            first_briefing = MorningBriefingBuilder().build(db, user, timezone="Europe/Berlin")
            second_briefing = MorningBriefingBuilder().build(db, user, timezone="Europe/Berlin")
            if first_briefing.context.plan_id != second_briefing.context.plan_id:
                raise AssertionError("Morning briefing did not reuse canonical plan state.")
            if user.world_revision <= initial_revision:
                raise AssertionError("Canonical writes did not advance WorldRevision.")
            db.commit()
            user_id = user.id
            workspace_id = workspace.id
            last_revision = user.world_revision

        with Session() as fresh:
            user = fresh.get(UserProfile, user_id)
            if user is None:
                raise AssertionError("User did not survive the fresh database session.")
            restored = ActiveWorkspaceService().get_foreground_workspace(fresh, user)
            if restored is None or restored.id != workspace_id:
                raise AssertionError("Foreground workspace did not survive reconstruction.")
            payload = ActiveWorkspaceService().reconstruct_payload(restored)
            if payload.current_question_ref != "question:7":
                raise AssertionError("Typed Study workspace payload was not reconstructed exactly.")

            foreground_count = fresh.scalar(
                select(func.count(ActiveWorkspace.id)).where(
                    ActiveWorkspace.user_id == user.id,
                    ActiveWorkspace.is_foreground.is_(True),
                )
            )
            current_plan_count = fresh.scalar(
                select(func.count(Plan.id)).where(
                    Plan.user_id == user.id,
                    Plan.status == "current",
                    Plan.planning_day == plan.planning_day,
                )
            )
            event_count = fresh.scalar(select(func.count(Event.id)).where(Event.user_id == user.id))
            revision_count = fresh.scalar(select(func.count(WorldRevision.id)).where(WorldRevision.user_id == user.id))
            unresolved_review_count = fresh.scalar(
                select(func.count(ReviewItem.id)).where(
                    ReviewItem.user_id == user.id,
                    ReviewItem.status == "PENDING",
                )
            )
            if foreground_count != 1 or current_plan_count != 1:
                raise AssertionError("PostgreSQL integrity check found duplicate foreground/current state.")
            if not event_count or revision_count != last_revision:
                raise AssertionError("Events and WorldRevision are inconsistent.")
            if unresolved_review_count:
                raise AssertionError("Resolved smoke review remained pending.")

            realtime = RealtimeStateService().changes_since(fresh, user, after_revision=0)
            if realtime.resync_required or realtime.current_revision != last_revision or not realtime.events:
                raise AssertionError("Realtime catch-up did not reproduce committed revision history.")

            if measure_performance:
                metrics["foreground_workspace"] = _measure(
                    lambda: ActiveWorkspaceService().get_foreground_workspace(fresh, user)
                )
                metrics["global_workspace"] = _measure(
                    lambda: GlobalWorkspaceBuilder().build(fresh, user)
                )
                metrics["review_queue"] = _measure(lambda: ReviewQueueService().list(fresh, user))
                metrics["morning_briefing"] = _measure(
                    lambda: MorningBriefingBuilder().build(fresh, user, timezone="Europe/Berlin")
                )
                metrics["realtime_catchup"] = _measure(
                    lambda: RealtimeStateService().changes_since(fresh, user, after_revision=0)
                )
            fresh.rollback()

        with TestClient(create_app(settings)) as client:
            health = client.get("/health")
            readiness = client.get("/readiness")
            if health.status_code != 200 or health.json().get("version") != "2.0":
                raise AssertionError("Application health check did not report Life OS 2.0.")
            if readiness.status_code != 200 or readiness.json().get("status") != "ready":
                raise AssertionError("Application did not become ready on restored PostgreSQL state.")
        return metrics
    finally:
        engine.dispose()


def _validate_restored(database_url: str) -> None:
    _configure_test_process(database_url)

    from fastapi.testclient import TestClient
    from sqlalchemy import inspect

    from app.core.config import Settings
    from app.database.models import ActiveWorkspace, Event, FinanceTransaction, UserProfile, WorldRevision
    from app.main import create_app

    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        tables = set(inspect(engine).get_table_names())
        required = {
            "alembic_version",
            "user_profiles",
            "events",
            "world_revisions",
            "finance_transactions",
            "active_workspaces",
        }
        if not required.issubset(tables):
            raise AssertionError(f"Restored database is missing tables: {sorted(required - tables)}")
        with Session() as db:
            user = db.scalar(select(UserProfile).where(UserProfile.auth_subject == "v2-release-smoke"))
            if user is None:
                raise AssertionError("Restored database is missing the release-smoke user.")
            finance_count = db.scalar(select(func.count(FinanceTransaction.id)).where(FinanceTransaction.user_id == user.id))
            foreground_count = db.scalar(select(func.count(ActiveWorkspace.id)).where(
                ActiveWorkspace.user_id == user.id,
                ActiveWorkspace.is_foreground.is_(True),
            ))
            event_count = db.scalar(select(func.count(Event.id)).where(Event.user_id == user.id))
            revision_count = db.scalar(select(func.count(WorldRevision.id)).where(WorldRevision.user_id == user.id))
            if finance_count != 2 or foreground_count != 1:
                raise AssertionError("Restored canonical Finance/workspace state is incomplete.")
            if not event_count or revision_count != user.world_revision:
                raise AssertionError("Restored Events and WorldRevision are inconsistent.")

        settings = Settings(
            _env_file=None,
            database_url=database_url,
            ai_enabled=False,
            laya_enabled=False,
            jev_enabled=False,
            development_auth_enabled=True,
        )
        with TestClient(create_app(settings)) as client:
            readiness = client.get("/readiness")
            if readiness.status_code != 200 or readiness.json().get("status") != "ready":
                raise AssertionError("Life OS did not start against the restored database.")
        print(
            "Restored database validated: "
            f"finance_transactions={finance_count} foreground_workspaces={foreground_count} "
            f"events={event_count} world_revisions={revision_count}."
        )
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", action="store_true", help="Exercise DATABASE_URL without creating or dropping it.")
    parser.add_argument("--validate-restored", action="store_true", help="Validate a restored DATABASE_URL without writing to it.")
    parser.add_argument("--skip-performance", action="store_true", help="Skip latency sampling during an existing-database seed run.")
    args = parser.parse_args()

    if args.validate_restored:
        _validate_restored(_admin_url())
        return 0
    if args.existing:
        metrics = _exercise(_admin_url(), measure_performance=not args.skip_performance)
        print("Existing PostgreSQL database integration smoke passed.")
        for name, (p50, p95) in metrics.items():
            print(f"PERF {name}: n={SAMPLE_SIZE} p50={p50:.2f}ms p95={p95:.2f}ms")
        return 0

    admin_url = _admin_url()
    parsed = make_url(admin_url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("The v2.0 integration smoke requires a PostgreSQL admin URL.")

    database_name = f"{DATABASE_PREFIX}{uuid4().hex[:12]}"
    if not re.fullmatch(r"life_os_v2_smoke_[a-f0-9]{12}", database_name):
        raise RuntimeError("Refusing to use an unsafe disposable database name.")
    database_url = parsed.set(database=database_name).render_as_string(hide_password=False)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    created = False
    print(f"Creating disposable PostgreSQL database {database_name}")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        created = True
        _run_alembic(database_url, "upgrade", "head")
        metrics = _exercise(database_url)
        print("PostgreSQL canonical-state, restart, idempotency, realtime, and startup smoke passed.")
        for name, (p50, p95) in metrics.items():
            print(f"PERF {name}: n={SAMPLE_SIZE} p50={p50:.2f}ms p95={p95:.2f}ms")
        return 0
    finally:
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            print(f"Dropped disposable PostgreSQL database {database_name}")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
