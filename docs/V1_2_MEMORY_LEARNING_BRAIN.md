# Life OS v1.2 Memory & Learning Brain

Version 1.2 adds durable personal memory while preserving the Life OS authority model. Canonical services, Events, Outbox, and `world_revision` remain the source of truth. Memory can shape context, but it cannot overwrite canonical state or invoke mutations.

## Memory Layers

- **Canonical state**: commitments, actions, plans, state, fitness, learning, and kitchen records. This remains authoritative.
- **Semantic memory**: durable preferences, routines, constraints, interaction preferences, and stable personal facts represented by `MemoryItem` plus provenance in `MemoryEvidence`.
- **Episodic memory**: compressed clusters of meaningful events represented by `memory_episodes`. Consolidation never creates one episode per event.
- **Conversation memory**: thread summaries used for continuity. A summary is not automatically promoted to a personal fact.
- **Personal Learning**: deterministic behavioral observations in `PatternEvidence`. These are supplied to context separately and labeled as observations rather than memories.

## Confidence And Lifecycle

Memory confidence is calculated from evidence reliability and direction. The model does not assign the stored confidence score. Direct user confirmation creates a strong floor, pinning fixes effective confidence at `1.0`, and unpinned memory decays conservatively by type.

Lifecycle states are `candidate`, `active`, `uncertain`, `contradicted`, `archived`, and `forgotten`. Exact normalized keys merge first; semantically equivalent memories may merge when their embedding similarity crosses the configured threshold. Opposite polarity supersedes an unpinned memory. A contradiction never silently weakens a pinned memory: it creates a separate uncertain item for user review.

Forgetting soft-deletes the item, removes its embedding, and excludes it from retrieval. The evidence history remains available for auditable export. Memory writes do not emit canonical Events and do not increment `world_revision`.

## Embeddings And Retrieval

The provider-neutral `EMBEDDING` capability is active through `AIGateway`. Both fake and Gemini providers implement the same embedding contract. Stored vectors carry provider, model, dimensions, pipeline version, and timestamp metadata. PostgreSQL uses `pgvector`; SQLite tests use a JSON-backed portable type.

Retrieval is user-scoped and bounded. It combines semantic or lexical relevance, domain fit, importance, effective confidence, recency, status, and user confirmation. The default limits are six semantic memories and three episodes. If embeddings are unavailable or optional AI calls are budget-suppressed, retrieval continues with lexical scoring.

## Curation And Consolidation

The Memory Curator uses a deterministic message gate before any model call. It extracts only durable candidates and excludes plans, calendar facts, current state, inventory, and other canonical records. The fake provider supplies deterministic local behavior; production extraction uses the configured `ECONOMY` route.

The worker runs an idempotent daily consolidation for the previous UTC day. Meaningful events are grouped by domain and compressed only when the event threshold is met. Recommendation outcomes can be attached to the episode summary. A manual user-scoped consolidation endpoint is available for operations and tests.

## Context Contract

Skills explicitly opt into `semantic-memory`, `episodic-memory`, and `behavioral-patterns`. `ContextBuilderV1` presents each as a separate labeled section. Canonical data and tool results always override memory. Under context pressure, episodes, semantic memory, and patterns are removed before critical request context.

## User APIs

- `GET/POST /api/v1/memories`
- `GET /api/v1/memories/search`
- `GET/PATCH /api/v1/memories/{id}`
- `POST /api/v1/memories/{id}/pin|unpin|confirm|forget`
- `GET /api/v1/memories/episodes`
- `GET/POST /api/v1/memories/outcomes`
- `POST /api/v1/memories/consolidate`

The Personal Model screen exposes add, pin, correct, confirm, and forget controls. Memory and deterministic Personal Learning patterns remain visibly separate.

## Operations

Apply migration `0012_memory_brain`, which enables the PostgreSQL `vector` extension and creates the memory tables. Configure `AI_MODEL_EMBEDDING` and `EMBEDDING_DIMENSIONS`; changing dimensions after vectors exist requires an explicit re-embedding migration. Keep the worker running for outbox delivery and daily consolidation.
