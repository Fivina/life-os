# Life OS — Codex Development Rules

## Delegation and Cost Policy

Default behavior: perform work in the primary Codex session. Do not create subagents merely because they are available.

For a large or multi-part request, first create a detailed internal task breakdown. Keep architectural decisions, sequencing, integration, and final verification in the primary session. Delegate only clearly bounded tasks that are independent enough to execute safely and return a concrete result.

Use up to two subagents concurrently only when their tasks and write scopes are independent. Review their results in the primary session. Do not manufacture tasks merely to use a subagent.

### fast_worker

Delegate only for narrow, mechanically defined, independent, low-risk work that does not require architectural judgment, such as locating a known implementation, inspecting limited files, straightforward mechanical edits, or documentation updates after behavior is known.

### deep_worker

Delegate only for genuine architectural ambiguity, important cross-module changes, unresolved integration problems, or difficult regressions. Do not use it for routine implementation.

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
