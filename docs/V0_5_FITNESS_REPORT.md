# Life OS V0.5 - Fitness

## 1. Release Purpose

V0.5 makes Fitness the first deep specialist domain. Fitness is now usable as an independent mini-application for programs, templates, workouts, sets, progression, body measurements, trends, recovery, and planner candidate generation while preserving the central planner as scheduling authority.

## 2. Preconditions

V0.4 Daily Control Loop is present and passing. V0.5 preserves V0.1 state, V0.2 commitments/actions, V0.3 planner projections, and V0.4 PlanBlock execution semantics.

## 3. Repository Audit

Existing foundations found: placeholder Fitness route, body measurement service, generic Fitness DB tables, Fitness page, domain contract, event/outbox/world revision service, Actions Planning Pool, `CandidateAction` fields for `domain`, `physical_load`, `activation_difficulty`, duration bounds, Home route, Calendar projection, and frontend API patterns.

## 4. Architecture Reused

Reused SQLAlchemy models, FastAPI routers, idempotency headers where appropriate, shared events/outbox/world revisions, canonical Actions for planner participation, deterministic Core Planner, React Query, existing app shell, stat tiles, content bands, forms, and timeline/list styling.

## 5. Deviations

Existing placeholder `fitness_workouts`, `fitness_workout_exercises`, and `fitness_exercise_sets` tables were preserved for compatibility. V0.5 adds canonical session/template/program tables and extends `fitness_exercise_sets` instead of dropping old tables.

## 6. Fitness Domain Boundary

Fitness owns training truth: programs, templates, exercises, sessions, sets, progression, recovery, body measurements, body trends, candidate generation, and coach context. Fitness does not write PlanBlocks directly and does not decide calendar placement.

## 7. Data Model

Added or finalized: `WorkoutProgram`, `WorkoutTemplate`, `WorkoutTemplateExercise`, `WorkoutSession`, `Exercise`, `ExerciseSet`, `BodyMeasurement`, `RecoveryObservation`, `ProgressionState`, and `FitnessGoal`.

## 8. WorkoutProgram / Templates

Programs can be created, updated, activated, and deactivated. Templates belong to programs, preserve sequence order, estimated duration, active status, and ordered template exercises.

## 9. Exercise Model

Exercises store name, category, primary muscle group, equipment, default rest seconds, active status, notes, user ownership, and version.

## 10. WorkoutSession Lifecycle

Workout sessions support `in_progress`, `completed`, and `abandoned`. Starting an already active session for the same template resumes it. Completion requires at least one logged set. Abandonment preserves logged sets.

## 11. ExerciseSet Logging

Sets store session, exercise, template exercise, sequence, reps, load in kg, RPE, set type, completion time, note, completion flag, and optional idempotency key. Retry with the same idempotency key returns the existing set.

## 12. Workout Runtime / Resume

The Fitness dashboard detects active sessions and renders Workout Mode. The active session survives refresh/re-query because `WorkoutSession` and `ExerciseSet` are canonical backend records.

## 13. Rest Timer

The frontend rest timer starts after set completion using the template exercise rest duration. It supports start, pause, and reset. Timer state is stored in browser localStorage per session and does not write per-second backend events.

## 14. Progression Engine

Rule: double progression.

For each template exercise, use the first `target_sets` completed working sets from the completed session.

- If all required working sets reach `target_rep_max` and all RPE values are `<= target_rpe` and a load exists, recommend `previous_load_kg + load_increment_kg`.
- If any required working set is below `target_rep_min`, maintain the previous load.
- Otherwise maintain the previous load.

No AI, hidden judgment, or aggressive auto-deload is used.

## 15. Progression Explainability

Each `ProgressionState` stores structured facts: rule, previous load, recommended load, target sets, rep range, RPE threshold, completed sets, and reason.

## 16. BodyMeasurement Model

Body measurements include timestamp, weight kg, body fat percentage, lean mass kg, optional muscle mass, water percentage, visceral fat rating, BMI, source, metadata, notes, and version. Default manual UI source is Etekcity scale.

## 17. Body Trend Algorithm

For weight and body fat, V0.5 uses a rolling seven-day window ending at the latest measurement timestamp. It uses only real timestamped observations in that window and does not fabricate missing days. If fewer than seven observations exist, it averages available observations and labels the sample count.

## 18. Fitness Goals / Trajectory

`FitnessGoal` supports target weight, target body fat, target lean mass, direction, active status, and notes. This allows goals like gaining weight while improving body composition.

## 19. Recovery / Readiness Algorithm

Readiness score starts from latest explicit readiness or `70`.

- Soreness penalty: `round(soreness * 0.35)`.
- Stress penalty: `round(stress * 0.2)`.
- Sleep contribution: `round((sleep_quality - 50) * 0.25)`.
- Recent hard completed workout within 24h and difficulty >= 8: `-12`.

Bands: `good >= 70`, `moderate >= 45`, otherwise `low`. This is planning input, not medical diagnosis.

## 20. CandidateAction Generation

Fitness generates candidate variants from the next deterministic template. Candidate fields include stable candidate id, title, template id, duration, min/max duration, physical load, activation difficulty, trajectory value, expected state effect, and metadata.

## 21. Duration Variants

Variants are full, reduced, and minimum. Full uses template duration. Reduced uses roughly 80 percent with a 40-minute floor. Minimum uses roughly 55 percent bounded to 25-45 minutes.

## 22. Expected State Effect

Candidate metadata separates expected state effect from progression value, including energy cost, recovery need, and readiness score.

## 23. Planner Integration

