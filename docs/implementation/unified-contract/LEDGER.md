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
| BE-SPORTS.PROVIDER | 55–56 §5 | Existing API-Football adapter team549 next=1; daily/manual sync, bounded retry, reschedule binding idempotently | standard sports worker +primary schema | IMPLEMENTED;35 targeted tests; Vault hookup/live verification and independent review pending |
| BE-SPORTS.CARD | 55–56 §5, 73 | Exactly nearest future fixture, beyond14days/48hours visible, priority inside48h, logos/calendar link, no model call | Primary | PARTIAL: nearest future/priority/logos/competition/TBD/pointer implemented; specific Calendar entry deep link remains open |
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
| T1-INTEGRATE | W10 | Primary: router/client configuration/migration ordering/checks | T1-VAULT/T1-SETTINGS | IMPLEMENTED `f3ef64d`; isolated200 list/deny installation/Vault fail-closed/UI checks;48 navigation tests after nested-route correction; hostedVault not applied |
| T1-REVIEW | W10 | Separate Symphony gpt-6.1-sol/high reviewer, read-only | Integrated diff + targeted evidence | Report saved on issue2:48 backend tests rerun; no extra credential defect found; two P2 importer findings. HostedVault gate remains open |
| T1-CORRECT | BE-INTEGRATIONS.LETTERBOXD | standard `settings_completion`: shared panel/Movies +two focused tests; primary reviewed | T1-REVIEW | IMPLEMENTED: default AUTO omits override, displays actual preview destination; Movies links Settings importer;18 frontend tests/typecheck passed |
| T2-SPORTS-PROVIDER | BE-SPORTS.PROVIDER | standard worker `sports_provider`: standing_calendar/providers.py, service.py, test_next_fixture_sync.py | Existing canonical worker; credential hookup primary-owned | IMPLEMENTED:35 tests pass; next=1/daily/transient max3 attempts; known-empty/failure-preserved pointer; no live calls. Generic Vault hookup pending |
| T2-SPORTS-SCHEMA | BE-SPORTS.PROVIDER | Primary: models.py, schemas.py, migration0032 +migration test | Existing0031 ordering | IMPLEMENTED: allow1/14 cadence, safe typed pointer fields, permit missing time only scheduledTBD; isolated SQLite migration roundtrip passed. Not applied to hosted DB |
| T2-SPORTS-CARD | BE-SPORTS.CARD | Primary: existing card projection/query/type +targeted tests | Existing fixture bindings/pointer | PARTIAL: one nearest future match beyond48h, near-term priority, authoritative-empty hide, selectedTBD/competition;71 focused frontend tests/typecheck passed. Specific Calendar entry deep link and independent review pending |

## Current implementation map (inspection evidence, not full acceptance)

Current continuation tasks: T2-VAULT primary (existing IntegrationSecretStore plus
fixed-provider backend-only installation read; no writes or tenant-admin bypass),
T2-CALENDAR-LINK standard `sports_calendar_link` gpt-5.6-sol/medium (bounded existing
Calendar/frontend read path). Follow with independent Symphony review of integrated
published commit. Source pages55–56, existing namespace/functions/runtime retained.
One-time thread wake-up `continue-life-os-development` created for2026-10-08 16:35
Europe/Berlin, exact prompt `keep doing`; latest user instruction replaces16:55 trigger.

Continuation checkpoint: T2-VAULT IMPLEMENTED with explicit
`FIXTURE_CREDENTIAL_SCOPE=installation|tenant` (default installation), fixed-provider
backend-only installation read function in migration0033; tenant management rights
unchanged. Runtime rereads selected Vault source and never falls back to environment
key after removal. SQLite/missing function fails closed. Savepoint rolls back partial
Calendar writes and sanitizes unexpected errors. Provider requests reject redirects/
environment proxies and cap response256KiB. Low-level env-key constructor remains
for legacy compatibility/tests, but canonical sync uses Vault only.
T2-CALENDAR-LINK IMPLEMENTED by standard `sports_calendar_link`: encoded commitment
query, authorized canonical read beyond projection, actual selected details, missing/
forbidden/error/TBD states. Primary corrected nullable CommitmentRead for already
valid unconfirmed fixture records; cross-tenant read isolation tested.
Checks:96 backend tests across integration/provider/sports/migration boundary;
37 frontend tests across Calendar/cards/Settings/Movies; typecheck passed.
Independent sports review and browser current-runtime check pending. Shared provider
fetch once across installation users is not yet accepted; existing worker still
reconciles each user's rule. Hosted migrations0031–0033 remain unapplied.

- App.tsx routes existing /self/assistant, Calendar, Kitchen, Finance, Movies,
  Settings, Personal Model and feature previews. New /settings/integrations and
  /settings/integrations/:provider added in f3ef64d. No /chat or /developer yet.
  Existing aliases remain.
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
| T1-REVIEW | Symphony gpt-6.1-sol /high (actual model/effort/read-only verified) | Independent bounded security review; no implementation or duplicate worker audit |
| T2-SPORTS-PROVIDER | gpt-5.6-sol /medium | Bounded existing provider/service change; shared credential privilege architecture retained by primary |
| T2-CALENDAR-LINK | gpt-5.6-sol /medium | Canonical frontend link/read and regression tests, existing endpoint |
| T2-REVIEW | Symphony gpt-5.6-sol /medium | Bounded independent sports/security integration review,26 backend tests |
| T2-SHARED-FETCH | standard_worker gpt-5.6-sol /medium | Bounded cache/service/migration implementation under primary architecture |

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
| C0-RUNTIME | Symphony unavailable at intake | Restarted native reviewer workflow; actual read-only model session now confirmed. Unsupported reject approval schema corrected to never; exact E:/.../GH-2 Git safe.directory added. No nested review workers |
| C0-PROVIDER | Live provider keys/qualification/paid benchmark not established | Tests inject transport/store; no production activation or paid benchmark claim |
| C1-HOSTED | Current application DB dialect is PostgreSQL; migration0031 has not been applied to the hosted DB | Keep hosted data intact; source/mocked security tests pass. Hosted Vault execution remains an external verification gate |
| C1-PRIVACY | GitHub403 at clone; subsequent API reported PUBLIC despite requested private repository | Restored PRIVATE, verified REST/GraphQL and fresh clone. User confirmed handling account/repository setting; cause not inferred. Recheck before pushes; Codex sign-in is independent of local gh sign-in |

