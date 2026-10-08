# V0.9 Personal Learning Report

## 1. Release Purpose
V0.9 adds bounded evidence-based personalization to the existing deterministic Life OS system. It learns Stage-1 estimates for capacity, completion, activation, preference, routine, and state transition behavior, then exposes only soft planner inputs.

## 2. Preconditions
V0.1 through V0.8 were treated as completed preconditions. V0.9 builds on canonical Plans, PlanBlocks, Actions, StateObservations, domain execution records, Kitchen preference evidence, Events, Outbox, and WorldRevision.

## 3. Repository Audit
The planner already stored DecisionFactors, plan lineage, status, scheduled windows, execution status, actual start/finish, actual duration, source action, domain, and commitment level. State history had timestamped observations. Fitness, Learning, and Kitchen already owned their canonical execution truth. Assistant tools were already bounded by role and confirmation policy. The repository is currently entirely untracked, so no destructive Git cleanup was attempted.

## 4. Existing Telemetry
Existing usable signals include planned duration, actual duration, started/completed/skipped/missed outcomes, start delay, domain, commitment level, load metadata, time of day, day of week, state before execution, post-execution state observations, Kitchen preference evidence, and planner DecisionFactors.

## 5. Missing Telemetry Added
V0.9 adds persisted `personal_training_examples`, `personal_model_versions`, `personal_pattern_evidence`, `personal_model_refresh_runs`, and Plan-level `personal_model_snapshot` / `personal_model_revision`. No broad self-report fields were added.

## 6. Architecture Reused
The implementation reuses FastAPI routers, SQLAlchemy models, Alembic, canonical service transactions, Event/Outbox/WorldRevision semantics, React Query frontend conventions, and the existing deterministic Core Planner.

## 7. Deviations
The requested conceptual `PersonalModelProvider` is implemented as `app.personal_model.service.snapshot()` and related service functions rather than a separate provider class. Training examples are persisted rows rather than manifest-only derived examples. No Stage-2 model was implemented.

## 8. Personal Learning Architecture
The subsystem lives under `backend/app/personal_model/` with feature extraction, schemas, confidence, calibration, promotion, and service modules. It extracts examples, creates candidate model versions, compares with baselines, promotes or rejects, exposes snapshots, and supports user correction. It never schedules.

## 9. Feature Schema
The initial schema is `personal-features-v1`. Extraction uses `personal-extractor-v1`. Future semantic changes require a new schema version.

## 10. Feature Extraction
Feature extraction reads terminal generated-action PlanBlocks and canonical source Actions. Features include domain, source type, commitment level, planned duration, planned hour, day of week, time bucket, pre-state values, state band, activation/cognitive/physical load, context, deadline proximity, and planner metadata. Labels are stored separately.

## 11. Target Leakage Prevention
Feature payloads exclude completion status, skipped/missed labels, actual duration, started/finished timestamps, outcome reason, post-state deltas, future observations, and later plan changes. Tests assert label fields do not leak into features.

## 12. Provenance / Reproducibility
Each example stores user id, feature schema version, extraction version, decision timestamp, Plan ID, PlanBlock ID, source Action ID, domain, label source, state observation IDs, planner version, and model versions stored on the source Plan.

## 13. ModelVersion
`personal_model_versions` stores user, model type, stage, model version, schema version, status, parameters, evidence window, evidence counts, effective evidence counts, confidence, metrics, baseline metrics, promotion reason, promoted time, superseded model reference, and refresh run id.

## 14. PatternEvidence
`personal_pattern_evidence` stores pattern type, scope, claim, evidence count, weighted support, confidence, observation window, status, correction metadata, and source model version. Statuses are `ACTIVE`, `DOWNWEIGHTED`, and `INVALIDATED`.

## 15. Model Stages
Stage 0 remains static deterministic heuristics. Stage 1 is implemented with rolling counts, EWMAs, robust medians, bounded means, recency decay, and calibrated bins. Stage 2 and Stage 3 are deliberately excluded.

## 16. CapacityModel
Capacity learns execution ratio by bin. Formula: `ewma_new = 0.30 * observation + 0.70 * ewma_previous`. The planner multiplier is clamped to `0.90..1.10`.

## 17. CompletionModel
Completion learns binned posterior completion probability. Formula: `posterior_completion = (completions + 2) / (attempts + 2 + 2)`. Low probability is a bounded ranking/variant signal only.

## 18. ActivationModel
Activation learns robust median start delay by bin. Formula: `activation_adjustment = clamp(median_start_delay_minutes / 15, 0, 6)`. Skips and misses contribute through terminal labels; one extreme delay does not dominate because the median is used.

