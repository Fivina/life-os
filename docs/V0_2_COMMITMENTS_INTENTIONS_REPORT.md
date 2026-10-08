# Life OS V0.2 - Commitments & Intentions

## 1. Release Purpose

V0.2 establishes canonical fixed reality and flexible demand before any planner exists. It lets Life OS store hard/semi-fixed commitments, store flexible unscheduled actions, detect hard commitment conflicts, project commitments into Calendar, and keep flexible work in a Planning Pool.

## 2. Preconditions

V0.1 State remains intact:

- `StateObservation` persists energy and mental state.
- `state.observed` events, `OutboxEvent`, and `WorldRevision` still work.
- Home still retrieves latest state.

## 3. Repository Audit Findings

Backend audit:

- `Commitment`, `Action`, and `Constraint` already existed.
- `Commitment` was minimal: title, start/end, status, source, notes.
- `Action` was minimal: domain, title, status, estimated minutes, metadata.
- Optimistic concurrency existed through `version`.
- Idempotency existed through `IdempotencyRecord`.
- Events, transactional outbox, and world revision existed through `append_event`.
- Development single-user ownership existed through `get_current_user`.
- Datetime fields already used SQLAlchemy timezone-aware columns, though SQLite tests lose timezone metadata on roundtrip.

Frontend audit:

- Calendar page was a placeholder.
- API client existed in `apps/web/src/services/api.ts`.
- Dark premium mobile-first layout existed.
- No modal/drawer component system existed, so V0.2 uses inline compact forms.

Test audit:

- V0.1 backend and frontend tests existed.
- Commitment concurrency had a small example test.
- No Action, calendar projection, overlap, or planning-pool tests existed.

## 4. Planned Scope

- Canonical commitments.
- Canonical flexible actions/intentions.
- Commitment levels and hard/semi-fixed/flexible distinction.
- Status transitions.
- Hard commitment overlap detection.
- Calendar projection endpoint.
- Planning Pool UI.
- Tests and migration.

## 5. Implemented Scope

- Expanded `Commitment` and `Action` models.
- Added Alembic migration `0002_commitments_intentions`.
- Replaced commitment routes with full V0.2 API behavior.
- Added action routes.
- Added calendar projection route.
- Updated Calendar UI with add commitment, add intention, projection timeline, planning pool, conflict/error states, and status action.
- Added backend and frontend tests.

## 6. Deliberately Deferred Scope

- Planner-generated PlanBlocks.
- Automatic scheduling or rescheduling.
- Drag-and-drop calendar editing.
- Advanced recurrence engine.
- Full Supabase Auth.
- AI, agents, notifications, memory, embeddings, and learned behavior models.

## 7. Domain Semantics

Commitment:

- Fixed or semi-fixed real-world obligation with start/end time.
- Calendar displays it as projection.
- It is not a PlanBlock.

Action/Intention:

- Flexible desired work before scheduling.
- Stored canonically as `Action`.
- Stays unscheduled unless future planner assigns it.

Commitment levels:

- `hard`
- `goal_critical`
- `maintenance`
- `optional`

Hard/semi-fixed/flexible:

- `Commitment.commitment_type` supports `hard` and `semi_fixed`.
- Flexible demand is represented by `Action`.

## 8. Data Model Changes

Commitment gained:

- `description`
- `level`
- `commitment_type`
- `timezone`
- `all_day`
- `location`
- `recurrence`

Action gained:

- `description`
- `level`
- `earliest_start`
- `latest_start`
- `deadline`
- `location`
- `context`
- `duration_min_minutes`
- `duration_max_minutes`
- `scheduled_start`
- `scheduled_end`

## 9. Database Migrations

Added:

- `backend/migrations/versions/0002_commitments_intentions.py`

Applied successfully to PostgreSQL/Supabase with:

```powershell
python -m alembic upgrade head
```

## 10. API Changes

Commitments:

- `POST /api/v1/commitments`
- `GET /api/v1/commitments`
- `GET /api/v1/commitments/{id}`
- `PATCH /api/v1/commitments/{id}`
- `POST /api/v1/commitments/{id}/complete`
- `POST /api/v1/commitments/{id}/cancel`
- `POST /api/v1/commitments/{id}/miss`

Actions:

- `POST /api/v1/actions`
- `GET /api/v1/actions`
- `GET /api/v1/actions/{id}`
- `PATCH /api/v1/actions/{id}`
- `POST /api/v1/actions/{id}/complete`
- `POST /api/v1/actions/{id}/cancel`
- `POST /api/v1/actions/{id}/miss`

Calendar:

- `GET /api/v1/calendar-projection`

## 11. Status Transition Rules

Allowed:

- `active -> completed`
- `active -> cancelled`
- `active -> missed`
- `completed -> archived`
- `cancelled -> archived`
- `missed -> archived`

Invalid transitions return HTTP 409.

## 12. Conflict Policy

Active hard commitments conflict when:

```text
new_start < existing_end AND new_end > existing_start
```

Touching boundaries are allowed. Conflicts return HTTP 409 with structured conflict information. No automatic move or resolution is attempted.

## 13. Optimistic Concurrency

PATCH and status commands require `expected_version`. Stale versions return HTTP 409 and do not mutate the object or increment `WorldRevision`.

## 14. Idempotency

Create and status command endpoints accept `Idempotency-Key`. Repeated identical mutations replay the stored response without duplicate canonical records, events, or revisions.

## 15. Events

Commitment events:

