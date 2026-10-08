# Life OS development handoff

Last checkpoint: 2026-10-08 (Europe/Berlin).
Checkpoint owner: primary Codex session, development orchestrator and final reviewer.

## Where we stopped

The user authorized AFK development from the preserved 88-page unified contract,
with task-sensitive workers, primary integration/final review, and durable checkpoints.
Source and stable requirement tracking: `docs/implementation/unified-contract/LEDGER.md`.

Branch `codex/unified-contract`, frontend correction head `331e917` (verify Git on resume),
private draft PR <https://github.com/Fivina/life-os/pull/3>. Foundation `f3ef64d`
and import corrections/next-match groundwork `55ddfc3` are published. Foundation
review issue2 completed; its two importer findings were corrected and browser-tested.

Current sports chunk: Vault-only runtime lookup (installation default or tenant),
fixed-provider backend getter/migration0033, bounded no-redirect transport, daily
next=1 synchronization and authorized Calendar deep links including TBD records.
Primary backend/integration; standard workers sports_provider/sports_calendar_link
implemented their bounded service/frontend scopes.96 backend and37 frontend tests
plus typecheck passed at0d1a12b; hosted migrations0031–0033 remain unapplied.

Independent Symphony review issue4 completed against0d1a12b, gpt-5.6-sol/medium,
read-only separate checkout.26 focused backend tests passed; no scoped backend
finding. Two P2 frontend findings: crowded card cap hides match/not compact;
same-record refresh resets Calendar navigation. Primary has local corrections and
regressions published as331e917 (21 frontend tests and typecheck pass). These corrections are not yet independently re-reviewed.

Runtime evidence on disposable SQLite preview5174/8001: dashboard shows one match
30days ahead; clicking opens that canonical Calendar record on its actual day;
missing record shows explicit unavailable state; TBD entry shows date/time unconfirmed.
Screenshots: ignored `artifacts/unified-contract/baseline/sports-calendar-*.jpg`.
One initial TBD browser request failed; explicit reload succeeded, authenticated
HTTP GET returned200. No real credentials, user database or live provider calls used.

T2-SHARED-FETCH IMPLEMENTED: standard worker sports_shared_fetch,
gpt-5.6-sol/medium, added backend-only normalized snapshot model/migration0034,
installation daily reuse, manual forced refresh, tenant bypass, Vault removal
fail-closed before cache hits, PostgreSQL transaction advisory lock and reload,
savepoint rollback. Primary inspected the diff and requested/final-reviewed the
missing-secret and stale-identity-map corrections. Worker reports96 relevant backend
tests passed (including9 new snapshot tests, runtime/sports/integration/release-gate);
git diff check passed. Ruff unavailable. No live provider or hosted migration.
This cache checkpoint is titled `Share daily installation fixture snapshots`;
verify its exact commit/publication against Git. No worker remains running.

Next action: bounded independent read-only review of the cache checkpoint against
331e917, focusing migration0034 grants/RLS, lock/cache race behavior, Vault removal,
tenant bypass/manual refresh/rollback. Do not enqueue a full contract audit. Cache
is implemented/tested but not independently reviewed or accepted. Hosted migrations
0031–0034 remain unapplied; actual PostgreSQL concurrency/Vault execution is still
unverified. Original8000/5173 are stopped; preview8001/5174 remains up but backend
process predates cache code/schema and must be restarted/recreated before cache
runtime checks. Preserve synthetic-only database isolation.

Current account last reported4% remaining. Resume the next unmet approved requirement
after this review and correction cycle; preserve feedback/decision gates. Do not
activate real banks/paid benchmarks or the seven blocked backend tickets.

User explicitly requested work until the usage limit and a one-time16:35 Berlin
continuation today2026-10-08. Heartbeat `continue-life-os-development` is ACTIVE,
exact prompt `keep doing`, verified through automation tool. This supersedes the
previous conditional16:55 request. Resume by reading this file/ledger and reconciling
Git; do not rotate accounts or use reset credits automatically.

## Resume checklist

1. Read this file and `AGENTS.md`. Check `git status`, current branch, latest commits
   and remote before changing anything; do not discard unfinished work.
2. Read the source brief and linked task ledger when present. Reconcile statuses
   with actual files, review findings and the GitHub issue workpad.
3. Recheck runtime/auth only for the work that needs it. A past successful check
   does not establish that a service or credential is still available.
4. Continue the next unmet requirement in dependency order. Respect the existing
   feedback gates and preserve working routes. Do not restart completed work.

## Repository and current runtime

