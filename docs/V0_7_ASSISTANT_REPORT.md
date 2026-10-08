# V0.7 Assistant Report

## 1. Release Purpose

V0.7 adds a natural-language Assistant as an interface to Life OS while preserving deterministic control. It parses requests into structured intents, compiles bounded context, routes through an explicit tool registry, and delegates every canonical mutation to existing services.

## 2. Preconditions

V0.1 State, V0.2 Commitments and Intentions, V0.3 Core Planner, V0.4 Daily Control Loop, V0.5 Fitness, and V0.6 Learning were already implemented and passing before this work.

## 3. Repository Audit

Existing AI code was limited to interface protocols in `backend/app/ai/interfaces.py`. The Assistant page was a placeholder. Backend services already existed for State, Commitments, Actions, Planner/control loop, Fitness, Learning, Events, Outbox, WorldRevision, idempotency, settings, auth, and typed web API patterns.

## 4. Architecture Reused

The implementation reuses existing FastAPI route structure, SQLAlchemy models/migrations, settings conventions, development bearer auth, domain services, planner services, V0.4 control loop, V0.5 Fitness service/context, V0.6 Learning service/context, and frontend React Query API patterns.

## 5. Deviations

No live paid model provider was added. V0.7 uses a deterministic `fake` provider for reproducible tests and local operation. The provider abstraction is ready for a future adapter, but provider SDK integration is intentionally deferred.

## 6. Assistant Architecture

New backend modules live under `backend/app/assistant`: `gateway.py`, `schemas.py`, `context.py`, `tools.py`, `service.py`, and `audit.py`. API endpoints live in `backend/app/api/routes_assistant.py`.

## 7. AI Gateway

`AIGateway` owns provider selection, model tier mapping, AI disabled behavior, and normalized provider errors. Provider use is not scattered across routes or domain services.

## 8. Provider Configuration

Server-side settings now include `AI_ENABLED`, `AI_PROVIDER`, `AI_MODEL_DEFAULT`, `AI_MODEL_STRONG`, and `AI_TIMEOUT_SECONDS`. No provider secret is exposed to frontend code or API responses.

## 9. Structured Output

The Assistant uses `AssistantIntent` with type, domain, tool name, validated arguments, confirmation flag, summary, confidence, and model tier. Consequential actions never depend on free-form prose.

## 10. Model Escalation Policy

Default path is `STANDARD`. Requests containing cross-domain synthesis/tradeoff language select `STRONG`. Discussion/no-action can return `NO_AI`. Planner scoring, trajectories, capacity, fitness progression, learning risk, validation, and confirmation rules do not use AI.

## 11. ContextCompiler

`ContextCompiler` compiles compact context per user, role, request, timestamp, timezone, and recent messages.

## 12. Context Budget

The compiler limits plan blocks, commitments, planning pool actions, and recent messages. It includes a context budget marker and never emits the whole database.

## 13. General Assistant

General context includes latest state, today plan summary/slices, hard commitments, planning pool summary, Learning status highlights, and Fitness status highlights.

## 14. Fitness Coach

Fitness role receives Fitness coach context, relevant fitness plan window, and current state. It does not automatically receive Learning context.

## 15. Learning Coach

Learning role receives Learning context, relevant learning plan window, and current state. It does not automatically receive Fitness context.

## 16. ToolRegistry

`ToolRegistry` registers named tools with description, argument schema, read/mutation classification, allowed roles, confirmation policy, and canonical handler.

## 17. Tool Permission Matrix

General can use general reads/mutations plus bounded Fitness/Learning read summaries. Fitness Coach can use Fitness tools and common state/plan reads. Learning Coach can use Learning tools and common state/plan reads. Cross-specialist unauthorized attempts are rejected server-side.

## 18. Read vs Mutation Classification

Read tools: today summary, current state, current plan, plan block explanation, commitments, planning pool summary, fitness status, learning status, exam status. Mutation tools: report state, create commitment, add intention, request replan, fitness execution/measurement tools, and learning course/exam/study tools.

## 19. Confirmation Policy

Read/explain tools never require confirmation. Commitment creation, StudySession logging, workout execution recording, course/exam mutations, and other consequential/ambiguous mutations require confirmation. Explicit state reports and simple intention creation can execute directly after validation.

## 20. AssistantActionProposal

`assistant_action_proposals` persists validated tool arguments, role, summary, expected world revision, expiry, status, confirmation requirement, idempotency key, and stored result metadata.

## 21. Replay/Stale Protection

Confirmation validates ownership, pending status, expiry, tool registration, role permission, argument schema, and expected world revision. Confirming an already confirmed proposal returns the stored result without duplicate mutation.

## 22. Discussion vs Action

Discussion fixtures such as "Maybe I should skip gym" return `NO_ACTION` and do not mutate any canonical records.

## 23. Clarification Policy

