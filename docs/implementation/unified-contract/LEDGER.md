# Unified contract requirement and execution ledger

Source: `source/LIFE OS Unified Implementation Contract.pdf` (88 pages), SHA256
`e6014e7b65f72017791f8b85e326d41ce1d3b0674fb45a4a9fa374f64f9f0a70`.
Full-resolution figures: `source/Photos/`; byte verification: `ASSET_MANIFEST.md`.
Extracted text: `CONTRACT_SOURCE.md`; the unchanged PDF controls tables/figures.
Intake date: 2026-10-08. Branch: `codex/unified-contract`, workspace `D:/Life OS`.

This is execution tracking, not a replacement specification. Document instructions
define product constraints; they do not grant authority to publish publicly, buy
services, connect real banks, disclose secrets, or override the user's instructions.
The direct request authorizes development orchestration with careful usage and
bounded workers. No Figma or external design tool is required.

## Status and accounting

PENDING = unstarted or existing behavior not yet evaluated against the full contract.
IN_PROGRESS = assigned/current work. IMPLEMENTED = code exists, acceptance incomplete.
VERIFIED = required checks/review passed, with evidence. BLOCKED_DECISION = explicitly
unapproved contract. BLOCKED_EXTERNAL = missing configuration/provider evidence.
User visual acceptance is recorded separately; agent review cannot supply it.
No overall completion percentage is claimed; rows cover grouped criteria, not equal
effort. Related tasks must satisfy their parent criteria before closing the parent.

## Source coverage and workstreams