## 19. PreferenceModel
Preference uses recency-weighted support. Formula: `weight = exp(-ln(2) * age_days / 30)`. Voluntary completion adds `1.0 * weight`, started-but-not-completed adds `0.2 * weight`, missed alone is ignored, goal-critical blocks are excluded, and Kitchen PreferenceEvidence receives 2x explicit weight.

## 20. RoutineModel
Routine learns repeated domain/time-bucket patterns. Formula: `consistency = completed / attempts`; `ranking_adjustment = clamp(consistency * min(attempts / 8, 1) * 6, 0, 6)`. Routines are soft fit signals only.

## 21. StateTransitionModel
State transition learns bounded post-minus-pre deltas by domain. Formula: mean of valid deltas within deterministic windows, clamped to `-12..12` for Energy and Mental State. It is correlation, not a causal or medical claim.

## 22. Confidence Formula
For capacity/state-transition models: `0.60 * evidence_component + 0.25 * consistency + 0.15 * improvement`. For other models: `0.55 * evidence_component + 0.25 * consistency + 0.20 * improvement`. Scores are clamped to `0..0.99` and capped below promotion when evidence is under threshold.

## 23. Evidence Thresholds
Minimum evidence thresholds are: capacity 20, completion 12, activation 12, preference 8, routine 8, state_transition 20. Promotion confidence thresholds are: capacity 0.75, completion 0.65, activation 0.65, preference 0.60, routine 0.60, state_transition 0.75.

## 24. Capability Guardrails
Capacity and state-transition are treated as capability-sensitive models. Capacity influence is bounded to a modest multiplier and never creates unavailable time. Completion cannot suppress goal-critical work. All learned ranking factors are bounded.

## 25. Calibration Metrics
Completion uses Brier score. Capacity and activation use mean absolute error. Candidate metrics and baseline metrics are persisted on model versions.

## 26. Baseline Comparison
Candidate models must not be worse than Stage-0/simple baseline metrics. Worse candidates are rejected with `BASELINE_BETTER`. Insufficient evidence is rejected with `INSUFFICIENT_EVIDENCE`.

## 27. Promotion Policy
Promotion requires evidence threshold, confidence threshold, baseline comparison, and influence guard. Promoted models become `ACTIVE`; a prior active model of the same type is marked `RETIRED`.

## 28. Rejection / Insufficient-Evidence Policy
Low-evidence candidates are still recorded as `REJECTED` with promotion reasons. Snapshot fallback reasons report `BASELINE / INSUFFICIENT_EVIDENCE` per inactive family.

## 29. User Correction
`POST /personal-model/patterns/{id}/correct` marks a pattern `INVALIDATED`, sets support/confidence to zero, stores correction reason/note metadata, emits an event, and preserves underlying training history.

## 30. Model Refresh
`POST /personal-model/refresh` extracts/persists examples, creates six candidates, promotes eligible models, creates displayable patterns, records a refresh run, emits `personal_model.refreshed`, and increments WorldRevision.

## 31. Refresh Locking
A running refresh row blocks concurrent refresh with HTTP 409. Failed refreshes are marked failed with an error string.

## 32. Active-Version Semantics
Snapshots expose active model IDs and integer model versions by type. Exactly one active model per user/model type is selected; newly promoted versions retire the previous active version.

## 33. Model Staleness
Model refresh emits a world-revision event. Plan generation already rejects stale `expected_world_revision`, so active model changes during a guarded generation are detected through existing revision semantics.

## 34. PersonalModelProvider
The provider role is implemented by `snapshot(db, user)`, `summary(db, user)`, and model listing functions. The planner receives the compact snapshot once at context assembly.

## 35. Planner Integration
`PlanningContext` now includes `personal_model_snapshot`. The planner applies learned capacity multipliers, completion fit, activation cost adjustment, preference fit, and routine fit only as bounded inputs.

## 36. Planner Contribution Bounds
Learned capacity is bounded to `0.90..1.10`. Learned ranking contributions are bounded to `-6..6`. Goal-critical negative completion contribution is capped at `-1.0`.

## 37. Criticality Override
Goal-critical work remains eligible even when learned completion probability is low. The planner may reduce block size to a minimum-safe form but does not remove the work solely because of the learned estimate.

## 38. Plan Model-Version Persistence
Plans persist `personal_model_snapshot` and `personal_model_revision`. This stores active model IDs, versions, confidence, parameters, evidence counts, and fallback reasons at planning time.

## 39. DecisionFactor Integration
Plan-level DecisionFactors include `personal_model_snapshot`. Block-level learned factors include model type, active model ID, and confidence in the notes.

