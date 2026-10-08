from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url


REPOSITORY_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPOSITORY_DIR / "backend"
DATABASE_PREFIX = "life_os_migration_test_"
EXPECTED_HEAD = "0027_capture_review_settings"
IMPORTANT_TABLES = {
    "user_profiles",
    "events",
    "outbox_events",
    "world_revisions",
    "plans",
    "plan_blocks",
    "memory_items",
    "kitchen_inventory_items",
    "finance_transactions",
    "cognitive_traces",
    "decision_audits",
    "active_workspaces",
    "attention_items",
    "open_threads",
    "prospective_threads",
    "feedback_sessions",
    "feedback_responses",
    "decision_training_examples",
    "decision_disagreements",
    "decision_provider_usage",
    "plan_proposals",
    "notebook_entries",
    "notebook_promotions",
    "standing_calendar_rules",
    "fixture_bindings",
    "leisure_trajectories",
    "movies",
    "movie_external_ids",
    "movie_watchlist_items",
    "movie_viewings",
    "social_activities",
    "opportunities",
    "opportunity_external_ids",
    "opportunity_source_states",
    "opportunity_user_states",
    "quick_captures",
    "review_items",
    "user_intelligence_settings",
}
CANONICAL_FOREIGN_KEYS = {
    "kitchen_inventory_items": {"fk_kitchen_inventory_items_ingredient_id"},
    "kitchen_meal_history": {
        "fk_kitchen_meal_history_recommendation_id",
        "fk_kitchen_meal_history_recommendation_option_id",
        "fk_kitchen_meal_history_meal_plan_id",
    },
    "kitchen_recipe_ingredients": {"fk_kitchen_recipe_ingredients_ingredient_id"},
    "kitchen_shopping_needs": {
        "fk_kitchen_shopping_needs_meal_plan_id",
        "fk_kitchen_shopping_needs_action_id",
    },
}


def _admin_url() -> str:
    explicit = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if explicit:
        return explicit
    sys.path.insert(0, str(BACKEND_DIR))
    from app.core.config import Settings

    return Settings().database_url


def _alembic(test_url: str, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = test_url
    command = [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments]
    try:
        completed = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = "\n".join(part.strip() for part in (exc.stdout, exc.stderr) if part and part.strip())
        if output:
            print(output)
        raise
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if output:
        print(output)
    return output


def _assert_schema(test_url: str) -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    from app.database import models  # noqa: F401
    from app.database.base import Base

    engine = create_engine(test_url)
    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        expected_tables = set(Base.metadata.tables)
        if actual_tables != expected_tables:
            missing = sorted(expected_tables - actual_tables)
            unexpected = sorted(actual_tables - expected_tables)
            raise AssertionError(f"ORM/migration table mismatch; missing={missing}, unexpected={unexpected}")
        if not IMPORTANT_TABLES.issubset(actual_tables):
            raise AssertionError(f"Important tables missing: {sorted(IMPORTANT_TABLES - actual_tables)}")
        for table_name in sorted(expected_tables):
            actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
            expected_columns = set(Base.metadata.tables[table_name].columns.keys())
            if actual_columns != expected_columns:
                raise AssertionError(
                    f"Column mismatch for {table_name}; "
                    f"missing={sorted(expected_columns - actual_columns)}, "
                    f"unexpected={sorted(actual_columns - expected_columns)}"
                )
        for table_name, expected_names in CANONICAL_FOREIGN_KEYS.items():
            actual_names = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)}
            if not expected_names.issubset(actual_names):
                raise AssertionError(
                    f"Foreign-key names missing on {table_name}: {sorted(expected_names - actual_names)}"
                )
    finally:
        engine.dispose()


def _assert_decision_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"cognitive_traces", "decision_audits"} & tables
        if unexpected:
            raise AssertionError(f"v1.6A tables unexpectedly exist at revision 0017: {sorted(unexpected)}")
    finally:
        engine.dispose()


def _assert_v16b_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"active_workspaces", "attention_items", "open_threads", "prospective_threads"} & tables
        if unexpected:
            raise AssertionError(f"v1.6B tables unexpectedly exist at revision 0018: {sorted(unexpected)}")
    finally:
        engine.dispose()


def _assert_v16c_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"feedback_sessions", "feedback_responses", "decision_training_examples"} & tables
        if unexpected:
            raise AssertionError(f"v1.6C tables unexpectedly exist at revision 0019: {sorted(unexpected)}")
    finally:
        engine.dispose()


def _assert_v16d_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        unexpected = {"decision_disagreements", "decision_provider_usage"} & tables
        if unexpected:
            raise AssertionError(f"v1.6D tables unexpectedly exist at revision 0020: {sorted(unexpected)}")
        training_columns = {column["name"] for column in inspector.get_columns("decision_training_examples")}
        if "decision_disagreement_id" in training_columns:
            raise AssertionError("v1.6D training-example link unexpectedly exists at revision 0020.")
    finally:
        engine.dispose()


def _assert_v17a_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        if "plan_proposals" in tables:
            raise AssertionError("v1.7A plan proposals unexpectedly exist at revision 0021.")
    finally:
        engine.dispose()


def _assert_v18a_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"notebook_entries", "notebook_promotions", "standing_calendar_rules", "fixture_bindings"} & tables
        if unexpected:
            raise AssertionError(f"v1.8A tables unexpectedly exist at revision 0022: {sorted(unexpected)}")
    finally:
        engine.dispose()