| ID | PDF pages / contract section | Scope and acceptance boundary | Owner | Status / dependency |
| --- | --- | --- | --- | --- |
| W0 | 1–5, 18–21, 51, 79–88 | Source preservation, live implementation map, conflicts, screenshot baseline, targeted checks | Primary | VERIFIED intake/baseline; code maps remain scoped evidence, not whole-product acceptance |
| NAV-001 | 6–7, 19, 47, 80–82 | Direct single-click primary navigation, no flyout/interstitial, legacy links/history retained | Primary + bounded shell worker | PENDING; W0 |
| DEV-001 | 7, 80–84 | Developer separate from Settings/Life; final visual/access design stays open | Primary | PENDING; final design BLOCKED_DECISION |
| CHAT-001 | 8–11, 19, 28–31, 80–83 | White original orb, Self→Chat aliases, real persisted threads/new/resume/available roles; permissions/history intact | Shell worker | PENDING; W0/W1 |
| PHENGOS-002 | 8–11, 16, 19, 47 | Shared top-right domain orb/floating overlay, same canonical thread, draft/focus/context/route/grid preserved, no bottom dock | Shell worker | PENDING; W1 |
| COPY-001 | 6, 12, 19–20, 38–41 | Remove slogans/decorative date chips; retain functional dates/status/instructions | Domain owners | PENDING; W1/domain migrations |
| MOTION-001 | 16, 19–20, 47–48 | Shared finite neon strip/transitions, stable geometry, reduced motion and focus | Shell worker | PENDING; W1 |
| CAL-001 | 11–12, 19, 23, 81–84 | Preserve grid/rail; Overview/Daily List/Planning; real edit/error/version flows; no seeded forms | Calendar worker | PENDING; W1 |
| KIT-001.OVERVIEW | 12–14, 19–20, 24–27 | Five tabs exact order, content-aware grid without hero void, real daily-first state | Kitchen worker | PENDING; W1 |
| KIT-001.FRIDGE | 14–15, 19 | Search/edit/consume/staples/expiry and receipt review preserved through existing services | Kitchen worker | PENDING; W1 |
| KIT-001.MEALS | 14–15, 19, 84 | Actual history read, manual log, planned/cooked/eaten distinctions, cooking restore; optional 2–3-day horizon | Kitchen worker | PENDING; bounded history API if absent |
| KIT-001.RECIPES | 14–15, 19 | Real recipe browse/detail/create/cook, history/provenance and media fallback | Kitchen worker | PENDING; W4/media |
| KIT-001.SHOPPING | 15, 19 | Canonical grouped needs/purchases and focused manual input; no invented history | Kitchen worker | PENDING; W4 |
| FIT-001 | 32–35, 42–44, 47–48 | Recompose existing training/sets/readiness/measurements; correct Y-value/X-time and truthful missing data | Fitness worker | PENDING; W1/W4; gated additions below |
| FIN-001 | 36–38, 44–45, 47, 49 | Single Overview/Transactions/Budgets/Debts/Analytics strip; real bank-first hierarchy and source-aware values | Finance worker | PENDING; W1/W2/W6; gated additions below |
| MOV-001 | 38–40, 45–49 | Exactly Overview/Watchlist/Logs, poster-first, no profile/fourth tab, import link to Settings | Movies worker | PENDING; W1/W2/W7; gated additions below |
| BE-INTEGRATIONS.STORE | 54–55 §4, 62 §10.3, 73 | Extend existing write-only Vault; tenant/installation/internal connection boundaries; safe replacement/delete; fail closed | deep worker `integration_vault` | IMPLEMENTED;31 tests pass; hosted SQL/Vault and independent review pending |
| BE-INTEGRATIONS.API | 54–55 §4 | Generic list/put/delete/test, sanitized status/test timestamps; safe non-secret configuration | deep worker `integration_vault` | IMPLEMENTED; scoped/redaction/mock transport tests pass; independent review pending |
| BE-INTEGRATIONS.UI | 54–55 §4 | /settings/integrations and /tmdb detail, write-only input/test/remove, real status/configuration | fast worker then standard worker `settings_completion` | IMPLEMENTED;15 focused tests +typecheck pass; isolated runtime/independent review pending |
| BE-INTEGRATIONS.LETTERBOXD | 54–55, 62–63 | Settings baseline import/history/resolve/confirm; one shared importer, never live Connected | Movies worker | PENDING; Movies import task |
| BE-SPORTS.PROVIDER | 55–56 §5 | Existing API-Football adapter team549 next=1; daily/manual sync, bounded retry, reschedule binding idempotently | Sports worker | PENDING; W2 credentials |
| BE-SPORTS.CARD | 55–56 §5, 73 | Exactly nearest future fixture, beyond14days/48hours visible, priority inside48h, logos/calendar link, no model call | Sports worker | PENDING; PROVIDER |
| BE-BANKING.QUALIFY | 56 §6.1, 76 | Record every Plaid/TARGOBANK Production gate; do not silently switch provider | Primary | PENDING; production credentials/business access external |
| BE-BANKING.STORE | 57–58 §6.3–4 | Additive connection/account/balance/sync concepts, Vault references, retain existing FinanceTransaction | Banking worker | PENDING; W2/qualification report |
| BE-BANKING.SYNC | 57–58 §6.3–4, 73–74 | Cursor pagination atomic commit/restart, modified/removed/pending transitions, verified idempotent webhook jobs | Banking worker | PENDING; STORE |
| BE-BANKING.UI | 56–58 §6.2–4 | Sandbox/qualified Production connect/sync/reconnect/disconnect with explicit history choice; preserve CSV until production gate | Banking worker | PENDING; provider/configuration |
| BE-BANKING.TOOLS | 58 §6.5 | Permission-limited local Finance reads, no tokens/raw payload/account IDs | Banking/runtime workers | PENDING; normalized data |
| BE-FOOD | 58–59 §7, 74 | Local/user/OFF/USDA precedence, sourced units/nutrients/corrections/provenance/cache; generic food API | Food worker | PENDING; W2 for USDA |
| BE-MEDIA.PROVIDER | 59–60 §8.1–3 | Existing media adapter, named Flare low policy; licensed wger first; generated exercise art decorative | Media worker | PENDING; provider availability/configuration |
| BE-MEDIA.CACHE | 60 §8.4, 74 | Versioned fixed templates, semantic fingerprint/unique claim/entity links/background ready events/cache reuse | Media worker | PENDING; W2/food IDs |
| BE-MEDIA.BENCHMARK | 59–60 §8.2, 76 | 10 food +10 exercise prompts; first acceptance/retry/latency/actual cost; food≥90%; comparison only if needed | Primary + media worker | PENDING; paid/live provider evidence required |
| BE-EVENTS | 60–61 §9, 65 §10.9 | Existing outbox/world revision/SSE, typed IDs and bounded cross-domain services; no copied facts | Primary | PENDING; integrate per milestone |
| BE-MOVIES.IMPORT | 61–63 §10.1–4 | Extend existing baseline import: bounded ZIP/CSV, read-only preview, explicit ambiguity, provenance/idempotency/local corrections | Movies backend worker | PENDING; W2 |
| BE-MOVIES.CATALOG | 63–65 §10.5/7 | Existing deterministic TMDB adapter detail/config-cache/minimal DTOs, allowed poster URLs/2:3 placeholders/attribution | Movies backend worker | PENDING; TMDB credential |
| BE-MOVIES.TOOLS | 64 §10.6 | Typed search/watchlist/recommendations/add/remove/watch/rate, atomic from-catalog, canonical permission/audit paths | Movies/runtime worker | PENDING; catalog |
| BE-MOVIES.METRICS | 65 §10.9–10 | Operational request/cache/errors, zero AI spend, safe outage/local history retention and SSE events | Movies worker | PENDING; import/catalog |
| BE-RUNTIME.TRIGGERS | 52–53 §2, 75 | Canonical TIME/USER/EVENT runs, CHECK/ACT/DECIDE_TYPED/REASON/WAIT/REPORT lanes | Runtime worker | PENDING; inspect existing runtime, no second scheduler |
| BE-RUNTIME.LEDGER | 52–53 §2.3, 75 | Shared recurrence/window satisfaction, unique transactional lease/claim, skip already satisfied across manual/scheduled | Runtime worker | PENDING; TRIGGERS |
| BE-RUNTIME.JEV | 53 §2.4, 75 | Schema-bound minimal decisions within triggered run, confidence/fallback/review, no clocks/provider authority | Runtime worker | PENDING; TRIGGERS |
| BE-COST | 53 §3, 75 | Every AI/image/embedding/vision call attribution; pricing version, actual vs estimated/cached, aggregates | Runtime/cost worker | PENDING; W8 |
| BE-DEVELOPER.STATUS | 65–67 §11.1–4, 75 | Ten derived states/precedence; valid lease+fresh heartbeat; SSE/refetch, versioned audited control APIs | Runtime worker | PENDING; W8 |
| BE-DEVELOPER.UI | 65–67 §11.1–4 | Canonical identity/detail/schedules/runs/responsibilities/costs/skills projection; final visual design stays gated | Developer worker | PENDING; W8; visual BLOCKED_DECISION |
| BE-BRAIN | 68–69 §11.5–6, 75 | Bounded shared-memory graph/typed relations, governed mutations/provenance/tenant/version, list fallback | Brain worker | PENDING; W8, dependency/license check |
| BE-WORKFLOWS | 69–71 §11.7–11, 75–76 | Immutable versions, exactly1 trigger/DAG/typed protocols/readonly simulation; existing runtime executes | Workflow worker | PENDING; W8, no arbitrary code/second runtime |
| W10 | 4, 19–20, 41, 73–78 | Milestone security/migrations/regressions/visual/a11y/end-to-end evidence; preserve data/routes | Primary + independent read-only reviewer | PENDING; at each boundary |