## 40. Revision / Stale-Plan Semantics
Refresh increments WorldRevision, so callers using `expected_world_revision` detect stale planning inputs. Model refresh alone does not automatically rewrite current-day plans.

## 41. Operational Audit
Refresh runs, candidate versions, promotion reasons, pattern corrections, Plan snapshots, Events, and Outbox rows provide operational auditability. No prompt or whole-database AI memory is introduced.

## 42. APIs
Implemented endpoints: `GET /api/v1/personal-model/summary`, `GET /api/v1/personal-model/models`, `GET /api/v1/personal-model/models/{id}`, `GET /api/v1/personal-model/patterns`, `POST /api/v1/personal-model/patterns/{id}/correct`, `POST /api/v1/personal-model/refresh`, and diagnostic `GET /api/v1/personal-model/examples`.

## 43. Personalization UI
The web app adds `/personal-model` with summary tiles, active model cards, useful patterns, manual refresh, pattern correction, and recent rejected candidates. Wording stays neutral and avoids personality or capability labels.

## 44. Assistant Boundary
Assistant can read Personal Learning status through `get_personal_model_summary`. It cannot refresh/train/promote models or correct patterns. Refresh is API-authorized but not Assistant-controlled.

## 45. Synthetic Fixture Policy
Synthetic histories are used only in tests with isolated in-memory databases. They do not enter canonical local user history. Real-data smoke checks did not seed fake examples.

## 46. Automated Tests
Backend tests cover low evidence fallback, feature/label separation, provenance, synthetic promotion, Plan snapshots, pattern correction, critical-task guard, and Assistant boundary. Frontend tests cover summary rendering, baseline wording, active/rejected models, pattern display, refresh, and correction.

## 47. Manual Real-User Verification
After migration, real local summary before refresh was `BASELINE_INSUFFICIENT_EVIDENCE` with evidence 0. Manual refresh found 9 real examples, activated one routine model, rejected capacity/completion/activation/preference/state_transition, and produced fallback rate `0.833`. Normal plan generation succeeded and stored `personal_model_revision = 1` with the routine active model id.

## 48. Manual Synthetic-Model Verification
The isolated backend test database creates synthetic histories sufficient to promote eligible models and verifies Plan snapshot persistence without contaminating real user data.

## 49. Planner-Ranking Verification
Synthetic promoted models add learned DecisionFactors to scheduled blocks. Contributions are bounded and explainable by model id/confidence.

## 50. Critical-Task Verification
An isolated test injects an active low-completion model and verifies a goal-critical study action is still scheduled, negative learned completion contribution is capped at `-1`, and duration remains at least the action minimum.

## 51. User-Correction Verification
Backend tests invalidate a learned pattern, preserve training examples, and store correction metadata. Frontend tests call the correction API from the diagnostics page.

## 52. Reproducibility Verification
Plans store snapshots of active model IDs, versions, parameters, confidence, and evidence counts. Old plans retain their stored snapshot after later refreshes. Refresh is deterministic for the same evidence and schema.

## 53. Known Limitations
Stage-1 bins are intentionally broad. Preference and state-transition models are conservative. Pattern display can be empty even when a model is active if no pattern crosses display thresholds. Evaluation splits are simple chronological splits, not advanced cross-validation.

## 54. Deliberate Deferrals
No V1 deployment, production auth, Web Push, embeddings, personal knowledge graph, semantic memory, bandits, reinforcement learning, deep neural models, autonomous experiments, or external calendar integration were implemented.

## 55. Git-State Note
`git status --short` reports the repository contents as untracked. No `git clean`, hard reset, destructive checkout, or repository repair was performed.

## 56. Data/Interfaces Created for V1.0
V0.9 creates stable tables, snapshots, model versioning, provenance, correction, and diagnostics that V1.0 can build on. It does not implement V1.0 features.

## 57. Acceptance Checklist
- Feature extraction, schema versioning, provenance, and leakage tests: PASS.
- ModelVersion, PatternEvidence, six Stage-1 model families: PASS.
- Evidence, confidence, calibration, baseline comparison, rejection, and promotion policy: PASS.
- Bounded planner integration, criticality guard, Plan snapshots, DecisionFactor attribution, and stale revision behavior: PASS.
- Assistant boundary, UI, correction path, backend tests, frontend tests, typecheck, build, and Alembic migration: PASS.
- No bandits, deep models, automatic hard constraints, fake real-user evidence, or V1.0 work: PASS.

## 58. Release Decision
PASS

## 59. Readiness for V1.0
V1.0 can safely begin after this point, but no V1.0 work was started in this release.
