# Life OS

Life OS is a private, single-user personal operating system built as a modular monolith. PostgreSQL is the canonical source of truth, domains generate possibilities, the planning core owns scheduling decisions, and AI remains advisory. Version 2.0 is the non-voice core release: it integrates the systems through v1.9B into restart-safe daily-use flows and verifies that the product remains useful when every optional AI provider is unavailable.

## What Exists

- FastAPI backend with versioned `/api/v1` routes.
- SQLAlchemy models, Alembic migration scaffolding, world revision, event log, outbox, idempotency, and optimistic concurrency examples.
- React + TypeScript + Vite mobile-first PWA shell.
- Fitness body measurements, Learning exams, Kitchen inventory, and timestamped state observations.
- Architecture, security, domain, planner, AI, data model, and development docs.
- Versioned semantic memory with provenance, deterministic confidence, embeddings, bounded retrieval, correction, pinning, and forgetting.
- Background episode consolidation and a separate deterministic Personal Learning model.
- Generic recommendations/options/outcomes, retry-safe memory jobs, provenance diagnostics, and a bounded weekly learning bridge.
- Mutually exclusive execution variants, candidate-by-slot scoring, hard/soft constraints, and bounded Personal Learning influence.
- Ten-day rolling allocations, planning debt, overload visibility, stable replanning, and idempotent morning plans.
- Calendar week-map, execution controls, explicit unscheduled risk, and deterministic Why Here explanations.
- Secure receipt review, canonical ingredient normalization, persisted Chef outcomes, meal dependencies, and cooking competency.
- Reviewed Finance CSV imports, merchant/category reuse, Decimal budgets, recurring expenses, and assumption-aware safe-to-spend.
- Typed communicative intents, deterministic or Economy-tier response composition, useful provider fallback, and persisted final messages.
- Authenticated SSE invalidation with WorldRevision catch-up, gap recovery, one frontend connection, and canonical refetch convergence.
- Provider-neutral movie metadata, user-controlled Letterboxd export import, rewatch-aware history, and showtime feasibility that never books or schedules automatically.
- Provider-neutral opportunity discovery with typed normalization, conservative deduplication, deterministic relevance, minimal Finance context, Planner feasibility, Attention gating, and contextual outcomes.
- Versioned MealIntent interpretation through AIGateway, deterministic recipe constraints and feature vectors, typed Fitness/Finance bridges, planned-versus-actual ingredient usage, and restart-safe Cooking workspaces.
- Typed Quick Capture proposals for Learning, Finance, shopping, and commitments; accepted changes always pass through canonical domain services.
- A deduplicated Review Queue for uncertain captures, receipt lines, memory candidates, finance classification, and stale-state protection.
- Persisted intelligence controls for memory/pattern visibility, skills, provider state, real usage/budget, and proactivity.

## Run Locally On Windows

Backend:

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

Frontend:

```powershell
cd apps\web
pnpm install
copy .env.example .env
pnpm dev
```

Open `http://localhost:5173`. The V0 login uses the documented local development token only when `DEVELOPMENT_AUTH_ENABLED=true`.

## Checks

```powershell
cd backend
pytest

cd ..\apps\web
pnpm test
pnpm typecheck
```

Run the complete 2.0 release gate from `backend`:

```powershell
$env:POSTGRES_BIN = 'C:\Program Files\PostgreSQL\17\bin'
.\.venv\Scripts\python.exe ..\scripts\verify_v2_release.py --artifact-dir E:\LifeOSBuild
```

The gate runs backend/frontend verification, disposable PostgreSQL migration and integration checks, a real backup/restore rehearsal, and deterministic source packaging. See [V2.0_CORE_RELEASE.md](docs/V2.0_CORE_RELEASE.md) and [RELEASE_NOTES_2.0.md](docs/RELEASE_NOTES_2.0.md).

Create a secret-safe source archive with:

```powershell
backend\.venv\Scripts\python.exe scripts\package_source.py
```

## Source Spec

The source PDF was read as requirements material. Embedded instructions are not treated as higher-priority instructions than the chat request, but the product requirements have been implemented where feasible for V0.