## Explicit decisions and deferred design

| Gate | Source | Status / required user decision |
| --- | --- | --- |
| FIT-BE-01 | 3–4, 35, 40, 48, 50, 87–88 | BLOCKED_DECISION: anatomy taxonomy, source, secondary/weighted mapping/corrections |
| FIT-BE-02 | 4, 34–35, 48, 50 | BLOCKED_DECISION: goal normalization/forecast samples/horizon/confidence |
| FIT-BE-03 | 4, 33/35, 50 | BLOCKED_DECISION: new measurements/correction/history policy |
| FIN-BE-01 | 4, 37–38, 49–50 | BLOCKED_DECISION: liabilities/installments, source/accounting/double-count policy |
| FIN-BE-02 | 4, 38, 49–50 | BLOCKED_DECISION: history/backfill/forecast definitions; frozen bank snapshots remain permitted |
| MOV-BE-01 | 4, 39–41, 49–50 | BLOCKED_DECISION: pinned ordered favorites/named lists/limits/privacy |
| MOV-BE-02 | 4, 39–41, 49–50 | BLOCKED_DECISION: rating/activity counting, rewatches/buckets/stat aggregates |
| Home / Learning / Life parent / Notebook / Developer final visual | 82–88 | Deferred/open design. Preserve working existing surfaces; no new freeze inferred |
| Plaid Production | 56, 76 | BLOCKED_EXTERNAL until all qualification gates independently evidenced |

