# Architecture

## v2.0 Integrated Core

v2.0 keeps one modular-monolith execution path per responsibility. Self Core orchestrates bounded context, workspaces, skills/tools, and attention; canonical mutations still pass through domain services; only `app.planning` constructs `PlanBlock`; Events, Outbox, and WorldRevision provide committed change history to realtime clients. Optional language and decision providers remain behind separate `AIGateway` and `DecisionGateway` boundaries and are not required for core operation. See `V2.0_CORE_RELEASE.md`.

## v1.9A Unified Self Core

The primary Self Core surface composes persistent conversation, reconstructed GlobalWorkspace, foreground ActiveWorkspace, current Planner output, active PlanProposal, relevant AttentionItems, and bounded domain signals. `SelfCoreOrchestrator` selects deterministic host routes before falling back to the existing `SkillRuntime`; `ToolRegistry` remains the permission boundary and `ResponseComposer` remains the prose boundary. Morning briefing is a versioned projection, not canonical state. See `V1.9A_SELF_CORE.md`.

## v1.8D Natural-Language Chef

v1.8D interprets bounded natural-language requests through AIGateway into a versioned `MealIntent`, then returns authority to deterministic Kitchen code. Canonical recipes, safe inventory lots, nutrition snapshots, typed Fitness context, a minimal Finance grocery signal, recent meals, preferences, and technique evidence produce inspectable recommendation factors. Selection reuses MealPlan; execution reuses ActiveWorkspace/CookingSession; confirmed actual usage alone mutates inventory. See `V1.8D_CHEF_INTELLIGENCE.md`.

## v1.8C Social Trajectory And Opportunities

v1.8C reuses `Goal`/`Trajectory` for a configurable, non-diagnostic meaningful-activity target and records qualifying evidence in `SocialActivity`. `Opportunity` is canonical discovered content, never a `Commitment` or `PlanBlock`. The pipeline is fetch, typed normalization, conservative deduplication, deterministic hard filters, explicit-signal matching, optional bounded DecisionGateway judgment for ambiguous survivors, Planner feasibility, and AttentionManager. See `V1.8C_SOCIAL_OPPORTUNITIES.md`.

## v1.6A Decision Infrastructure

`app.decision` provides a dormant typed-decision path separate from the generative `app.ai` gateway. Versioned questions, bounded structured context, a provider-neutral gateway, deterministic fake provider, immutable cognitive traces, append-oriented audits, and a contract benchmark are implemented. No existing workflow is connected automatically, and no component outside planning gains `PlanBlock` authority. See `V1.6A_DECISION_INFRASTRUCTURE.md`.

## v1.6B Situation and Attention

v1.6B adds a reconstructable bounded `GlobalWorkspace`, persisted activity continuity, structured open/prospective threads, deterministic attention and curiosity policy, dynamic contributor activation, and a thin cognitive-cycle coordinator. See `V1.6B_WORKSPACE_ATTENTION.md` for state boundaries and lifecycle details.

## v1.6C Feedback Evidence

v1.6C adds an isolated `Log feedback` interaction that freezes one meaningful completed cognitive decision, records dimension-specific user ratings, appends outcome audit evidence, derives provenance-rich training examples for non-skipped ratings, and computes quality aggregates. Feedback sessions remain separate from conversations and active workspaces and have no canonical write authority. See `V1.6C_INTELLIGENCE_FEEDBACK.md`.

## v1.6D Provider Routing

v1.6D adds optional lazy local Laya and external Jev adapters behind `DecisionGateway`, deterministic routing/fallback/shadow policy, provider usage and disagreement evidence, health status, and a versioned synthetic benchmark. AUTO now prefers Jev for supported typed decisions and retains Laya as fallback. Jev keys are per-user Vault secrets, not process configuration. Shadow output has no operational authority and candidate benchmark profiles never self-activate. See `V1.6D_PROVIDER_ROUTING.md`.

`GlobalWorkspace` is not canonical state, `ActiveWorkspace` is not a conversation, and `AttentionAction` is not a side effect. Domain services and the central Planner retain all canonical mutation authority.

## v1.5 Kitchen And Finance Automation

Kitchen v1.5 adds canonical ingredient identity, secure provider-neutral receipt import, persisted Chef recommendations and outcomes, MealPlans, cooking competency, aggregated shopping, and dependency-aware shopping/cooking Actions. Finance adds reviewed CSV imports, merchant/category learning, Decimal transactions, budgets, recurring evidence, safe-to-spend, and receipt reconciliation. Only bounded grocery-budget context crosses from Finance to Kitchen. See `V1.5_KITCHEN_FINANCE_AUTOMATION.md` and `POST_V1_5_INTEGRATION_AUDIT.md`.

## v1.4 Domain Intelligence

Core domains publish stable requirements as shared Action variants through the Domain Planning Contract. `DomainRefreshService` reconciles Learning, Fitness, Home, and Goal-derived priority state before rolling allocation. Planner V2 alone compiles Actions and Constraints into PlanBlocks. Calendar execution routes actual outcomes back to canonical domain services, which emit transactional events and generate the next need. See `DOMAIN_CONTRACT.md` and `V1.4_CORE_DOMAIN_INTELLIGENCE.md`.

