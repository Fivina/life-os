# Life OS V0.4 - Daily Control Loop & Replanning

## 1. Release Purpose

V0.4 adds the deterministic daily control loop on top of the V0.3 planner. It lets Life OS evaluate the current day, execute generated blocks, mark stale work as missed, and repair or replan the remaining day without duplicating backlog items.

## 2. Preconditions

V0.1 state tracking, V0.2 canonical commitments/actions, and V0.3 deterministic plans are present. V0.4 relies on canonical source records remaining authoritative while `Plan` and `PlanBlock` stay projections.

## 3. Core Service

Added `backend/app/planning/control_loop.py` with `evaluate_day`, `manual_replan`, `replan_remaining_day`, `start_block`, `complete_block`, `skip_block`, and overdue missed-block handling.

## 4. Replan Policy

The control loop returns `NO_CHANGE`, `REPLAN_SUGGESTED`, `LOCAL_REPAIR_REQUIRED`, or `FULL_REPLAN_REQUIRED` style reasons through structured API responses. Manual replans return `USER_REQUESTED`; material state changes return `STATE_MATERIAL_CHANGE`; hard commitment conflicts return `HARD_COMMITMENT_CONFLICT`.

## 5. State Materiality

Energy or mental-state deltas of at least `15` trigger material change. Band changes use a small hysteresis guard so minor boundary crossings such as `70/70` to `66/68` do not destabilize the day.

## 6. Freeze Horizon

The service preserves completed, in-progress, and near-term frozen plan blocks during replanning. The freeze horizon is `30` minutes.

## 7. PlanBlock Lifecycle

Generated action blocks now support `planned`, `in_progress`, `completed`, `skipped`, and `missed`. Invalid transitions are rejected.

## 8. Execution Metadata

`PlanBlock` stores `started_at`, `finished_at`, `actual_duration_minutes`, `outcome_reason`, and `note`.

## 9. Source Action Semantics

Completing a generated block increments the canonical Action's `completed_minutes`. The Action is completed only when cumulative completed minutes meet or exceed its estimated duration. Partial PlanBlock completion does not complete the source Action.

## 10. Backlog Firewall

Skipped and missed generated blocks do not clone Actions, create replacement Actions, or mutate hard commitments. Remaining work is represented by the existing canonical Action and its `completed_minutes`.

## 11. Overdue Blocks

Overdue generated blocks are marked `missed` only inside mutation paths such as `POST /api/v1/day/evaluate`. GET endpoints do not mutate execution state.

## 12. Replanning

The service replans the remaining day by generating a new current plan, linking it to the previous plan, preserving immutable/frozen execution history, and storing a structured `plan_diff`.

## 13. PlanDiff

Diff output tracks kept blocks, moved blocks, shortened blocks, removed blocks, added blocks, deferred source actions, stress changes, and slack changes.

## 14. Hard Commitment Conflicts

Evaluation detects active canonical hard commitments that overlap generated blocks. This requests local repair/replanning while hard commitment blocks remain authoritative.

## 15. API Changes

Added:

- `POST /api/v1/day/evaluate`
- `POST /api/v1/plans/replan`
- `POST /api/v1/plans/{plan_id}/blocks/{block_id}/start`
- `POST /api/v1/plans/{plan_id}/blocks/{block_id}/complete`
- `POST /api/v1/plans/{plan_id}/blocks/{block_id}/skip`

## 16. Database Changes

Migration `0004_daily_control_loop` adds `actions.completed_minutes`, plan lineage/control-loop fields, plan diff metadata, evaluation/replan timestamps, and PlanBlock execution metadata.

## 17. Events / Outbox

The lifecycle emits `plan.block.started`, `plan.block.completed`, `plan.block.skipped`, and `plan.block.missed` events. Each event is mirrored into the transactional outbox by the shared event appender.

## 18. Frontend Changes

Home now has execution controls for generated PlanBlocks, manual replan, state-check-in evaluation, and compact PlanDiff feedback. Calendar now shows current PlanBlocks alongside canonical commitments while preserving the projection boundary.

## 19. Acceptance Scenarios

Covered by automated tests:

- Start block changes status to in-progress.
- Complete block records execution metadata and source Action progress.
- Partial completion does not complete the canonical Action.
- Full completion completes the canonical Action.
- Skip does not create duplicate Actions.
- Invalid transitions are rejected.
- Small state changes keep the plan stable.
- Material state changes replan with lineage and diff.
- Replan cooldown prevents rapid churn.
- Overdue generated blocks become missed through evaluation.
- Manual replan preserves completed history.
- Hard commitment conflicts trigger repair/replan behavior.

## 20. Automated Tests

Backend tests: `42 passed`. Frontend tests: `22 passed`. Frontend typecheck passed.

## 21. Known Limitations

The control loop is deterministic and rule-based. It does not yet send notifications, learn personalized recovery behavior, sync external calendars, or run on an automatic scheduler.

## 22. Deliberately Deferred Scope

Deferred: adaptive AI planning, external calendar sync, notification delivery, routine prediction, learned task completion estimates, and long-term pattern intelligence.

## 23. Acceptance Checklist

- [x] DailyControlLoop service exists.
- [x] Execution lifecycle exists.
- [x] Invalid transitions are rejected.
- [x] Execution metadata is persisted.
- [x] Lifecycle events and outbox entries are emitted.
- [x] Partial completion does not complete source Actions.
- [x] Full completion can complete source Actions.
- [x] Skipped/missed blocks do not duplicate backlog.
- [x] Overdue missed marking happens through POST evaluation, not GET.
- [x] Replan policy responses are structured.
- [x] Material state changes trigger replanning.
- [x] Small state changes preserve plan stability.
- [x] Freeze horizon preserves near-term blocks.
- [x] Completed/in-progress history is preserved.
- [x] Plan lineage and PlanDiff are persisted.
- [x] Home supports execution controls, state evaluation, manual replan, and PlanDiff feedback.
- [x] Calendar shows current PlanBlocks as projections.
- [x] Backend tests, frontend tests, typecheck, migration, build, and manual acceptance were run for release verification.

## 24. Release Decision

PASS WITH KNOWN LIMITATIONS