The Part Four BE-FIT/BE-FIN/BE-MOV spellings refer to the same tickets above, not
additional approvals. Frozen UI appearance does not authorize gated new schemas.

## Related tasks and active ownership

| Task | Parent | Owner / write scope | Dependencies | Status / evidence / remaining |
| --- | --- | --- | --- | --- |
| T0-SOURCE | W0 | fast_worker `checkpoint_setup_docs`: source/ + ASSET_MANIFEST.md only | None | VERIFIED byte preservation: 1 PDF +25 images; zero hash mismatches. Primary reviewed manifest |
| T0-RECONCILE | W0 | Primary: ledger/handoff/current implementation map | T0-SOURCE | VERIFIED intake: full contract read; six local baseline screenshots;13 provider+46 navigation tests passed |
| T1-VAULT | BE-INTEGRATIONS.STORE/API | deep_worker `integration_vault`: backend/app/integrations/, provider_credentials.py, routes_integrations.py, migration0031, test_integration_credentials.py | W0 | IMPLEMENTED;31new+17legacy tests pass; primary registered router/config/model; hostedVault not run |
| T1-SETTINGS | BE-INTEGRATIONS.UI | fast_worker `checkpoint_setup_docs`: new view/client/tests | Agreed DTOs/T1-VAULT | Initial implementation complete; primary review corrected endpoint and draft isolation; five focused tests passed |
| T1-SETTINGS-COMPLETE | BE-INTEGRATIONS.UI/LETTERBOXD | standard worker `settings_completion`: integration view/client/tests +shared LetterboxdImportPanel +MoviesPage/movies.test.tsx | T1-SETTINGS/backend DTO | IMPLEMENTED;15focused tests/typecheck pass; explicit metadata clears, import preview survives tab switches, Settings importer independent of Vault. Full ZIP/history remainsM6 |
| T1-INTEGRATE | W10 | Primary: router/client configuration/migration ordering/checks | T1-VAULT/T1-SETTINGS | PENDING |
| T1-REVIEW | W10 | Separate read-only reviewer | Integrated diff + targeted evidence | PENDING; corrections assigned to owning worker |

## Current implementation map (inspection evidence, not full acceptance)

- App.tsx routes existing /self/assistant, Calendar, Kitchen, Finance, Movies,
  Settings, Personal Model and feature previews. No /chat, /settings/integrations
  or /developer routes yet. Existing aliases must remain.
- navigationModel.ts still uses Self; AppShell mounts the global assistant bottom
  bar; Calendar baseline shows flyout controls, slogan and seeded lower forms.
- Existing provider store supports openai/gemini/jev via private Vault functions.
  SQLite fails closed. Reuse this boundary; do not create a parallel encryption
  store. General integration status/configuration/scoped metadata is missing.
- Existing daily standing-calendar worker/reconciliation is canonical; provider
  currently fetches a date window. Fixture projection contains a48h restriction.
- Kitchen writes MealHistory but no dedicated browsable MealHistory GET found in
  routes_kitchen.py. Existing cooking workspace must be preserved.
- Existing Movies import preview/confirm, catalog/provider/watchlist/history are
  substantial. No multipart import/config-cache/from-catalog route found in audit.
- Existing media generation uses entity cache and binary dedup; semantic template
  claim/entity-link/background semantics require extension.
