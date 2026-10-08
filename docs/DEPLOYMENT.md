# Deployment

Current reference topology:

```text
Cloudflare Pages PWA
  -> Render FastAPI backend
  -> Supabase PostgreSQL/Auth
  -> Render worker for outbox/push
```

No secret values belong in this document.

Cloudflare, Render, and Supabase are deployment choices, not permanent architectural requirements. A replacement must preserve PostgreSQL behavior, private JWT verification, the API trust boundary, outbox worker operation, backups, and migration ownership.

## Frontend: Cloudflare Pages

- Project root: repository root.
- Build command: `pnpm install --frozen-lockfile && pnpm --dir apps/web build`
- Output directory: `apps/web/dist`
- SPA fallback: `apps/web/public/_redirects` contains `/* /index.html 200`.
- Required environment variables:
  - `VITE_API_BASE_URL`
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_VAPID_PUBLIC_KEY`
- Rollback: use Cloudflare Pages deployment rollback to a prior successful build.

## Backend: Render Web Service

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Required environment variables:
  - `APP_ENV=production`
  - `DATABASE_URL`
  - `DEVELOPMENT_AUTH_ENABLED=false`
  - `SUPABASE_PROJECT_URL`
  - `SUPABASE_JWT_SECRET`
  - `SUPABASE_JWT_AUDIENCE=authenticated`
  - `AUTHORIZED_AUTH_SUBJECTS`
  - `CORS_ORIGINS`
  - `FRONTEND_BASE_URL`
  - `DEPLOYMENT_VERSION`
  - AI provider variables if non-fake AI is enabled
  - push variables if `PUSH_DELIVERY_MODE=webpush`
- Rollback: roll back the Render deploy. Database downgrades should be avoided unless the downgrade has been rehearsed and is explicitly safe.

## Worker: Render Background Worker

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `python -m app.worker --limit 50 --sleep 5`
- Required environment variables: same backend variables, plus:
  - `PUSH_DELIVERY_MODE`
  - `VAPID_PRIVATE_KEY` when using real Web Push
  - `PUSH_SUBJECT` when using real Web Push

## Database/Auth: Supabase

1. Disable public signup in Supabase Auth.
2. Create the single authorized account.
3. Put its stable Supabase user UUID in `AUTHORIZED_AUTH_SUBJECTS`.
4. Put Supabase project URL in `SUPABASE_PROJECT_URL`.
5. Put the JWT secret in backend/worker `SUPABASE_JWT_SECRET` only.
6. Never expose service-role keys to Cloudflare Pages.

The current backend auth verifier supports Supabase HS256 access tokens only. `SUPABASE_JWT_SECRET` is the JWT signing secret, not a Supabase service/secret API key. Configure `SUPABASE_PROJECT_URL` or the exact `SUPABASE_JWT_ISSUER`; do not configure unused JWKS variables. A deployment using asymmetric/JWKS tokens requires a separately implemented and tested verifier before launch.

## Migration Procedure

1. Take a Supabase snapshot/backup.
2. Verify current revision with `python -m alembic current`.
3. Deploy migration-compatible backend code.
4. Run `python -m alembic upgrade head` from `backend`.
5. Smoke test `/health`, `/readiness`, `/api/v1/me`, plan generation, export, and worker.
6. Observe logs and outbox dead letters.
7. Roll back application if needed. Downgrade the database only after a safe rehearsal.

## Current Status

Deployment was not executed in this workspace because Cloudflare, Render, and Supabase production credentials/access were not available.
