# Operations Runbook

## Health And Readiness

- Process health: `GET /health`
- Dependency readiness: `GET /readiness`
- Authenticated identity: `GET /api/v1/me`

Health returns no user data. Readiness checks database connectivity and auth configuration only.

## Deploy Frontend

Use Cloudflare Pages with the settings in `docs/DEPLOYMENT.md`. Confirm nested routes refresh correctly after deployment.

## Deploy Backend

Use Render web service. Confirm `/health`, `/readiness`, CORS, and `/api/v1/me` from the hosted frontend origin.

## Run Migration

```powershell
cd backend
python -m alembic current
python -m alembic upgrade head
python -m alembic current
```

Always back up first.

## Worker Health

Run as a background worker:

```powershell
python -m app.worker --limit 50 --sleep 5
```

One-shot diagnostic:

```powershell
python -m app.worker --once --limit 50
```

## Inspect Outbox / Dead Letters

Check `outbox_events` for `retry` and `dead_letter` statuses. Important fields: `event_type`, `attempts`, `last_error`, `available_at`, `processed_at`.

## Auth Troubleshooting

- `401`: missing, malformed, expired, wrong issuer/audience/signature.
- `403`: valid Supabase token but subject not in `AUTHORIZED_AUTH_SUBJECTS`.
- Production startup failure: check `DEVELOPMENT_AUTH_ENABLED=false`, `SUPABASE_JWT_SECRET`, and `AUTHORIZED_AUTH_SUBJECTS`.

## Push Troubleshooting

- Permission denied: browser setting, not a backend failure.
- Missing VAPID public key: frontend cannot subscribe.
- `no_active_subscription`: user has not enabled reminders or subscription was revoked/dead.
- Dead subscription: failure count reached threshold; user should re-enable reminders.

## AI Provider Troubleshooting

V1.0 defaults to the fake provider. If enabling a real provider later, keep keys server-side and verify Assistant still uses registered tools only.

## DB Outage Behavior

Readiness should degrade/fail. User-facing mutations must not show success when the API request fails.

## Rollback

1. Roll back frontend deployment if UI-only.
2. Roll back backend deployment if API-only.
3. Keep database at newer revision unless a rehearsed downgrade is safe.
4. If worker causes delivery issues, pause worker first.

## Backup

Use Supabase backup/snapshot before deployments and migrations. See `docs/OPERATIONS_BACKUP_RESTORE.md`.

## Export

Authenticated export endpoint: `GET /api/v1/export`. See `docs/DATA_EXPORT.md`.

## Incident Notes

Record incident time, deployed versions, symptoms, affected routes, outbox status, mitigation, and follow-up tests.