Life OS is a modular monolith with a React PWA client and a FastAPI backend. PostgreSQL is the canonical production database. Supabase Auth/PostgreSQL is the current reference managed deployment, not an architectural dependency of domain or planning logic.

## Backend Modules

- `api`: versioned FastAPI routes under `/api/v1`.
- `core`: settings, logging, and shared runtime concerns.
- `database`: SQLAlchemy base, session, and models.
- `events`: event append, world revision, idempotency, and outbox processing.
- `state`: timestamped user state observations.
- `domains`: Fitness, Kitchen, Learning, Home, Goals, and Finance specialist domains. Kitchen and Finance integrate through typed, bounded budget and receipt contracts rather than shared table access.
- `planning`: future planner interfaces and simulation harness.
- `personal_model`: V0.9 bounded Personal Learning subsystem. It extracts versioned examples from canonical history, builds Stage-1 estimates, promotes only calibrated model versions, exposes soft planner parameters, and records user-correctable pattern evidence. It never schedules.
- `ai`: v1.1 provider-independent gateway, normalized provider types, Gemini/fake adapters, capability routing, budget policy, and usage accounting.
- `decision`: bounded typed-decision contracts, fake/Laya/Jev adapters, gateway, context builder, deterministic routing, provider evidence, contributors, traces/audits, and benchmark harness. Real providers are disabled by default.
- `workspaces`: v1.6B typed activity continuity plus reconstructable situation snapshots.
- `threads`: v1.6B open/prospective thread lifecycle and deterministic eligibility.
- `attention`: v1.6B host attention policy, curiosity policy, and pending-item lifecycle.
- `cognition`: v1.6B bounded contributor routing and cognitive-cycle coordination. It is disabled by default.
- `feedback`: v1.6C reserved-command matching, trace targeting, bounded interviews, training-example derivation, and computed quality summaries. It is disabled by default.
- `skills`: v1.1 manifest registry and bounded skill runtime; behavioral source files live in `backend/skills`.
- `conversations`: v1.1 user-scoped threads, messages, summaries, ordering, and compaction.
- `assistant`: natural-language interface, Context Builder V1, explicit tool registry, proposal confirmation flow, and compatibility schemas.
- `notifications`: notification intent foundation.
- V1.0 production support: Supabase JWT auth mapping, single-user allowlist, health/readiness, request IDs, authenticated export, PushSubscription, idempotent push delivery, and an independent outbox worker.

## Data Flow

Important mutations should run in one transaction:

1. Update queryable current state.
2. Append an immutable `Event`.
3. Append an `OutboxEvent` when integration work is needed.
4. Increment the user's `world_revision`.

This is not pure event sourcing. The system keeps both queryable current state and historical event history.

Assistant requests follow a stricter boundary:

1. The user message is persisted in a user-owned conversation.
2. `SkillRegistry` selects an enabled role-compatible skill and `ContextBuilderV2` assembles bounded context.
3. `SkillRuntime` requests a capability through the central AI Gateway and enforces the skill whitelist.
4. `ToolRegistry` validates tool name, role permission, arguments, and confirmation policy.
5. Read tools return canonical service summaries without domain events.
6. Mutation tools either create a confirmation proposal or call canonical services.
7. Canonical services remain responsible for events, outbox, world revision, conflicts, and domain invariants.

Kitchen requests follow the same deterministic source-of-truth rule as other specialist domains:

1. Inventory state is derived from active `InventoryLot` rows, not planned meals.
2. Recipe completion validates units/availability, consumes earliest-expiring lots first, snapshots a `MealHistory`, and emits Kitchen events.
3. Meal recommendation is deterministic and explainable; no AI is needed for scoring.
4. Shopping needs can become normal `Action` rows with `domain="kitchen"`.
5. Only the Core Planner writes `PlanBlock` rows. Kitchen never schedules directly.

Personal Learning follows a stricter non-authority rule:

1. Training examples are derived from canonical Plans, PlanBlocks, Actions, StateObservations, and domain evidence.
2. Candidate model versions are compared with Stage-0 baselines and rejected when evidence, confidence, or calibration is insufficient.
3. Active model parameters are compiled once into an immutable `PersonalModelSnapshot` at plan-generation start.
4. The Core Planner may use learned values only as bounded capacity, ranking, activation, preference, or routine inputs.
5. Personal Learning never writes `PlanBlock` rows, never creates hard constraints, and never suppresses goal-critical work by itself.

## Reference Deployment Shape

The current deployment recipe uses Cloudflare Pages for the frontend, Render for the API and worker, and Supabase for PostgreSQL and Auth. Equivalent hosts are valid when they preserve PostgreSQL semantics, the backend authorization boundary, worker/outbox behavior, secret handling, and backup requirements.

The browser uses Supabase Auth endpoints only. It does not use Supabase Data API tables as canonical application access; all domain data flows through the FastAPI backend.
