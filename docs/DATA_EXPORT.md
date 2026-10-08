# Data Export

Life OS provides an authenticated JSON export:

```text
GET /api/v1/export
```

The route requires the same bearer authentication as private API routes.

## Contents

The export includes:

- manifest with export schema version, app version, environment, and timestamp
- user profile metadata excluding `auth_subject`
- State observations
- Commitments and Actions
- Plans and PlanBlocks
- Events and WorldRevisions
- Assistant proposals/audits
- Fitness records
- Learning records
- Kitchen records
- Personal Learning examples, models, patterns, and refresh runs
- Semantic memories, evidence, episodes, recommendation outcomes, and consolidation runs
- Notification intents
- Push delivery metadata

## Redactions

Push subscription endpoint and cryptographic keys are not exported. Raw embedding vectors are also omitted; provider/model/dimension/version metadata remains available so memories can be inspected. Service secrets, database credentials, JWT secrets, VAPID private key, and AI provider keys are never part of the export.

## Current Verification

Automated tests verify `GET /api/v1/export` returns the backward-compatible `life-os-export-v1` envelope and user-scoped tables when authenticated, and returns `401` without auth.
