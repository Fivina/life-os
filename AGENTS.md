# Life OS — Codex Development Rules

## Checkpoints and Resuming Work

Read root `HANDOFF.md` when starting or resuming project work. Verify its branch,
commit and working-tree notes against Git before relying on them. It is the resume
entry point; the live code and referenced source requirements remain authoritative.

The primary session owns orchestration, integration and final review. Use bounded
workers according to the cost policy below; do not default every task to a high
capability model. Require a separate read-only reviewer for substantial implementation.

When an implementation document arrives, preserve an accessible source copy and
assign stable requirement IDs with page/section references. Derive related subtasks
and dependencies; record each requirement's owner, status, verification evidence
and remaining work in the handoff or a linked per-brief task ledger. Distinguish
implemented work from reviewed, verified and user-accepted work. Do not claim a
completion percentage without a defined denominator and counting method.

Update the handoff at completed work chunks, review/correction outcomes, blockers,
milestone boundaries and before a planned chat/account handoff. Do not update it
after every command or minor edit. Before lengthy implementation, persist the plan
and ownership so an interrupted run has a recovery point. Workers report results;
the primary session consolidates checkpoints to avoid concurrent handoff edits.
Record branch/workspace, commits or uncommitted files, who did what, checks actually
run, open review findings, blockers and the exact next action. Keep secrets out.
Unexpected chat/process loss may leave work since the last checkpoint unrecorded;
on resume, reconcile the ledger with Git and actual files before continuing.

## Delegation and Cost Policy

Default behavior: perform work in the primary Codex session. Do not create subagents merely because they are available.

For a large or multi-part request, first create a detailed internal task breakdown. Keep architectural decisions, sequencing, integration, and final verification in the primary session. Delegate only clearly bounded tasks that are independent enough to execute safely and return a concrete result.

Use up to two subagents concurrently only when their tasks and write scopes are independent. Review their results in the primary session. Do not manufacture tasks merely to use a subagent.

### fast_worker

Delegate only for narrow, mechanically defined, independent, low-risk work that does not require architectural judgment, such as locating a known implementation, inspecting limited files, straightforward mechanical edits, or documentation updates after behavior is known.

### deep_worker

Delegate only for genuine architectural ambiguity, important cross-module changes, unresolved integration problems, or difficult regressions. Do not use it for routine implementation.

### standard_worker and task-sensitive model routing

Use `standard_worker` for bounded feature implementation, provider adapters,
UI refactors and meaningful tests once architecture and acceptance criteria are
known. Do not force ordinary engineering into either the cheapest mechanical role
or the deepest architecture role. The user explicitly requested multiple models
matched to their tasks on 2026-10-08.

| Task | Starting role / model / effort |
| --- | --- |
| Mechanical source/file handling or exact edits | `fast_worker`, `gpt-5.6-luna`, low |
| Routine feature implementation, adapters, UI and regression tests | `standard_worker`, `gpt-5.6-sol`, medium |
| Difficult architecture/security/integration/regressions | `deep_worker`, `gpt-6.1-sol`, high |
| Independent review | Separate read-only context; choose effort for risk, ordinarily Sol medium, higher for consequential security |

Record role/model/effort and a short selection reason in the task ledger. Do not
inherit the primary's expensive model accidentally: project `[agents]` defaults
select the standard tier. When a client does not list a custom role, use its worker
role with an explicit equivalent model/effort. If a model is unavailable, record
the compatible substitution. Escalate a bounded task for observed difficulty or
failed corrections; do not run competing implementations. Primary retains
architecture, sequencing, integration and final review. Maximum two concurrent
workers and disjoint ownership remain in force.

## Hard Cost Rules

- Maximum two subagents at a time, with disjoint write scopes.
- Never spawn multiple agents for the same problem or run competing implementations.
- Never delegate work the primary agent can perform directly.
- Do not repeatedly re-audit the repository or run the full test suite after every small edit.
- Use targeted tests for changed behavior; run broader verification at milestone or acceptance boundaries.
- Stop after the requested milestone is complete.

## No Assumption Rule

The live repository is implementation truth. Before changing a subsystem, inspect the relevant implementation, preserve newer working behavior, and do not invent missing architecture or silently fill unspecified requirements. If the implementation conflicts with the requested contract, preserve the working system and report the conflict. Implement only the requested scope.

## Phengos Redesign Continuity

Read `docs/PHENGOS_ROADMAP.md` when continuing the UI redesign. It records the four
user-approved milestones and their feedback gates. A request for "usable navigation"
means milestone 2, not a new 3D scene. Preserve the existing features inventoried in
`docs/PHENGOS_FEATURE_INVENTORY.md`; do not delete routed workflows to simplify visuals.
