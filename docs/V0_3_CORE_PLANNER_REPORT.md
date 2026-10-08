# Life OS V0.3 - Core Planner V0

## 1. Release Purpose

V0.3 implements the first deterministic Core Decision Engine for answering "What should I realistically do today?" It consumes current state, hard commitments, active flexible actions, deadlines, capacity, stress, and slack requirements. It optimizes sustainable trajectory progress rather than raw task throughput.

## 2. Preconditions

V0.1 State and V0.2 Commitments & Intentions are present. The planner consumes `StateObservation`, `Commitment`, `Action`, `Event`, `OutboxEvent`, `WorldRevision`, idempotency, optimistic concurrency, Calendar Projection, and Planning Pool data.

## 3. Repository Audit Findings

The repository already had skeletal `Plan` and `PlanBlock` models plus placeholder planner dataclasses, a placeholder engine, and a simulation harness. It also had world revision/event/outbox infrastructure, state projection, commitment/action services, and a Home/Calendar frontend.

## 4. Existing Planner Foundations Reused

Reused `backend/app/planning`, the existing `plans` and `plan_blocks` tables, canonical V0.2 action/commitment queries, `append_event`, idempotency records, and Home/Calendar UI patterns.

## 5. Architecture Deviations

No parallel planner architecture was introduced. `PlanBlock.decision_factors` is stored as JSON containing an `items` list because the existing model represented decision factors as JSON rather than a separate table.

## 6. PlanningContext

`PlanningContext` includes user, planning date, timezone, horizon, generation timestamp, `generated_from_world_revision`, latest energy/mental state, active hard commitments overlapping the horizon, and active unscheduled planner-eligible actions converted into candidates.

## 7. CandidateAction Contract

`CandidateAction` contains canonical `source_action_id`, domain, title, commitment level, estimated/min/max duration, optional time windows, deadline, location/context, cognitive load, physical load, activation difficulty, stress cost, trajectory value, maintenance value, neglect cost, splittable, and metadata.

## 8. Plan / PlanBlock Model

`Plan` stores planning day, horizon, status, generated timestamp, planner version, source world revision, summary metrics, and plan-level factors. `PlanBlock` stores source type/id, canonical action/commitment references, title, domain, start/end, duration, block type, level, movability, status, and structured factors.

## 9. State Capacity Model V0

Average state is `round((energy + mental_state) / 2)`, bounded 0-100. Bands:

- High `>= 70`: capacity ratio `0.78`, slack ratio `0.15`, minimum slack `45m`.
- Medium `50-69`: capacity ratio `0.60`, slack ratio `0.22`, minimum slack `75m`.
- Low `35-49`: capacity ratio `0.42`, slack ratio `0.35`, minimum slack `120m`.
- Very low `< 35`: capacity ratio `0.28`, slack ratio `0.45`, minimum slack `150m`.

Available minutes are free minutes after hard commitments. Required slack is `min(available, max(min_slack, round(available * slack_ratio)))`. Usable flexible minutes are `max(0, min(available - required_slack, round(available * capacity_ratio)))`.

## 10. Stress Budget V0

Stress is bounded 0-100 with threshold `68`. Formula: `state_pressure + block_count_pressure + context_switch_pressure + workload_pressure + slack_relief`.

State pressure is high `2`, medium `8`, low `16`, very low `24`; block pressure is generated action block count times `4`; context switch pressure is domain switches times `3`; workload pressure is `min(45, flexible_minutes / usable_flexible_minutes * 38)`; slack relief is `-8` when required slack is at least `90m`, otherwise `-3`.

## 11. Slack Policy

Slack is explicit `PlanBlock` output with type `slack`, not accidental leftover time. Lower state increases required slack. The planner never fills every free minute by default.

## 12. Utility / Priority Model

Candidate score is the sum of named factors: `commitment_level`, `trajectory_value`, `deadline_urgency`, `neglect_cost`, `maintenance_value`, `stress_cost`, `activation_cost`, `capacity_mismatch_cost`, `context_switch_cost`, and `time_cost`.

## 13. Deadline Urgency

No deadline gives `0`. Expired active actions give `32`. Deadline within one day gives `30`, within three days `22`, within seven days `12`, otherwise `4`.

## 14. Neglect Cost

Defaults are goal-critical `14`, maintenance `25`, optional `3`, plus `8` when a deadline exists. Metadata may override the value. This distinguishes future consequence from immediate productivity.

## 15. Activation Difficulty

Defaults are goal-critical `48`, maintenance `36`, optional `24`, with metadata override. Cost multiplier is `0.32` when both state values are at least 50, otherwise `0.55`.

## 16. Context Switching

Context switch cost is modest: `2` when explicit context exists, otherwise `4` for admin/kitchen/home and `3` for other domains. Stress also counts domain switches among scheduled generated blocks.

## 17. Block Sizing

High state schedules up to estimated duration. Medium state caps at `90m`. Low/very-low state caps goal-critical at `45m`, maintenance at `35m`, optional at `25m`, while respecting candidate min/max duration.

## 18. Minimum Viable Progress

Low state does not delete critical trajectories. Goal-critical work can become a smaller executable block, such as 25-45 minutes, without marking the source Action complete.

## 19. Plan Generation Pipeline

