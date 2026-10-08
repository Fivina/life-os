# Life OS v1.1 Intelligence Foundation

This version implements the intelligence runtime described by the Life OS 2.x Implementation Handbook while preserving the deterministic modular monolith. Canonical services, Events, Outbox, and `world_revision` still own reality. AI interprets requests and invokes explicit tools; it does not write database state directly.

## Request Flow

1. `AssistantService` resolves or creates a user-owned conversation and persists the user message.
2. `SkillRegistry` selects the enabled skill assigned to the requested compatible assistant role.
3. `ContextBuilderV1` builds a stable prefix and bounded dynamic context.
4. `SkillRuntime` requests an allowed capability and calls the central `AIGateway`.
5. `CapabilityRouter` resolves capability, budget state, provider, model, and request settings.
6. The provider returns normalized `AIResponse`, structured `AssistantIntent`, or tool calls.
7. `SkillRuntime` enforces the skill whitelist, capability ceiling, and tool-call cap.
8. The existing `ToolRegistry` revalidates role permission, typed arguments, and confirmation policy.
9. Canonical services execute approved tools and retain normal Event/Outbox/WorldRevision behavior.
10. Read tools may use one finalization call with no tools exposed; failures fall back to the canonical tool message.
11. The assistant response and AI usage metadata are persisted.

There is no SQL, filesystem, arbitrary service, or unrestricted internal API tool.

## AI Gateway

Provider-neutral types live in `backend/app/ai/types.py`. `AIGateway` is the only application path to provider calls and records both successful and failed attempts. The current providers are:

- `fake`: deterministic compatibility provider used by automated tests and local development.
- `gemini`: production-capable REST provider with structured response, function declaration, usage, timeout, rate-limit, and malformed-response handling.

Capabilities are `ECONOMY`, `FAST`, and `REASONING`. `VISION`, `IMAGE`, and `EMBEDDING` exist only as typed future capabilities and are intentionally unrouted in v1.1.

Configuration:

```dotenv
AI_ENABLED=true
AI_PROVIDER=gemini
AI_MODEL_ECONOMY=<configured-model>
AI_MODEL_FAST=<configured-model>
AI_MODEL_REASONING=<configured-model>
GEMINI_API_KEY=<backend-secret>
AI_TIMEOUT_SECONDS=15
```

Provider keys are read only by backend settings and are never returned by the provider-status API.

### Adding A Provider

1. Implement the `AIProvider` protocol and normalize all results into `AIResponse`.
2. Translate vendor errors into `AIProviderError` categories.
3. Register the provider once in `app.ai.gateway.AIGateway`.
4. Add configuration and deterministic provider tests.
5. Do not import the provider from a domain or skill.

## Routing, Budget, And Cost

Skills request capabilities, never vendor model IDs. `CapabilityRouter` maps capability to configured models and applies centralized budget signals. Budget thresholds may downgrade routing to `ECONOMY` or suppress optional calls; deterministic application behavior remains available.

`AIActionAudit` records provider, model, requested/effective capability, skill and prompt versions, conversation/request references, token counts, tool-call count, duration, status, errors, and estimated cost. Pricing is supplied by `AI_MODEL_PRICING_JSON`, for example:

```json
{
  "configured-model": {
    "input_per_million_eur": 0.1,
    "cached_input_per_million_eur": 0.025,
    "output_per_million_eur": 0.4
  }
}
```

`GET /api/v1/assistant/usage` exposes user-scoped monthly totals and provider/model/capability/skill groupings without prompt content.

## Skills

Version-controlled skills live under `backend/skills/<name>/` with:

- `SKILL.md`: behavioral boundaries and reasoning instructions.
- `skill.yaml`: typed permissions and runtime policy.

v1.1 includes `self-core`, `fitness-coach`, `learning-coach`, and `chef`. Their manifests define role assignment, enabled state, default and maximum capability, exact allowed tools, scopes, tool-call and iteration limits, confirmation policy, and cost class. Startup fails clearly for malformed manifests, unknown tools, duplicate role assignments, or missing instructions.

### Adding A Skill

1. Create `backend/skills/<skill>/SKILL.md` with behavior, boundaries, and clarification guidance.
2. Add a valid `skill.yaml`; use only names already present in `ToolRegistry`.
3. Assign an unclaimed compatible assistant role.
4. Choose conservative capability and tool-call limits.
5. Add registry, permission, context isolation, and runtime tests.

Domain logic must remain in canonical services. A skill is policy, instructions, and permissions, not a parallel domain implementation.

## Conversations

`ConversationThread`, `ConversationMessage`, and `ConversationSummary` are user-scoped. Messages carry a deterministic per-thread sequence number. The APIs support create, list, retrieve, send, and archive. The legacy `recent_messages` request field remains accepted during migration, but server history is authoritative.

When the configurable threshold is crossed, old messages are compacted into a bounded conversation summary while a recent raw window remains. Raw records are retained in v1.1 for auditability. This summary is working conversation context, not permanent personal memory.

Conversation writes do not increment `world_revision` and do not emit domain events. Any mutation invoked through a conversation still uses its canonical service and existing event behavior.

## Context Builder

The stable prefix contains:

- Life OS intelligence constitution;
- selected `SKILL.md`;
- allowed tool schemas;
- structured output and runtime contract.

The dynamic section contains the current request, thread/summary reference, recent persisted messages, current time, `world_revision`, and bounded role-relevant canonical state from existing context services. Low-priority dynamic sections are omitted first when the configured character budget is exceeded. Stable safety instructions and the current request are never silently removed.

The stable prefix receives a deterministic cache key. Correctness does not depend on provider caching, and volatile canonical or conversation state is never included in that cache identity.

## Deliberate Limits

v1.1 does not implement semantic or episodic memory, embeddings, a Memory Curator, Planner V2, receipt OCR, Finance, autonomous tool loops, or learned domain recommendation engines. Conversation summaries are not promoted to long-term facts. These extension points can be added through new context sections and capabilities without moving canonical authority into the model.
