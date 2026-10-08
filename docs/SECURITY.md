# Security

Life OS is private and single-user, but the backend still validates authentication independently from the frontend.

## Rules

- No secrets in frontend code.
- No secrets committed to Git.
- Supabase service-role or secret API keys stay server-side only and are not required by the browser.
- Public sign-up is not exposed in the UI.
- Backend routes require bearer authentication unless explicitly public, such as health.
- CORS must not allow every origin in production.
- Production and debug configuration are separated.
- No arbitrary SQL endpoints.
- No AI API keys in browser code.
- Logs must avoid secrets and sensitive message contents.

## Development Auth

`DEVELOPMENT_AUTH_ENABLED=true` allows the local token in `.env.example`. The settings layer refuses to start production with development auth enabled.

## V1.0 Production Auth

Production uses Supabase-issued JWTs. The backend verifies bearer tokens independently with the configured JWT secret, issuer, audience, expiry, and signature. The stable JWT `sub` is mapped to `UserProfile.auth_subject`; frontend-provided `user_id` is ignored. `AUTHORIZED_AUTH_SUBJECTS` enforces the private single-user allowlist.

The implemented verifier accepts HS256 only. `SUPABASE_JWT_SECRET` must contain the JWT signing secret; it must not be populated with a Supabase service/secret API key. `SUPABASE_PROJECT_URL` derives the expected issuer unless `SUPABASE_JWT_ISSUER` is explicitly set. JWKS/asymmetric verification is not implemented and is therefore not a supported production configuration.

No token or invalid token returns `401`. A valid but non-allowlisted Supabase user returns `403`.

## V1.0 Export And Push

`GET /api/v1/export` is authenticated and omits auth subjects, service secrets, push endpoints, and push cryptographic keys. Push subscription routes require auth and enforce subscription ownership. Notification delivery is routed through Outbox and idempotent `push_deliveries`.

## Database Exposure And RLS

The browser calls Supabase Auth endpoints but does not query Life OS tables through PostgREST/Data API. Domain data is accessed through FastAPI, which verifies the JWT/allowlist and scopes service queries to the internal user id.

Migration `0030_supabase_data_api_lockdown` enables RLS on existing tables in `public`, revokes table and sequence privileges from `PUBLIC`, `anon`, `authenticated`, and `service_role`, and removes those default grants for objects created by the migration role. No client policies are created: direct Data API access is intentionally unsupported. New public tables must continue to enable RLS, and any future direct-client access requires reviewed, tested policies and explicit least-privilege grants.

The backend uses direct PostgreSQL access and remains the trusted data boundary. In the connected Supabase project, the current connection role was observed as `postgres`, which bypasses RLS and has broad database privileges. Keep that credential server-side only; before hosting the backend publicly, provision a dedicated least-privilege runtime role and update the deployment connection string. RLS/Data API hardening does not reduce the authority of the `postgres` role.

## Provider Credentials

Provider API keys are stored in Supabase Vault, not in application tables or browser storage. Migrations `0028` and `0029` install/verify Vault-backed functions in the non-exposed `private` schema for OpenAI, Gemini, and Jev. The authenticated FastAPI route sets the verified internal user id as transaction-local database context before a secret operation. The UI receives only whether a credential is configured; key values are write-only and are not returned by the API. Never log submitted key values.
