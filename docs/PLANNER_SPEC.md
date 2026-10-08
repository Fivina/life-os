# Planner Spec

V0.3 implements deterministic daily scheduling authority while preserving canonical source boundaries. V0.4 adds a deterministic daily control loop for execution, evaluation, repair, and replanning. Version 1.3 evolves that same planner into Adaptive Planner V2.

## Core Types

- `PlanningContext`
- `CandidateAction`
- `PlanningConstraint`
- `PlanningResult`
- `DecisionFactor`
- `CapacityEstimate`
- `StressEstimate`
- `PlannedBlock`
- `UnscheduledAction`

## Planner Inputs

The planner consumes current energy and mental state, active hard commitments overlapping the horizon, active unscheduled Actions from the Planning Pool, deadlines, commitment level, duration estimates, context/location, load defaults, stress defaults, and current `WorldRevision`.

Adaptive Planner V2 also consumes user-scoped rolling allocations, open planning debt, typed canonical constraints, controlled translations of pinned scheduling memories, active Personal Learning evidence, candidate group metadata, and prior-plan stability metadata.

## Authority Boundary

Domains and users own canonical Actions and Commitments. The Core Decision Engine owns Plan and PlanBlock projections. PlanBlocks reference canonical sources but do not replace or mutate them.

V0.4 keeps that boundary intact: PlanBlock execution can update source Action progress, but skipped and missed PlanBlocks never clone or replace Actions.

## Deterministic Rules

The planner places hard commitments first, derives free intervals, calculates state-based capacity and explicit slack, scores candidate actions with named factors, places feasible blocks, enforces a stress threshold, inserts slack blocks, and rejects stale generation.

Version 1.3 treats domain alternatives as mutually exclusive members of one action group. It evaluates bounded `Action x Variant x Slot` choices, uses future-slot weekday/time buckets for learned behavior, applies hard constraints as feasibility gates and soft constraints as penalties, and uses deterministic tie-breaking. Low state excludes oversized variants even when raw clock capacity could fit them.

A rolling ten-day allocator protects deadlines and reports real shortfall without creating duplicate Actions. Daily execution creates debt for partial, skipped, missed, or cancelled placements. Replanning keeps completed, in-progress, frozen, manually moved, and user-locked blocks stable while rescheduling remaining requirements. Unscheduled work and overload remain explicit plan output.

Morning generation is user/date scoped and idempotent. The worker runs it only after the configured local hour; `/plans/current` provides a first-access fallback. Planning remains fully functional with AI disabled.

The control loop preserves completed, in-progress, hard, and near-term frozen blocks before repairing or replanning the remaining day. Material state changes, hard commitment conflicts, and manual user requests can produce a new current plan linked to the previous one by PlanDiff metadata.

V0.5 Fitness participates through canonical `Action` records generated from Fitness candidate variants. Fitness proposes full/reduced/minimum workout options with physical load, activation difficulty, duration bounds, and expected state effect metadata; the Core Planner remains the only component that creates PlanBlocks.

V0.6 Learning participates through canonical `Action` records generated from exam trajectories. Learning candidates include exam/course/topic metadata, full/standard/reduced/minimum/activation variants, cognitive load, activation difficulty, trajectory value, urgency, neglect cost, deadline, and prerequisite metadata. Core Planner arbitrates Learning against Fitness and all other domains. Completed Learning PlanBlocks create linked StudySessions through the Learning service; skipped and missed Learning PlanBlocks create no study progress and no duplicate backlog rows.

V0.9 Personal Learning participates through an immutable `PersonalModelSnapshot` compiled before planning starts. The snapshot may provide bounded Stage-1 capacity, completion, activation, preference, and routine inputs. The planner records learned DecisionFactors with model id/confidence where a learned value contributes. Learned capacity is clamped to a 0.90-1.10 multiplier, learned ranking factors are bounded, and low completion probability cannot suppress goal-critical work. Personal Learning never creates PlanBlocks or hard constraints.

## Simulation Harness

`backend/app/planning/simulator.py` runs deterministic scenarios for normal days, low state, deadline pressure, maintenance neglect, overload, no flexible work, and determinism.