- Existing AIActionAudit and DecisionProviderUsage plus memory job machinery are
  relevant to W8. No general agent lane/job/step/workflow/banking/food catalog
  models found by named-concept inspection. Reconcile equivalents before adding.

## Per-task model routing (user refinement, 2026-10-08)

| Task | Actual model / effort | Selection reason |
| --- | --- | --- |
| T0-SOURCE | gpt-5.6-luna /low | Mechanical copy/hash/manifest |
| T1-VAULT | gpt-6.1-sol /high | Consequential Vault/RLS/scoped isolation and additive SQL security |
| T1-SETTINGS | gpt-5.6-luna /low | Initial tightly defined view scaffold; primary review found feature-level gaps |
| T1-SETTINGS-COMPLETE | gpt-5.6-sol /medium | Normal feature refactor, canonical importer/state preservation and endpoint tests |
| T1-REVIEW | Symphony gpt-6.1-sol /high (planned) | Independent bounded security review; no implementation or duplicate worker audit |

Project defaults now use the standard tier; AGENTS.md and standard_worker.toml
define three task-sensitive tiers. Keep two concurrent workers, disjoint scopes,
and escalate for observed difficulty. This chat's middle-tier spawn is explicit;
the new default/custom role still needs verification in Symphony's actual runtime.

## Conflict and verification register

| ID | Finding | Resolution / remaining |
| --- | --- | --- |
| C0-UI | Prior Phengos roadmap gates remain; contract explicitly preserves them | Approved frozen targets may be implemented; stop at visual feedback boundary. No advance into unapproved UI areas |
| C0-WATCHLIST | Contract route DELETE names movie_id, current route names item_id | Preserve existing caller behavior; add adaptation only after scoped Movies audit |
| C0-SOURCE | Historical DOCX/package-update instructions appear in preserved PDF | We are implementing code, not editing/rebuilding source design masters. Preserve source unchanged |
| C0-RUNTIME | Symphony dashboard unavailable at intake; this chat has bounded workers | Primary coordinates current workers directly; no claim of live Symphony execution yet |
| C0-PROVIDER | Live provider keys/qualification/paid benchmark not established | Tests inject transport/store; no production activation or paid benchmark claim |
| C1-HOSTED | Current application DB dialect is PostgreSQL; migration0031 has not been applied to the hosted DB | Keep hosted data intact; source/mocked security tests pass. Hosted Vault execution remains an external verification gate |

## Checkpoint evidence

- Source/plan checkpoint `3204ac9` pushed on `codex/unified-contract`.
- Private overall tracker: <https://github.com/Fivina/life-os/issues/1> (not ready;
  do not duplicate the current implementation).
- Symphony restarted; state API HTTP200 with0active runs before review dispatch.
- Local baseline screenshots (ignored): `artifacts/unified-contract/baseline/`
  Calendar, Kitchen, Settings, Fitness, Finance, Movies. Scope is displayed layout,
  including observed loading states; not proof all live domain data loaded.
- PDF page54 rendered and visually inspected to crosscheck credential contract.
- Backend worker31new credential cases +17legacy provider/capability cases passed.
- Initial frontend5tests passed; standard completion15tests +typecheck passed.
- Gitleaks found one exact synthetic replacement test string; added only a
  rule/path/value-scoped exception, then rerun before publishing the checkpoint.

## Usage and resume policy

Direct user instruction: manage tokens carefully; AFK; if an available account
window falls below5% remaining, checkpoint and create a thread scheduled task for
16:55 Europe/Berlin with prompt `keep going`. Threshold uses100-usedPercent and
the lowest available relevant window. Check at work chunk boundaries, not every
command. Initial09:59UTC check:96% five-hour/84% weekly; later check89%/83%.
No threshold-triggered task created yet. Verify current time before scheduling;
if16:55 has passed, use the next16:55 and record the date. An automation must read
HANDOFF.md/this ledger, respect gates and check limits; it cannot create allowance.

Do not use reset credits, rotate accounts, spawn redundant audits or call costly
product providers automatically. Primary updates progress after coherent chunks.
Most recent limit check:73% remaining five-hour /80% weekly; trigger not met.
