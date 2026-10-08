# Data Model

V0 uses UUID string identifiers, `created_at`, `updated_at`, and `version` on important mutable records. Important writes increment the user's world revision.

## Core Tables

- `user_profiles`: single-user profile, current world revision, and V1.0 `auth_subject` mapping to the verified Supabase user id.
- `goals`, `trajectories`, `commitments`, `actions`, `constraints`: extensible life planning entities.
- `plans`, `plan_blocks`: deterministic Core Planner projections. Domains must not write these directly. PlanBlocks reference canonical Commitments or Actions through source fields and must not become source of truth. V0.4 adds plan lineage, control-loop metadata, PlanDiff payloads, and PlanBlock execution metadata. V0.9 adds `personal_model_snapshot` and `personal_model_revision` to Plans so past plans identify the learned model versions that influenced them.
- `fitness_workout_programs`, `fitness_workout_templates`, `fitness_workout_template_exercises`, `fitness_workout_sessions`, `fitness_exercise_sets`, `fitness_progression_states`, `fitness_recovery_observations`, `fitness_goals`: V0.5 Fitness specialist domain records. WorkoutSession and ExerciseSet are canonical training execution truth; PlanBlocks are only planner projections.
- `learning_courses`, `learning_exams`, `learning_study_requirements`, `learning_study_sessions`: V0.6 Learning specialist domain records. Exams expose deterministic preparation trajectories; StudySession is canonical academic execution truth. Planned study does not count as completed study until a StudySession exists.
- `state_observations`: timestamped energy, mental state, stress, sleep quality, readiness, and future measurement types.
- `events`: historical event log with world revision.
- `outbox_events`: transactional outbox for future processors.
- `world_revisions`: revision history linked to events.
- `notification_intents`: deterministic notification candidates.
- `push_subscriptions`: V1.0 browser Push API subscriptions owned by the authenticated user.
- `push_deliveries`: V1.0 idempotent per-subscription notification delivery records keyed by dedupe key.
- `idempotency_records`: mutation replay protection.
- `assistant_action_proposals`: V0.7 short-lived server-side proposals for consequential Assistant mutations. Stores validated tool arguments, role, expected world revision, status, expiry, and confirmation result metadata. It is not source of truth for the domain mutation.
- `ai_action_audits`: V0.7 privacy-aware audit metadata for Assistant interactions. Stores request id, role, provider/model/tier, tool, proposal/mutation references, outcome, error code, duration, and small metadata. It does not store full prompts or compiled database context.
- `personal_training_examples`: V0.9 versioned feature/label/provenance rows extracted from canonical PlanBlock execution history. Features are pre-decision only; labels store later outcomes separately.
- `personal_model_versions`: V0.9 Stage-1 personal estimate versions for capacity, completion, activation, preference, routine, and state transition models. Statuses are `CANDIDATE`, `ACTIVE`, `REJECTED`, and `RETIRED`.
- `personal_pattern_evidence`: V0.9 user-visible learned pattern evidence with confidence, weighted support, status, correction metadata, and source model version.
- `personal_model_refresh_runs`: V0.9 refresh audit rows and lock points for deterministic personal-model rebuilds.
- `conversation_threads`, `conversation_messages`, `conversation_summaries`: V1.1 user-owned conversation continuity. Summaries remain separate from permanent personal memory.
- `memory_items`: V1.2 typed semantic memories with lifecycle, confidence, importance, confirmation/pinning, validity, and embedding metadata.
- `memory_evidence`: V1.2 support/contradiction provenance linked to stable sources and short excerpts.
- `memory_episodes`: V1.2 compressed historical episodes referencing event ranges and related entities.
- `recommendation_outcomes`: V1.2 user-scoped feedback about recommendations for later consolidation and learning.
- `memory_consolidation_runs`: V1.2 idempotent background-run records for episode creation.

Memory tables do not participate in canonical `world_revision`. Memory can inform context, but canonical domain records always win conflicts.