- `commitment.created`
- `commitment.updated`
- `commitment.completed`
- `commitment.cancelled`
- `commitment.missed`

Action events:

- `action.created`
- `action.updated`
- `action.completed`
- `action.cancelled`
- `action.missed`

## 16. Outbox Behavior

All meaningful V0.2 mutations call `append_event(..., outbox=True)`, creating matching `OutboxEvent` rows.

## 17. WorldRevision Behavior

Every successful canonical mutation increments `UserProfile.world_revision` and appends a `WorldRevision`. Reads, failed validation, conflicts, stale edits, and failed transactions do not increment revision.

## 18. Calendar Projection

`GET /api/v1/calendar-projection` derives from canonical active commitments and includes unscheduled active actions as `planning_pool`. It does not create projection-owned objects and does not convert flexible actions into fake events.

## 19. Planning Pool

Planning Pool shows active actions with no scheduled start/end. It includes title, domain, level, estimated duration, deadline, and status action controls.

## 20. Frontend Changes

Calendar page now includes:

- Calendar Projection timeline.
- Add Commitment form.
- Conflict/error/success state for commitment creation.
- Add Intention form.
- Planning Pool list.
- Complete action button.
- Simple canonical commitment edit action.

## 21. Tests Added

Backend V0.2 tests cover:

- create/retrieve/list/edit/status commitments
- hard overlap rejection
- boundary-touching acceptance
- stale edit rejection
- idempotent commitment create
- create/list/edit/status actions
- action stale edit rejection
- calendar projection source-of-truth behavior
- canonical edit reflected in projection
- rollback when event append fails

Frontend V0.2 tests cover:

- commitment form render
- commitment API submission
- conflict/error display
- projection render
- intention API submission
- Planning Pool render
- status action call
- canonical edit call

## 22. Automated Verification Results

Backend:

```text
26 passed, 1 warning
```

Frontend:

```text
3 test files passed
11 tests passed
```

Typecheck:

```text
tsc -b passed
```

Production build:

```text
vite build passed
```

Migration:

```text
alembic upgrade head passed
```

## 23. Manual Verification Results

API/database acceptance was run against the configured runtime DB:

- Created hard University commitment.
- Calendar projection contained that commitment.
- Overlapping Doctor commitment returned HTTP 409.
- Canonical edit changed commitment time.
- Stale edit returned HTTP 409.
- Created Study Macroeconomics action.
- Action appeared in Planning Pool.
- Action did not appear as scheduled calendar event.
- Completed action status command succeeded.
- DB contained canonical Commitment and Action.
- DB contained semantic Events.
- DB contained OutboxEvents.
- `WorldRevision` advanced.

Full browser click-through refresh verification has not been performed in this run.

## 24. Known Issues

- Browser-level manual acceptance remains to be performed.
- Calendar edit UI is intentionally minimal; it calls canonical PATCH but does not expose a full edit form.
- Recurrence is metadata only; no recurrence engine exists.
- All-day behavior is represented but not deeply implemented in UI.
- Starlette/FastAPI test warning recommends `httpx2`; this is dependency noise, not a V0.2 regression.

## 25. Architecture Deviations

- The spec says Action/Intention may be named either way. The repository already has `Action`, so V0.2 uses `/actions` and does not create a parallel `/intentions` API.
- Inline forms are used instead of modals/drawers because the app had no existing modal/drawer system.

## 26. User Friction Observed

- Conflict messages are clear but technical because they surface API error text.
- Editing a commitment from Calendar is present but sparse.
- Planning Pool filters are not yet a rich UI; backend filters exist.

## 27. Data Now Available to V0.3

V0.3 Planner can rely on:

- active hard/semi-fixed commitments with start/end/location/level
- active flexible actions with domain/level/deadline/duration
- missed/completed/cancelled histories
- event history
- outbox
- world revision
- optimistic concurrency
- hard-overlap policy

## 28. V0.2 Acceptance Checklist

- [x] Fixed appointment can be stored.
- [x] Fixed appointment appears at correct time in projection.
- [ ] Fixed appointment survives browser reload - API persistence verified, browser refresh not manually executed.
- [x] Flexible intention can be stored.
- [ ] Flexible intention survives browser reload - API persistence verified, browser refresh not manually executed.
- [x] Flexible intention remains unscheduled.
- [x] Planning Pool exists.
- [x] Hard vs flexible distinction is visible.
- [x] Hard commitment overlap is detected.
- [x] Commitment status transitions persist.
- [x] Action status transitions persist.
- [x] Semantic events are emitted.
- [x] Outbox behavior remains correct.
- [x] WorldRevision changes on canonical mutations.
- [x] Failed/stale mutations do not increment WorldRevision.
- [x] Optimistic concurrency returns 409 on stale edit.
- [x] Calendar projection is regenerated from canonical data.
- [x] Calendar does not become source of truth.
- [x] Calendar edit modifies canonical object through command/API.
- [x] No generated PlanBlocks exist.
- [x] V0.1 State still works.
- [x] Backend tests pass.
- [x] Frontend tests pass.
- [x] Frontend typecheck passes.
- [x] Production frontend build passes.
- [x] Database migrations pass.
- [ ] Manual browser acceptance scenario passes - not run in browser.

## 29. Release Decision

PASS WITH KNOWN ISSUES

## 30. Readiness for V0.3

V0.3 can safely begin after browser refresh acceptance is completed. The planner can now consume hard commitments, flexible active actions, levels, deadlines, duration estimates, status histories, and `WorldRevision` as truthful canonical inputs.