Consequential missing information triggers `CLARIFICATION`. Vague state input such as feeling worse does not invent numbers; it asks for Energy and Mental State values.

## 24. State Tool

`report_state` validates `StateObservationCreate`, calls `state.service.create_observations`, and then evaluates the day through V0.4 control loop.

## 25. Commitment Tool

`create_commitment` validates `CommitmentCreate` and calls the canonical Commitment service. Natural-language commitment creation returns a proposal before mutation.

## 26. Intention Tool

`add_intention` validates `ActionCreate` and calls the canonical Action service. It creates flexible Actions only; it never writes PlanBlocks.

## 27. Replan Tool

`request_replan` calls V0.4 `manual_replan`. It does not construct or edit PlanBlocks directly.

## 28. Fitness Tools

Fitness read uses V0.5 `status_summary`. Mutation wrappers call `start_workout`, `log_set`, `complete_workout`, and `add_body_measurement`.

## 29. Learning Tools

Learning read uses V0.6 `status_summary` and exam trajectories. Mutation wrappers call course/exam services and `log_study_session` with idempotency on confirmation.

## 30. Plan Explanation / DecisionFactors

`get_plan_block_explanation` selects a current/referenced PlanBlock, reads stored block or plan DecisionFactors, and returns a concise explanation without chain-of-thought.

## 31. AIActionAudit

`ai_action_audits` records request id, role, provider, model, tier, tool, proposal/mutation reference, status, error code, duration, and metadata.

## 32. Privacy-Aware Logging

Audit does not store full prompts, compiled context, or full database records.

## 33. Events

Normal chat messages, reads, proposals, cancellations, provider failures, and rejected confirmations do not create domain events. Confirmed canonical mutations create existing semantic events.

## 34. WorldRevision

Read-only, clarification, proposal, cancel, and failed confirmation paths do not increment WorldRevision. Confirmed canonical mutations increment via existing services.

## 35. API Surface

Added `POST /api/v1/assistant/message`, `POST /api/v1/assistant/proposals/{id}/confirm`, and `POST /api/v1/assistant/proposals/{id}/cancel`.

## 36. Assistant UI

The Assistant page now supports empty, composing, sending, informational, clarification, proposal, executing/confirming, mutation success, semantic error, no-action, explanation, and provider-unavailable states.

## 37. Home Ask/Add

Home "Ask or add something" now submits to `/assistant` with the query prefilled.

## 38. Provider Failure / Disabled Mode

Provider failures return typed `ERROR` responses with no mutation. `AI_ENABLED=false` causes gateway rejection without breaking deterministic Life OS features.

## 39. Security Boundaries

There is no SQL, shell, direct calendar mutation, direct PlanBlock mutation, generic database query, or generic database write tool. Prompt injection can only request registered tools and still passes permissions/confirmation.

## 40. Database Migration

Migration `0007_assistant` creates `assistant_action_proposals` and `ai_action_audits`. It applies after `0006_learning_domain` and has a downgrade.

## 41. Automated Tests

Backend tests now cover gateway disabled mode, fake provider paths, bounded context isolation, tool permissions, proposals, confirmation, cancellation, replay, stale rejection, state ambiguity, commitment/intention/study fixtures, plan explanation, provider failure, forbidden tool rejection, events, and WorldRevision. Frontend tests cover Assistant rendering, submission, loading-ish transitions, info, clarification, proposals, confirm, cancel, mutation success, semantic/provider error, no-action, plan explanation, specialist role, and Home prefill.

## 42. Manual Acceptance

Live smoke tested after migration and backend restart: read-only Fitness query returned `INFORMATION`; commitment fixture returned a proposal; the smoke proposal was cancelled without mutation.

## 43. Known Limitations

The fake provider only supports deterministic fixture parsing. Natural-language coverage is intentionally narrow until a real provider adapter is added.

## 44. Deliberate Deferrals

No V0.8 Kitchen/Chef, external calendar integration, proactive agent, long-term memory, embeddings, pgvector, learned behavior models, or autonomous background assistant were implemented.

## 45. User Friction Observed

The Assistant is conservative: some ambiguous actions require clarification or confirmation. This is intentional for V0.7 safety.

## 46. Interfaces Created for V0.8 / future Memory

Context includes `memory: None` as a future-compatible placeholder. No memory tables or retrieval paths were added.

## 47. Acceptance Checklist

All V0.7 acceptance fixtures A-J passed in automated tests or live smoke: commitment proposal/confirm, intention, state clarification and explicit mutation, plan explanation, Learning query, Fitness query, StudySession proposal/confirm/replay, discussion/no-action, forbidden SQL, provider failure, specialist isolation, regression tests, migration, typecheck, and build.

## 48. Release Decision

PASS

## 49. Readiness for V0.8

V0.8 can begin after V0.7 is accepted. Kitchen work can reuse the same Assistant boundary later, but V0.7 intentionally did not start V0.8.
