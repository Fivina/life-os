# Development

## Backend

```powershell
docker compose up -d postgres
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000/api/v1`.

## Frontend

```powershell
cd apps\web
pnpm install
copy .env.example .env
pnpm dev
```

The PWA is available at `http://localhost:5173`.

## Tests

```powershell
cd backend
pytest

cd ..\apps\web
pnpm test
pnpm typecheck
```

## v2.0 Release Gate

The complete release check reuses the normal test suites and named golden-scenario manifest. It also creates isolated PostgreSQL databases for migration, service integration, and backup/restore checks; it never points destructive operations at the configured database itself.

```powershell
cd backend
$env:POSTGRES_BIN = 'C:\Program Files\PostgreSQL\17\bin'
.\.venv\Scripts\python.exe ..\scripts\verify_v2_release.py --artifact-dir E:\LifeOSBuild
```

`POSTGRES_BIN` must contain `pg_dump` and `pg_restore` from a client version at least as new as the server. `TEST_POSTGRES_ADMIN_URL` is optional; when omitted, the configured `DATABASE_URL` supplies the server and credentials used only to create uniquely named disposable databases. Use `--quick --skip-migrations` for a fast local code check; that mode is not a release acceptance run.

The clean-install harness uses pnpm's hoisted linker so its temporary checkout also works on exFAT cache drives, which do not support the symlinks used by pnpm's default isolated linker.

Migration history has a separate PostgreSQL integrity harness. It creates a uniquely named disposable database, upgrades to head, compares migrated table/column ownership with the ORM, downgrades to base, re-upgrades, and drops the database:

```powershell
.\.venv\Scripts\python.exe ..\scripts\verify_migrations.py
```

Run the command from `backend`, or invoke `scripts\verify_migrations.py` with the backend virtual-environment Python from the repository root. `TEST_POSTGRES_ADMIN_URL` can provide a dedicated admin connection; otherwise the configured `DATABASE_URL` is used only to create and remove the isolated test database.

## Source Package

Create a deterministic source-only archive from the repository root:

```powershell
backend\.venv\Scripts\python.exe scripts\package_source.py
```

The archive is written under `.cache\build` by default. Real environment files, virtual environments, dependencies, build output, caches, logs, bytecode, and temporary databases are excluded. Environment example files remain included.

## Decision Provider Benchmark

The v1.6D benchmark runs the versioned synthetic task-family dataset with Fake and any explicitly enabled/available real providers. Its routing profile is a review-only candidate and never changes runtime configuration:

```powershell
backend\.venv\Scripts\python.exe scripts\run_decision_benchmark.py
```

## Optional Local Database Modes

PostgreSQL is canonical. Use Docker Compose for local parity. Tests use in-memory SQLite to keep feedback fast; app development should use PostgreSQL when validating database behavior.

## OpenAPI

FastAPI publishes OpenAPI at `/openapi.json`. A future milestone can generate TypeScript contracts from this file instead of duplicating schemas manually.