def _assert_v18c_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"social_activities", "opportunities", "opportunity_external_ids", "opportunity_source_states", "opportunity_user_states"} & tables
        if unexpected:
            raise AssertionError(f"v1.8C tables unexpectedly exist at revision 0024: {sorted(unexpected)}")
    finally:
        engine.dispose()


def _assert_v18d_columns_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        inspector = inspect(engine)
        meal_plan_columns = {column["name"] for column in inspector.get_columns("kitchen_meal_plans")}
        meal_history_columns = {column["name"] for column in inspector.get_columns("kitchen_meal_history")}
        unexpected = {"planned_ingredients_json", "modifications_json"} & meal_plan_columns
        if unexpected or "actual_usage_json" in meal_history_columns:
            raise AssertionError("v1.8D columns unexpectedly exist at revision 0025")
    finally:
        engine.dispose()


def _assert_v19b_tables_absent(test_url: str) -> None:
    engine = create_engine(test_url)
    try:
        tables = set(inspect(engine).get_table_names())
        unexpected = {"quick_captures", "review_items", "user_intelligence_settings"} & tables
        if unexpected:
            raise AssertionError(f"v1.9B tables unexpectedly exist at revision 0026: {sorted(unexpected)}")
    finally:
        engine.dispose()


def main() -> int:
    admin_url = _admin_url()
    parsed_admin_url = make_url(admin_url)
    if parsed_admin_url.get_backend_name() != "postgresql":
        raise RuntimeError("Migration verification requires a PostgreSQL admin URL.")

    database_name = f"{DATABASE_PREFIX}{uuid4().hex[:12]}"
    if not re.fullmatch(r"life_os_migration_test_[a-f0-9]{12}", database_name):
        raise RuntimeError("Refusing to use an unsafe disposable database name.")
    test_url = parsed_admin_url.set(database=database_name).render_as_string(hide_password=False)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created = False

    print(f"Creating disposable PostgreSQL database {database_name}")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        created = True

        heads = _alembic(test_url, "heads")
        head_lines = [line for line in heads.splitlines() if line.endswith("(head)")]
        if head_lines != [f"{EXPECTED_HEAD} (head)"]:
            raise AssertionError(f"Expected one Alembic head {EXPECTED_HEAD}, received {head_lines}")

        _alembic(test_url, "upgrade", "0017_repository_integrity")
        _assert_decision_tables_absent(test_url)
        print("Repaired v1.5 schema reached revision 0017 without v1.6A tables.")

        _alembic(test_url, "upgrade", "0018_decision_infrastructure")
        _assert_v16b_tables_absent(test_url)
        print("v1.6A schema reached revision 0018 without v1.6B tables.")

        _alembic(test_url, "upgrade", "0019_workspace_attention_threads")
        _assert_v16c_tables_absent(test_url)
        print("v1.6B schema reached revision 0019 without v1.6C tables.")

        _alembic(test_url, "upgrade", "0020_intelligence_feedback")
        _assert_v16d_tables_absent(test_url)
        print("v1.6C schema reached revision 0020 without v1.6D tables.")

        _alembic(test_url, "upgrade", "0021_provider_routing_evidence")
        _assert_v17a_tables_absent(test_url)
        print("v1.6D schema reached revision 0021 without v1.7A tables.")

        _alembic(test_url, "upgrade", "0022_strategic_plan_proposals")
        _assert_v18a_tables_absent(test_url)
        print("v1.7A schema reached revision 0022 without v1.8A tables.")

        _alembic(test_url, "upgrade", "0024_leisure_movies")
        _assert_v18c_tables_absent(test_url)
        print("v1.8B schema reached revision 0024 without v1.8C tables.")

        _alembic(test_url, "upgrade", "0025_social_opportunities")
        _assert_v18d_columns_absent(test_url)
        print("v1.8C schema reached revision 0025 without v1.8D columns.")

        _alembic(test_url, "upgrade", "0026_chef_meal_intent")
        _assert_v19b_tables_absent(test_url)
        print("v1.9A schema reached revision 0026 without v1.9B tables.")

        _alembic(test_url, "upgrade", "head")
        current = _alembic(test_url, "current")
        if EXPECTED_HEAD not in current:
            raise AssertionError(f"Alembic current did not report {EXPECTED_HEAD}")
        _assert_schema(test_url)
        print("Schema matches current ORM table and column ownership.")

        _alembic(test_url, "downgrade", "0026_chef_meal_intent")
        _assert_v19b_tables_absent(test_url)
        _alembic(test_url, "upgrade", "head")
        _assert_schema(test_url)
        print("v1.9B downgrade to v1.9A and re-upgrade completed successfully.")

        _alembic(test_url, "downgrade", "0025_social_opportunities")
        _assert_v18d_columns_absent(test_url)
        _alembic(test_url, "upgrade", "head")
        _assert_schema(test_url)
        print("v1.8D downgrade to v1.8C and re-upgrade completed successfully.")

        _alembic(test_url, "downgrade", "0022_strategic_plan_proposals")
        _assert_v18a_tables_absent(test_url)
        _alembic(test_url, "upgrade", "head")
        _assert_schema(test_url)
        print("v1.8A downgrade to v1.7A and re-upgrade completed successfully.")

        _alembic(test_url, "downgrade", "base")
        _alembic(test_url, "upgrade", "head")
        _assert_schema(test_url)
        print("Disposable downgrade-to-base and re-upgrade completed successfully.")
        return 0
    finally:
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            print(f"Dropped disposable PostgreSQL database {database_name}")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