## Checkpoint evidence

- Source/plan checkpoint `3204ac9` pushed on `codex/unified-contract`.
- Implementation checkpoint `f3ef64d` pushed; bounded independent review:
  <https://github.com/Fivina/life-os/issues/2>, exact commit fixed in brief.
- Corrected implementation/next-match groundwork published as `55ddfc3`; private
  draft PR <https://github.com/Fivina/life-os/pull/3>. Staged Gitleaks scanned38.5KB,
  no leaks. Reverified repository private immediately before publication.
- Private overall tracker: <https://github.com/Fivina/life-os/issues/1> (not ready;
  do not duplicate the current implementation).
- Symphony restarted; state API HTTP200 with0active runs before review dispatch.
- Local baseline screenshots (ignored): `artifacts/unified-contract/baseline/`
  Calendar, Kitchen, Settings, Fitness, Finance, Movies. Scope is displayed layout,
  including observed loading states; not proof all live domain data loaded.
- PDF page54 rendered and visually inspected to crosscheck credential contract.
- Backend worker31new credential cases +17legacy provider/capability cases passed.
- Initial frontend5tests passed; standard completion15tests +typecheck passed.
- Primary isolated preview5174/8001: statusHTTP200 with8providers, Vault saving
  disabled, installation access denied, TMDB detail/notice and Settings navigation
  displayed, Letterboxd importer opens independently. Mobile390x844 has no horizontal
  overflow; all five secret inputs empty/disabled. Screenshots saved locally under
  `artifacts/unified-contract/baseline/integrations-*.jpg`.
- Independent review report saved on issue2; two P2 findings corrected by standard
  worker and primary reviewed the diff. CSV synthetic preview did not create viewing
  history; explicit confirmation created one isolated fixture viewing.
- Sports targeted backend35 tests +daily cadence SQLite migration roundtrip1 test
  passed. Combined frontend milestone check71 tests across4 files; typecheck passed
  after correcting a missing test-fixture type field. No full repository suite run.
- Current original backend8000 and isolated8001 processes predate later sports
  changes. New sports runtime/0032 and hosted Vault0031 are not live-verified.
- Corrected default-watchlist path verified through the browser against isolated
  backend8001: preview destination Watchlist, confirmation one watchlist item,
  viewing history remains one previous synthetic diary entry. No real export used.
- Gitleaks found one exact synthetic replacement test string; added only a
  rule/path/value-scoped exception, then rerun before publishing the checkpoint.

## Usage and resume policy

Latest direct instruction supersedes conditional16:55: work until account allowance
is exhausted; one-time heartbeat `continue-life-os-development` for2026-10-08
16:35 Europe/Berlin, exact prompt `keep doing`, created/verified. Save coherent
checkpoints before interruption. On resume read HANDOFF/ledger and reconcile Git.
Check usage at chunk boundaries; scheduling creates no allowance. Do not consume
reset credits, switch accounts, duplicate audits or call paid product providers.

## Sports review and local runtime checkpoint

Independent Symphony review: issue4,0d1a12b vsf3ef64d, standard gpt-5.6-sol/medium,
read-only.26 focused backend tests passed, no scoped backend defect. Two P2 findings:
card cap could omit fixture and emitted wide size; same-record refresh could reset
Calendar navigation. Primary corrected reserved compact card and once-per-ID initial
positioning;21 focused frontend tests and typecheck passed, publication pending.
These corrections have not received a second independent review.
Runtime5174/8001 disposable SQLite: one30day future match shown, actual Calendar
entry/day opens, missing entry unavailable without unrelated selection, TBD actual
record shows date/time unconfirmed after reload. Authorized TBD GET200. Screenshots
ignored under artifacts/unified-contract/baseline/sports-calendar-*.jpg. No live
provider/hosted DB calls; hosted migrations0031–0033 and shared cache still open.

### T2-SHARED-FETCH plan (2026-10-08, primary architecture)

Source p54: installation API-Football credentials should fetch shared public data
once. Extend existing standing_calendar service; no second sports runtime/scheduler.
Standard worker sports_shared_fetch, gpt-5.6-sol/medium, owns only new cache model
registration, migration0034, service fetch-cache integration and focused tests.
Primary owns integration/review. Add one backend-only normalized public fixture
snapshot cache keyed provider/team/base URL, expires after one daily interval.
Only installation scope shares it; tenant mode stays isolated. Read selected Vault
key before every sync (including cache hits); removal must fail closed. Scheduled
worker reuses a fresh snapshot; manual sync forces a provider refresh and updates
that snapshot. Cache successful empty results too. PostgreSQL transaction advisory
lock serializes successful cache miss/refresh without committing inside services.
Keep reconciliation in existing savepoint, do not cache secrets/raw payloads/errors.
No hosted migrations/provider calls. Tests: two users share one scheduled fetch,
manual refresh updates cache, tenant bypass, empty reuse, expiry, removal, rollback.
Implementation/review pending; PostgreSQL concurrency and live Vault remain external
verification gates. Do not mark parent sports VERIFIED until these gaps are closed.