The pipeline loads context, validates expected revision when provided, places hard commitments, derives free intervals, calculates capacity/slack, converts Actions to CandidateActions, scores and sorts candidates deterministically, places feasible blocks, enforces stress budget, inserts slack blocks, validates source revision before publish, persists Plan/PlanBlocks, and appends `plan.generated`.

## 20. WorldRevision / Stale Plan Protection

Plans store `generated_from_world_revision`. `POST /api/v1/plans/generate` accepts `expected_world_revision`; stale requests return `409 stale_world_revision`. The service also checks the user revision again immediately before publishing.

## 21. Planner Concurrency

Generation runs in one backend transaction. Current plans for the same day are superseded before the new plan becomes current. The final world-revision check prevents stale publication.

## 22. Plan Stability

Sorting is deterministic by score, deadline, domain, title, and source action id. Given unchanged inputs, outputs are canonically equivalent.

## 23. Backlog Firewall Foundation

The planner selects from canonical active unscheduled Actions each run. It does not clone missed or unscheduled work into new Actions.

## 24. Unscheduled Action Policy

Unscheduled actions remain canonical active Actions in the Planning Pool. Reasons include `capacity_limit`, `time_constraints`, and `stress_limit`.

## 25. Explainability / Decision Factors

Generated action blocks persist structured factors such as deadline urgency, commitment level, activation cost, capacity mismatch, stress cost, context switch cost, and block size. No hidden reasoning is stored.

## 26. API Changes

Added `POST /api/v1/plans/generate`, `GET /api/v1/plans/current`, and `GET /api/v1/plans/{id}`.

## 27. Database Changes

Migration `0003_core_planner` adds plan horizon/generated/summary fields and PlanBlock source, title, duration, type, level, movability, and decision factor fields.

## 28. Events / Outbox

Successful generation emits `plan.generated`, increments `WorldRevision`, and creates an `OutboxEvent`.

## 29. Frontend Changes

Home now loads the current plan, renders no-plan/loading/error states, can generate today's plan, shows hard commitments, generated actions, slack blocks, and a compact deterministic summary.

## 30. Simulation Scenarios

The simulation harness covers normal day, low state, deadline pressure, maintenance neglect, overloaded day, no flexible work, and determinism.

## 31. Automated Tests

Backend tests: `32 passed`. Frontend tests: `15 passed`. Coverage includes context assembly, persistence, hard blocks, generated blocks, slack, stress, stale revision rejection, backlog firewall, low-state behavior, and deterministic scenarios.

## 32. Manual Verification

Runtime PostgreSQL acceptance passed with suffix `985a25aa`. Normal plan scheduled 180 flexible minutes, 300 hard minutes, 119 slack minutes, 3 actions, stress 39. Stale revision generation returned `409`. Low-state plan scheduled 75 flexible minutes, 360 hard minutes, 216 slack minutes, 2 actions, 1 unscheduled, stress 48.

## 33. Known Limitations

There is no automatic replanning, no repair of existing plans, no execution controls, no learned personalization, no advanced domain intelligence, and no external calendar sync. The planner does not yet reuse previous block placement beyond deterministic ordering.

## 34. Deliberately Deferred Scope

Deferred: AI planner, adaptive learning, routine models, completion prediction, notifications, external calendars, automatic missed-block handling, full Day Alignment, specialized domain intelligence, and ongoing control loop behavior.

## 35. User Friction Observed

The Home screen now generates plans manually. Users still need to create canonical commitments/actions in Calendar before planning, and stale generation errors currently ask for refresh/retry rather than offering automatic retry.

## 36. Data Produced for V0.4

V0.4 can use persisted PlanBlocks, unscheduled reasons, summary metrics, stress estimates, slack allocations, source references, and decision factors for daily control-loop behavior.

## 37. Acceptance Checklist

- [x] Planner consumes canonical V0.1/V0.2 data.
- [x] PlanningContext exists.
- [x] CandidateAction exists.
- [x] Plan and PlanBlock exist.
- [x] Hard commitments are placed first and not moved.
- [x] Free intervals are calculated.
- [x] State affects capacity, low state reduces workload, and low state increases slack.
- [x] Goal-critical and maintenance priority are represented.
- [x] Optional work is deprioritized under pressure.
- [x] Explicit slack and stress estimate exist.
- [x] Stress ceiling is enforced.
- [x] Utility is decomposed into named factors.
- [x] Planner is deterministic and may leave work unscheduled.
- [x] Unscheduled work remains in Planning Pool and is not cloned.
- [x] PlanBlocks reference canonical sources and do not become source of truth.
- [x] World revision is recorded and stale generation is rejected.
- [x] Plan and PlanBlocks persist.
- [x] `plan.generated` Event and OutboxEvent are emitted.
- [x] Frontend can load/generate/display plans.
- [x] Simulation, backend, frontend, typecheck, build, migration, and manual scenarios passed.

## 38. Release Decision

PASS WITH KNOWN ISSUES

## 39. Readiness for V0.4

V0.4 may safely rely on canonical plan projection storage, source references, explicit slack, stress metrics, unscheduled reasons, deterministic block ordering, stale-world protection, and event/outbox behavior. It should build the daily control loop on top of these projections without mutating canonical Actions or Commitments through PlanBlocks.