Fitness syncs candidate variants into canonical `Action` records with `domain="fitness"` and metadata consumed by the existing planner. The Core Planner then decides whether and where to schedule them.

## 24. Nutrition Boundary

No meal planning, inventory, shopping, or Chef behavior was added. V0.5 only creates room for future nutrition constraints through Fitness summaries/goals.

## 25. Events

Added events include `fitness.program.created`, `fitness.program.updated`, `fitness.exercise.created`, `fitness.exercise.updated`, `fitness.template.created`, `fitness.template.updated`, `fitness.template_exercise.added`, `fitness.template_exercise.updated`, `fitness.workout.started`, `fitness.set.logged`, `fitness.workout.completed`, `fitness.workout.abandoned`, `fitness.body_measurement.recorded`, `fitness.recovery.observed`, and `fitness.goal.updated`.

## 26. WorldRevision Behavior

Fitness mutations that affect planner context or canonical user state append events and increment `WorldRevision` through the shared event service. Timer ticks do not increment world revision.

## 27. Outbox Behavior

Fitness events use the shared transactional outbox. Workout lifecycle, set logging, body measurements, recovery, and configuration mutations create outbox rows.

## 28. API Surface

Added `/api/v1/fitness/status`, `/coach-context`, `/programs`, `/exercises`, `/templates`, `/templates/{id}/exercises`, `/template-exercises/{id}`, `/sessions/start`, `/sessions/active`, `/sessions/{id}/sets`, `/sessions/{id}/complete`, `/sessions/{id}/abandon`, `/body-measurements`, `/body-trends`, `/recovery`, `/readiness/summary`, `/candidates`, `/candidates/sync-actions`, `/progression`, and `/goals`.

## 29. Fitness Dashboard

Dashboard shows next workout, recovery band, weekly count, weight trend, today workout, program setup, progression, body measurements, recovery, and planner candidates.

## 30. Workout Mode UX

Workout Mode shows workout name, current exercise, current set, target reps/load/RPE, quick inputs for load/reps/RPE, Complete Set, rest timer, recent sets, Complete Workout, and Abandon.

## 31. Home Integration

Home now includes a compact Fitness card with next workout, recovery, workouts this week, weight trend, and today planned Fitness block when present.

## 32. Coach Context / Tool Contracts

`FitnessDomain` exposes bounded context and tools: `start_workout`, `record_workout_set`, `complete_workout`, `add_body_measurement`, and `get_fitness_status`. It explicitly forbids direct plan writes, SQL execution, and meal selection.

## 33. Database Migration

Migration `0005_fitness_domain` applies cleanly after `0004_daily_control_loop` and preserves existing V0.1-V0.4 data.

## 34. Automated Tests

Backend tests: `49 passed`. Frontend tests: `28 passed`. Typecheck passed. Production build passed.

## 35. Manual Acceptance

Manual acceptance passed with suffix `af9d3b1b`: created Hypertrophy 4-Day, Upper A, Bench/Row/Lateral Raise, started/resumed workout, logged nine sets, completed workout, verified Bench recommendation 70kg to 72.5kg, entered noisy body data, verified rolling trend 78.47kg vs latest 78.3kg, created recovery state, synced candidates, and generated a planner day where the central planner selected a 41-minute Fitness minimum variant.

## 36. Known Limitations

No wearable sync, no Etekcity API sync, no notifications, no advanced periodization, no form analysis, and no autonomous Fitness Coach AI.

## 37. Deliberate Deferrals

Deferred: Apple Health, smartwatch integrations, camera form analysis, automatic routine generation, learned recovery model, nutrition planning, Kitchen integration, Learning V0.6, embeddings, and general assistant behavior.

## 38. User Friction Observed

Program setup is functional but still compact and manual. Template exercise editing is API-supported, but the UI prioritizes create/add over rich drag-and-drop editing.

## 39. Data Created for V0.6 and Later Personal Learning

V0.6 and later systems can rely on real workout sessions, set history, body trends, readiness factors, deterministic progression state, and planner-visible Fitness candidate Actions.

## 40. Acceptance Checklist

- [x] Fitness is usable independently as a mini-app.
- [x] WorkoutProgram exists.
- [x] WorkoutTemplate exists.
- [x] Exercise exists.
- [x] WorkoutSession exists.
- [x] ExerciseSet exists.
- [x] BodyMeasurement exists.
- [x] Program configuration persists.
- [x] Workout can start and resume.
- [x] Sets can be logged quickly.
- [x] Reps, kg load, and RPE are stored.
- [x] Rest timer works without per-second backend writes.
- [x] Workout can complete or be abandoned.
- [x] Progression is deterministic and explainable.
- [x] Body measurements and Etekcity/manual source are represented.
- [x] Rolling weight and body-fat trends work.
- [x] Fitness goals support recomposition direction.
- [x] Recovery/readiness foundation works.
- [x] Fitness generates CandidateActions and duration variants.
- [x] Low readiness changes candidate characteristics.
- [x] Expected state effect is separate from progression value.
- [x] Central Planner consumes Fitness candidate Actions.
- [x] Fitness never directly schedules PlanBlocks.
- [x] Calendar remains projection.
- [x] Events/outbox/world revision behavior is preserved.
- [x] Home Fitness card exists.
- [x] Backend tests, frontend tests, typecheck, build, migration, and manual acceptance pass.

## 41. Release Decision

PASS

## 42. Readiness for V0.6

V0.6 Learning and the central Planner can now rely on Fitness as a real specialist domain that produces canonical execution history, deterministic progression, readiness context, body trends, bounded coach context, and planner-visible candidate Actions without taking scheduling authority.

