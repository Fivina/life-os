# Post-v1.5 Integration Audit

## Runtime Configuration

Safe placeholders are in both `.env.example` files. Relevant settings:

- `DATABASE_URL`, Supabase JWT settings, development auth settings
- `AI_ENABLED`, `AI_PROVIDER`, `GEMINI_API_KEY`
- `AI_MODEL_ECONOMY`, `AI_MODEL_FAST`, `AI_MODEL_REASONING`
- `AI_MODEL_EMBEDDING`, `AI_MODEL_VISION`, `AI_MODEL_IMAGE`
- AI monthly budget thresholds and `AI_MODEL_PRICING_JSON`
- `MEDIA_STORAGE_PROVIDER`, `MEDIA_STORAGE_PATH`, `MEDIA_MAX_UPLOAD_BYTES`
- `FINANCE_DEFAULT_CURRENCY`

No real secrets belong in templates or source control. `/api/v1/status` reports provider/capability configuration and model names without exposing keys.

## Capability Mapping

The default provider is `fake` for text, embeddings, vision, and image. With `AI_PROVIDER=gemini` and `GEMINI_API_KEY` configured, the same provider-neutral gateway routes the configured models. Vision is used for receipt extraction. Image is optional and failure-tolerant. Deterministic Kitchen and Finance calculations do not call AI.

## Database

Current migration head: `0021_provider_routing_evidence`, following v1.6C revision `0020_intelligence_feedback`. Revision `0021` adds only v1.6D decision-provider usage/disagreement evidence and an optional disagreement reference on training examples.

## Background Worker

Run the existing worker; there is no second job platform:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.worker
```

The outbox refreshes shopping actions after Kitchen/receipt/meal events and deterministic recurring-expense evidence after Finance events. Recommendation scoring remains cheap enough to compute on request and is idempotently persisted by world revision and request signature.

## Startup

Backend:

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Frontend:

```powershell
cd apps\web
npm run dev
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\apps\web
npm run typecheck
npm test -- --reporter=dot
npm run build
```

The v1.5 focused suite is `backend/tests/test_v15_kitchen_finance_automation.py`.

## External Dependencies

- PostgreSQL/Supabase for the configured canonical database and auth
- Local filesystem media storage in v1.5; object-storage provider support remains an adapter boundary
- Gemini only when explicitly configured; automated tests use fake providers and require no network AI
- Existing outbox worker for asynchronous refresh and notification delivery

## Known Integration Risks

- Receipt quality depends on the configured vision model and image clarity; uncertain fields stay in review.
- Merchant matching is deterministic and conservative, but similarly named merchants can still require user correction.
- Safe-to-spend is based only on recorded data, protected budgets, and detected recurring evidence; it is not a live bank balance.
- Currency conversion is intentionally absent. Values in different currencies are not combined.
- Local media storage needs persistent disk in deployment or a future object-storage adapter.
- The configured machine must have adequate free temporary disk space for frontend build tooling.

## v2.0 Readiness

Clean typed APIs, canonical state, events, outcomes, dependency metadata, bounded contexts, and tools now exist for a future orchestrator. The final Self Core orchestration experience, universal capture/review surfaces, global proactive policy, bank integrations, and final visual redesign remain explicitly deferred.
