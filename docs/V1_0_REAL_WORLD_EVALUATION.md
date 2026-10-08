# V1.0 Real-World Evaluation

Status: PENDING

V1.0 final PASS requires actual use. Automated tests and local smoke checks are not enough.

## Evaluation Period

Minimum: 7 consecutive days after hosted frontend, hosted backend, production Supabase Auth/Postgres, and worker are available.

Preferred: 14 consecutive days.

## Track Daily

- days actually used
- state check-ins
- plan generations
- replans
- blocks started/completed/skipped/missed
- hard-commitment conflicts
- duplicate mutations
- network failures
- auth failures
- crashes
- outbox failures
- notification usefulness
- manual rescheduling burden
- unnecessary large replans
- backlog growth after disruption
- perceived planning burden
- Fitness/Learning/Kitchen/Assistant friction
- export/backup confidence

## Allowed During Evaluation

- bug fixes
- reliability fixes
- security fixes
- UX corrections
- calibration fixes

## Not Allowed During Evaluation

- V1.1 Memory
- Personal Knowledge Graph
- embeddings/vector retrieval
- new external integrations
- finance/markets
- new autonomous agent capabilities

## Final PASS Criteria

- hosted Life OS usable without development PC
- login reliable
- critical data survives refresh/restart
- no unresolved duplicate mutation issue
- no unresolved backlog avalanche behavior
- planner/replanning remains bounded
- major UX blockers fixed
- auth reliable
- export/backup path credible
- network failures do not show false success
- notifications, if enabled, are not spammy
- planning burden is meaningfully lower than manual maintenance
