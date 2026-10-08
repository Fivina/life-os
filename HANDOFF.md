# Life OS development handoff

Last checkpoint: 2026-10-08 (Europe/Berlin).
Checkpoint owner: primary Codex session, development orchestrator and final reviewer.

## Where we stopped

The user supplied the 88-page unified implementation contract and 25 reference
images on 2026-10-08 and authorized AFK development orchestration with careful token
usage. No Figma or other external design tool is required. Source files are preserved
under `docs/implementation/unified-contract/source/`, with byte hashes verified.
The requirement ledger is `docs/implementation/unified-contract/LEDGER.md`.

Current chunk: integration credential foundation (backend milestone 1). Primary
read the full text, inspected the relevant implementation and captured baseline
Calendar/Kitchen/Settings screenshots in `artifacts/unified-contract/baseline/`
(local, ignored by Git). Deep worker `integration_vault` owns scoped backend Vault,
integration routes/model/migration/tests; fast worker `checkpoint_setup_docs` owns
the new Settings integration view/client/tests. Primary owns registration and
integration. No substantial implementation has passed independent review yet.

Next action: align the worker DTOs, integrate the credential foundation, run focused
security/frontend checks and independent review; route corrections. Follow the
ledger for remaining work and explicit decision gates. No new bank production,
paid media benchmark, unapproved backend ticket or open visual design is activated.

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
| Last published baseline before this handoff | `875d5da` — Record private repository and tracker verification |
| Last completed handoff rules chunk | `f857f15`, pushed to master; new source intake/progress is on `codex/unified-contract` |
| Frontend | <http://localhost:5173>; HTTP 200 verified on 2026-10-08 |
| Backend | <http://localhost:8000/readiness>; HTTP 200, ready, database reachable, auth configured on 2026-10-08 |
| Symphony | Installed and GitHub queue previously verified; <http://localhost:8787/api/v1/state> unreachable at this checkpoint. Startup cause not investigated. No new implementation issue dispatched. |
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
The real implementation, independent review and correction cycle remains untested.

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
| Unified contract implementation | Primary orchestrator; `integration_vault` backend; fast `checkpoint_setup_docs` Settings UI | Complete text read and source hash preservation; requirement/dependency/decision ledger; baseline source/UI inspection | Credential foundation in progress; see ledger for all later work and review gates |
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
  `gpt-6.1-sol`/high for `deep_worker`; see `.codex/agents/`. The real Symphony pilot
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

## Checkpoint log

| Date | Contributor | Result | Evidence / next action |
| --- | --- | --- | --- |
| 2026-10-08 | Primary | Local app restarted and readiness verified | Frontend/backend HTTP 200; next: user testing |
| 2026-10-08 | Primary + fast worker `checkpoint_setup_docs` | Handoff policy/documentation complete; primary reviewed worker diff, existing model roles and consistency across all four files; no product implementation | `git diff --check` passed; app readiness verified; Symphony unavailable. Checkpoint commit: find `Add durable development handoff and worker checkpoints` in Git. Next: receive source document and create requirement ledger. |
| 2026-10-08 | Primary + fast `checkpoint_setup_docs` | Contract intake, unchanged PDF +25 images preserved/hash-verified, complete text read, requirement/decision ledger created; backend/UI workers dispatched | Branch `codex/unified-contract`. Next: milestone1 integration and independent review. Usage89% five-hour/83% weekly at last check; below5% resume-task condition not met. |

## AFK usage instruction

Check account limits at chunk boundaries. If the minimum available relevant usage
window has less than5% remaining, save a safe checkpoint and create a thread
scheduled task at16:55 Europe/Berlin prompting `keep going`. Verify current time;
use the next16:55 if today's time has passed. No scheduled task created yet.
Do not consume reset credits or switch accounts automatically. A resume must read
this handoff/ledger, check current limits and respect contract decision gates.
