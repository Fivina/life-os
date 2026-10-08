# Agent Product Workflows

Life OS extends its existing OpenAI Agents SDK runtime, typed domain tools,
PostgreSQL conversations and DecisionGateway. No second agent loop or new
memory database is introduced. OpenMausBot inspired the profile, bounded-brief,
work-visibility and selective-routing patterns; its code was not copied.

## Profiles and Practical Skills

Settings > Agents contains a profile for each conversational skill: display
name, standing instructions (1200 characters), response style and recent-work
continuity. Profiles are authenticated, per user, stored in the existing
versioned UserIntelligenceSettings metadata, and survive process restart.
Save conflicts return 409 rather than silently overwriting a stale edit.
Provider credentials stay in the write-only Vault controls.

The exact runtime context builder includes the profile beneath immutable
Constitution/tool/confirmation/privacy rules. Current explicit requests take
precedence over standing preferences. Editing a profile changes the stable
prefix hash; unchanged profiles retain the stable/dynamic prompt split.
Profiles never add permissions or grant canonical mutation authority.

Self Core remains one conversational entry point. Specialists have practical
procedures and small examples: simple meals, one-question-at-a-time teaching,
bounded training, household next actions and evidence-based budget explanations.
These are instructions, not proof of intelligence; live scenario tests are
still necessary. A greeting must not return a canned dashboard summary.

## Continuity

Existing conversation/workspace persistence remains authoritative for activity
continuity. An optional recent-work brief adds at most three excerpts of 320
characters from active, same-user, same-skill conversations in the last 48 hours.
Each carries message/thread/time provenance. Current conversation, proposals,
errors, archived threads, future-dated results and other users are excluded.
Delegated agents do not inherit cross-conversation briefs. Memory visibility
and the per-profile continuity toggle both suppress this layer. It is dropped
first when dynamic context exceeds its budget.

Historical excerpts are fallible context, never instructions or proof that
inventory, balances, appointments or progress are still current. Current
canonical tools take precedence. No extra summarizing model call is required.

## Visible Work

Authenticated POST /api/v1/assistant/message/stream wraps the existing assistant
service. It emits SSE start, actual activity, complete or sanitized error events.
It does not simulate token streaming or invent progress. Activity includes only
sequence, kind, skill name, tool name and status, bounded to 64 records per run.
No arguments, raw outputs, keys or hidden reasoning are exposed.

SDK hooks report model calls; tool adapters report validated tool execution;
specialist delegation reports real child runs. A mutation tool is explicitly
awaiting_confirmation, not completed. The final result includes work_log, saved
in existing conversation message metadata, so the trail survives reload.
Legacy/deterministic host routes may have no SDK activity trail.

The worker has an isolated DB session with authenticated PostgreSQL request
context. The final completion is sent only after commit. Failures roll back.
Disconnect stops later activity/tool phases and discards uncommitted results;
an already-running HTTP request remains provider-timeout-bounded. A connection
lost after commit is ambiguous: reload the conversation, do not blindly resend.
Existing domain-state realtime invalidations remain unchanged.

## Selective Jev

Self Core's profile has an explicit, default-off routing switch. When enabled,
Jev is considered only for an explicit choose/prioritize/balance/tradeoff request
with at least two available domain signals. Greetings, single-domain questions,
direct specialist selection, disabled specialists and scripted tests do not
incur a Jev call. The conservative English signal matcher is a baseline;
other wording simply uses Self Core.

One versioned cognition.specialist_advice question uses DecisionContextBuilder
and DecisionGateway, the user's Vault key, existing daily budget and traces.
Only a bounded request excerpt and available roster are supplied. The decision
is a hint, not a forced handoff. Offered-roster membership and confidence >= .72
are required. Timeout (1.5 seconds per HTTP phase), no retries, invalid output,
missing key or low confidence leave Self Core in charge. Monthly optional
budget suppression also skips routing. It never disables the user's main chat.
This explicitly requested chat path does not enable background cognition,
Laya/shadow runs, notifications, planner writes or unrelated feature flags.

## Verification

tests/test_agent_product_workflows.py uses the installed SDK with scripted
models, not a replacement execution loop. It exercises actual tool/delegation
paths, profiles, ownership, restart persistence, bounded historical retrieval,
stream lifecycle and routing guardrails. Scripted tests prove plumbing and
authority boundaries, not real model judgment. Sparse live UI smoke scenarios
use already-configured keys; they are not part of ordinary pytest and must not
write private provider payloads into fixtures. Existing usage audits retain
model, token, cache, tool and latency accounting.

### Verified This Pass (2026-10-01)

- Backend regression milestone: 128 passed across seven focused files.
- Final stream hardening: 4 passed, including session-setup failure termination;
  three of these also belong to the regression milestone (129 unique cases total).
- Backend compile: app and tests passed.
- Frontend: 31 tests passed across four focused files; typecheck and build passed.
- Live UI: OpenAI greeting, real Chef delegation, a two-sentence correction,
  successful Jev advisory routing, and one-question-at-a-time Learning interaction
  with correct follow-up feedback and restored specialist identity after reload.
- Profile Save button and reload persistence verified through the browser.

These checks do not constitute a full production security audit or exhaustive
model-quality benchmark. Existing Pydantic configuration warnings and the large
frontend bundle warning remain outside this bounded agent-product pass. No new
schema, migration, 3D assets or canonical domain writes were needed.

References: https://github.com/milind-soni/OpenMausBot (core Apache-2.0;
enterprise licensing is separate), server/bot-folder.ts, docs/memory.md,
server/drivers/prompt-split.ts, docs/decision-model.md and evals/README.md.