| Item | Checkpoint state |
| --- | --- |
| Primary workspace | `D:/Life OS` |
| Repository | Private: <https://github.com/Fivina/life-os> |
| Branch at checkpoint | `codex/unified-contract`; source intake and implementation work branch |
| Independently reviewed foundation | `f3ef64d` — integration credential foundation and tiered worker routing; later correction/next-match checkpoint is identified above |
| Last completed handoff rules chunk | `f857f15`, pushed to master; new source intake/progress is on `codex/unified-contract` |
| Frontend | Original5173 process stopped at account switch; isolated5174 running. Check ports before restart. |
| Backend | Original8000 process stopped at account switch; isolated8001 running disposable SQLite. Hosted DB unchanged. |
| Symphony | Reviewer daemon8787; issue4 report saved, ready label removed. Standard model/read-only review completed. Verify live state before dispatch. |
| Isolated verification app | <http://localhost:5174/settings/integrations> → SQLite backend8001; current source, no hosted migration or real credentials |
| Source of setup details | `docs/SYMPHONY_SETUP.md` and `scripts/start-symphony.ps1` |

Restart application from two PowerShell terminals if required:

```powershell
# Terminal 1: D:/Life OS
pnpm web:dev --host 127.0.0.1

# Terminal 2: D:/Life OS/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check ports before starting duplicate services. Start connected Symphony only when
needed, from `D:/Life OS`:

```powershell
.\scripts\start-symphony.ps1 -GitHub -Doctor
.\scripts\start-symphony.ps1 -GitHub
```

Keep the service terminal open. Attaching a document to a chat does not automatically
enqueue it; its accessible contents must be represented in a private issue/source.
The independent review/correction cycle is in progress; implementation workers
ran in this chat and the separate reviewer runs through Symphony.

## What is done, who did it, and what remains

Historical ownership below is limited to available records; no earlier individual
subagent attribution is inferred.

| Workstream | Owner / contributor | Done and evidence | Remaining |
| --- | --- | --- | --- |
| Private repository and source publication | Earlier primary Codex session | Source snapshot `8b974ad`; private GitHub repo and queue setup recorded in `875d5da` | Preserve privacy and exclude credentials/runtime data from future commits |
| Symphony development orchestration | Earlier primary Codex session | Native Windows build, GitHub adapter read, labels and workflow; `c9c5708`, setup verification in `docs/SYMPHONY_SETUP.md` | Restart/check service when dispatching; validate a bounded real brief end to end |
| Local application restart | Current primary Codex session | Frontend/backend checks above; no product code changed | User testing and document-driven changes |
| Durable handoff and checkpoint rules | Current primary Codex session | Root handoff, repository resume policy and workflow checkpoint instructions | Keep requirement ledger current at meaningful checkpoints |
| Setup documentation continuity | Fast worker `checkpoint_setup_docs`; primary reviewed/integrated | Updated setup guide with checkpoint/ledger rules and corrected historical runtime wording; diff reviewed | No open findings for this documentation chunk |
| Unified contract implementation | Primary orchestrator; deep `integration_vault` backend; fast `checkpoint_setup_docs` UI scaffold; standard `settings_completion` UI completion | Source/ledger, Vault/routes/migration, Settings and shared importer committed;31+17 backend and15 frontend checks pass | Independent review and hostedVault verification pending; see ledger for later work |
| Existing Phengos product work | Prior contributors; see domain docs | Existing implementation retained; `docs/PHENGOS_ROADMAP.md` records status and feedback gates | Visual acceptance remains open in recorded roadmap; new document may require explicit scope reconciliation |

For UI work read `docs/PHENGOS_ROADMAP.md` and
`docs/PHENGOS_FEATURE_INVENTORY.md`. Old spatial/art checkpoints are historical and
must not override the newer Phengos direction. This handoff does not certify all
existing product behavior or close any user acceptance gate.

## Requirement and related-task ledger

Source received and preserved; detailed ledger:
`docs/implementation/unified-contract/LEDGER.md`. It maps source pages and stable
requirements to related tasks, owners, status, evidence and open decisions. Keep
that ledger as the requirement-status source; this file is the concise checkpoint.

Required ledger fields:

| Field | Meaning |
| --- | --- |
| Requirement ID and source | Stable ID, document version/path and exact page/section |
| Desired result / acceptance criteria | What must work and how completion is assessed |
| Related subtasks and dependencies | Coherent task IDs mapped to the requirement; prerequisite IDs |
| Owner and write scope | Lead/worker identity, branch/workspace, bounded files/modules |
| Status | Pending, in progress, implemented, verified or blocked; partial work stays explicit |
| Review / acceptance | Independent review outcome, unresolved findings, user acceptance where required |
| Evidence | Actual checks and results, commits/PR links, limitations |
| Remaining / next action | Concrete unmet work or precise blocker |

A parent requirement is not verified merely because one related task finished.
Count completion only against an explicitly defined requirement denominator.

## Worker and review logic

- Primary owns architecture, sequencing, orchestration, integration and final review.
- Use bounded workers where justified, with at most two concurrently and disjoint
  write scopes. Use fast workers for mechanical tasks; deeper capability only for
  consequential ambiguity, difficult integration or regressions. Follow `AGENTS.md`.
  Existing role files select `gpt-5.6-luna`/low for `fast_worker` and
  `gpt-5.6-sol`/medium for `standard_worker`, `gpt-6.1-sol`/high for `deep_worker`;
  project defaults use the standard tier. See `.codex/agents/`. The Symphony pilot
  must verify these roles are available in its worker runtime.
- A separate read-only reviewer checks substantial implementation against the
  source brief and actual evidence. The primary also reviews integrated behavior
  and routes actionable corrections without requiring repeated user prompts.
- Workers report what changed, what passed, and what remains. The primary updates
  the handoff/ledger to avoid concurrent edits to shared progress records.
- Save the initial plan before lengthy work. Update after completed chunks,
  review/correction outcomes, blockers, milestone gates or a planned handoff/account
  switch. No per-command or per-minor-edit logging is required.
- Push safe Git checkpoints when possible; record incomplete work honestly. On
  sudden chat/process loss, recover any work since the checkpoint from Git/files.

## Account and environment dependencies

GitHub CLI identity is `Fivina` on this Windows user; it is separate from Codex
sign-in. Before changing Codex accounts, stop active workers, save progress, verify
the CLI's intended sign-in and restart Symphony. No automatic account rotation or
mid-run handoff is implemented. Keep credentials out of this file and the ledger.
Local runtimes/assets outside Git are documented in the setup and domain docs;
a clone alone does not reproduce them. No external design plugin is required by
the current agreed workflow.

Repository privacy/access checkpoint: an initial Symphony clone received GitHub403;
API verification subsequently reported PUBLIC, contrary to the requested private
repository. Visibility was restored to PRIVATE and verified by REST/GraphQL before
a fresh clone succeeded. The user confirmed handling the account/repository setting.
No cause is inferred. Recheck privacy before future pushes. GitHub CLI access works
as Fivina independently of the current Codex account; no account switch is required.

## Checkpoint log

| Date | Contributor | Result | Evidence / next action |
| --- | --- | --- | --- |
| 2026-10-08 | Primary | Local app restarted and readiness verified | Frontend/backend HTTP 200; next: user testing |
| 2026-10-08 | Primary + fast worker `checkpoint_setup_docs` | Handoff policy/documentation complete; primary reviewed worker diff, existing model roles and consistency across all four files; no product implementation | `git diff --check` passed; app readiness verified; Symphony unavailable. Checkpoint commit: find `Add durable development handoff and worker checkpoints` in Git. Next: receive source document and create requirement ledger. |
| 2026-10-08 | Primary + fast `checkpoint_setup_docs` | Contract intake, unchanged PDF +25 images preserved/hash-verified, complete text read, requirement/decision ledger created; backend/UI workers dispatched | Branch `codex/unified-contract`. Next: milestone1 integration and independent review. Usage89% five-hour/83% weekly at last check; below5% resume-task condition not met. |
| 2026-10-08 | Primary | User requested less polarized, task-sensitive worker models; added standard tier and explicit default model/effort | Existing two-worker cap retained; model/reason recorded per task. Source/plan pushed as `3204ac9`; private tracker https://github.com/Fivina/life-os/issues/1. Symphony restarted, queue API checked with0runs; review dispatch still pending implementation checkpoint. |
| 2026-10-08 | deep `integration_vault` + standard `settings_completion`; primary review | Credential foundation and shared Settings/Movie CSV importer implemented; targeted checks pass; primary corrections preserved explicit metadata clearing and import draft continuity | Next: publish checkpoint, Symphony independent read-only review and isolated UI/runtime checks; hostedVault pending. Latest usage73% five-hour/80% weekly; no resume task needed yet. |
| 2026-10-08 | Primary + Symphony reviewer | Published `f3ef64d`; issue2 now has a real read-only model session. Fixed native CLI approval policy from unsupported reject object to never; added exact Git safe.directory for GH-2 on E: | Local status/scopes/mobile/detail checks pass;48 navigation tests passed. Review pending. Latest usage40% five-hour/75% weekly remaining; threshold not met. |
| 2026-10-08 | Symphony reviewer; standard `settings_completion`; standard `sports_provider`; primary | Review report saved; two P2 importer findings corrected; next-match provider/cadence/card groundwork implemented with targeted checks |71 frontend +typecheck;35 sports backend +1 migration test. Remaining tasks above and ledger. Latest usage10% five-hour/70% weekly; no threshold-triggered automation yet. User will click Continue; no automatic account rotation. |
| 2026-10-08 | Primary | Published `55ddfc3` and private draft PR3; staged Gitleaks scanned38.5KB, no leaks; reverified private before push | Watchlist browser correction verified in isolated DB. Latest usage6% five-hour/70% weekly; below5% trigger not met. Next: sports review/Vault/deep link and approved backlog |

## AFK usage instruction

Check account limits at chunk boundaries. If the minimum available relevant usage
window has less than5% remaining, save a safe checkpoint and create a thread
scheduled task at16:55 Europe/Berlin prompting `keep going`. Verify current time;
use the next16:55 if today's time has passed. No scheduled task created yet.
Do not consume reset credits or switch accounts automatically. A resume must read
this handoff/ledger, check current limits and respect contract decision gates.
