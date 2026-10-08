# AI Boundaries

AI in Life OS is semantic, generative, and advisory. Core backend code remains authoritative.

Version 1.2 also routes text embeddings through the same audited gateway. Embeddings support similarity and retrieval only; they do not make stored memory authoritative and cannot invoke tools.

## V1.1 Intelligence Boundary

- `AIGateway`: the only provider call boundary. It normalizes `fake` and Gemini responses and records usage/errors.
- `CapabilityRouter`: maps Life OS capabilities and budget state to configured provider models.
- `SkillRegistry`: loads versioned `SKILL.md` behavior and typed tool/capability permissions.
- `SkillRuntime`: builds one bounded request and enforces skill tool, capability, and iteration limits.
- `ContextBuilderV1`: assembles stable instructions plus bounded canonical and conversation context.
- `ToolRegistry`: V0.7 explicit registry of schema-validated read and mutation tools.
- `AssistantActionProposal`: V0.7 short-lived confirmation object for consequential assistant actions.
- `AIActionAudit`: provider/model/capability/skill/token/cost/error metadata without full sensitive prompts.

The active skills are Self Core, Fitness Coach, Learning Coach, and Chef. They are constrained request handlers, not persistent independent agents.

## Forbidden AI Capabilities

AI may not:

- Execute SQL.
- Receive unrestricted database access.
- Directly edit `PlanBlock` records.
- Directly control calendar output.
- Arbitrarily mutate canonical state.
- Independently schedule the user's life.
- Execute shell commands or filesystem writes.
- Bypass confirmation, service validation, idempotency, optimistic concurrency, or WorldRevision semantics.
- Treat semantic memory, episodes, conversation summaries, or Personal Learning patterns as canonical facts.
- Invent state numbers, StudySessions, workout completion, historical facts, or memories.
- Invent inventory, nutrition history, meal completion, food preferences, or shopping needs.
- Train, refresh, promote, or fabricate Personal Learning models or evidence.

## V0.7 Assistant Boundary

The Assistant is an interface to Life OS. It may parse natural language, classify intent, summarize bounded context, ask clarifying questions, propose structured mutations, and communicate canonical service results.

All action-capable output must become a validated `AssistantIntent` and then pass through `ToolRegistry`. Unknown tools are rejected. There is no SQL, shell, direct calendar, direct PlanBlock, or generic database-write tool.

Read-only Assistant requests, clarification, discussion, proposal creation, cancellation, and failed confirmation do not create canonical domain events and do not increment `world_revision`. Confirmed mutations call existing domain services, so the existing semantic `Event`, `OutboxEvent`, and WorldRevision behavior remains authoritative.

Consequential proposals are persisted server-side and revalidated on confirmation. Replay/double-click confirmation returns the stored result. Stale world revisions are rejected before mutation.

## Memory Architecture

Future memory layers may include canonical structured facts, learned behavioral parameters, episodic memories, conversational working memory, and an Obsidian-style linked knowledge graph.

Future memories may include title, type, content, confidence, importance, evidence, source, validity dates, links, and optional embeddings. `pgvector` may be introduced later.

AI must never receive the whole database as context. v1.1 adds server-side conversation working context and compaction but does not implement permanent memory, embeddings, pgvector retrieval, or an automatic long-term fact store.

See `V1_1_INTELLIGENCE_FOUNDATION.md` for provider, skill, conversation, context, and cost architecture.

## V0.8 Chef Boundary

Chef is an interface to deterministic Kitchen services. It may read Kitchen status, no-shopping recommendations, shopping needs, and propose confirmed meal logging/completion through registered tools. Chef does not score meals with AI, does not mutate inventory directly, does not create PlanBlocks, does not provide medical nutrition advice, and does not order groceries.

## V0.9 Personal Learning Boundary

Personal Learning is deterministic backend infrastructure, not an AI agent. It derives versioned examples from canonical history, computes Stage-1 estimates, compares candidate model versions against baselines, and exposes bounded planner parameters. The Assistant may read the Personal Learning summary through a read-only tool, but it cannot refresh, train, promote, correct evidence, or create synthetic evidence. Learned estimates are never hard constraints and never write PlanBlocks.