## Domain Tables

Fitness:

- `fitness_body_measurements`
- `fitness_workouts`
- `fitness_exercises`
- `fitness_workout_exercises`
- `fitness_exercise_sets`
- `fitness_workout_programs`
- `fitness_workout_templates`
- `fitness_workout_template_exercises`
- `fitness_workout_sessions`
- `fitness_progression_states`
- `fitness_recovery_observations`
- `fitness_goals`

Learning:

- `learning_courses`: course name, code, description, institution, status, ownership, version.
- `learning_exams`: course link, exam deadline, target preparation minutes, strategy version, importance, status, format/location/notes, legacy hour/date compatibility fields.
- `learning_study_requirements`: V0.6 study topics with order, importance weight, estimated required minutes, simple prerequisite topic, completed minutes, and status.
- `learning_study_sessions`: actual study execution with course/exam/topic links, optional source Action/PlanBlock links, raw duration minutes, quality rating, quality multiplier, quality-adjusted minutes, source, and idempotency key.

Kitchen:

- `kitchen_ingredients`
- `kitchen_inventory_items`: V0.8 ingredient identity records with canonical unit, source, active flag, and legacy quantity compatibility fields.
- `kitchen_inventory_lots`: V0.8 lot-level stock truth with quantity, unit, purchased time, expiry time, storage, and active/depleted status. Available inventory totals are derived from active lots.
- `kitchen_recipes`: V0.8 meal definitions with timing, servings, nutrition per serving, protein family, difficulty, tags, and active flag.
- `kitchen_recipe_ingredients`: V0.8 recipe requirements linked to inventory items when known, with quantity/unit, optional flag, substitution group, and order.
- `kitchen_meal_history`: V0.8 canonical meal execution history. Recipe meals snapshot nutrition and consume lots; manual/external meals snapshot nutrition without inventory decrement.
- `kitchen_nutrition_targets`: V0.8 active/superseded calories and protein targets by effective date.
- `kitchen_preference_evidence`: V0.8 deterministic preference signals, currently explicit/satisfaction evidence only.
- `kitchen_shopping_needs` and `kitchen_shopping_need_items`: V0.8 deduped shopping requirements derived from deterministic recommendation forecasts.
- Revision `0017_repository_integrity` retires the empty pre-v0.8 Kitchen placeholders (`kitchen_meals`, `kitchen_nutrition_logs`, `kitchen_food_preferences`, `kitchen_shopping_lists`, and `kitchen_shopping_list_items`). Current Kitchen ownership uses meal history, nutrition targets, preference evidence, meal plans, and shopping needs.
- `cognitive_traces`: immutable explicit records of bounded decision inputs, question/version, provider/model/policy identity, validated output, confidence/probabilities, latency, and status. They never store hidden reasoning.
- `decision_audits`: append-oriented downstream outcomes/corrections linked to a cognitive trace without rewriting historical provider output.
- `decision_provider_usage`: normalized per-attempt provider/model, primary/fallback/shadow role, routing reason, token units, latency, reported cost, request ID, and status/error evidence.
- `decision_disagreements`: immutable comparison evidence linking a trace/context hash, question/version, both provider results, operational result, routing policy, and optional later audit. A disagreement is not a truth label.

## Concurrency

Mutable records expose `version`. APIs that update important records should accept an `expected_version` and return HTTP 409 if the current version differs.

PlanBlock execution mutations use optimistic concurrency and valid lifecycle transitions: `planned`, `in_progress`, `completed`, `skipped`, and `missed`.

## Idempotency

Mutation endpoints can accept an `Idempotency-Key`. The same key and payload replays the stored response. The same key with a different payload returns HTTP 409.

Assistant confirmation adds another replay layer: each persisted proposal can be confirmed once, and subsequent confirmation attempts return the stored mutation result without creating duplicate Commitments, Actions, StudySessions, or other canonical records.
