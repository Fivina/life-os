---
tracker:
  kind: github
  provider:
    repo: $SYMPHONY_GITHUB_REPO
    token: $GITHUB_TOKEN
  required_labels: ["symphony:ready", "symphony:review-task"]
  active_states: [open]
  terminal_states: [closed]
polling:
  interval_ms: 30000
workspace:
  root: E:/LifeOS-Tools/symphony-review-workspaces
hooks:
  after_create: |
    git clone "$SYMPHONY_SOURCE_URL" .
    git checkout --detach origin/codex/unified-contract
  timeout_ms: 180000
agent:
  max_concurrent_agents: 1
  max_turns: 5
codex:
  command: '"$SYMPHONY_CODEX_BIN" --config model=gpt-6.1-sol --config model_reasoning_effort=high --config shell_environment_policy.inherit=all app-server'
  approval_policy: never
  thread_sandbox: read-only
  turn_sandbox_policy:
    type: readOnly
server:
  host: 127.0.0.1
  port: 8787
observability:
  dashboard_enabled: false
---

You are an independent read-only Life OS reviewer for GitHub issue
{{ issue.identifier }}: {{ issue.title }}.

Assigned review brief:
{{ issue.description }}

Read the assigned brief and the referenced handoff/ledger, then inspect only the
specified published commit/diff and its relevant source acceptance criteria.
You did not implement this change. Do not modify any source, create commits/PRs,
deploy, apply live migrations, read secrets, call paid providers, or spawn workers.
This is a bounded review, not a second implementation or full backlog audit.

Use the provided github_api tool to create/update one comment headed
"Life OS independent review". Report concrete actionable findings with priority,
file/line, violated criterion and a minimal reproduction where possible. Separate
defects from missing external verification and unimplemented future scope. Record
the exact reviewed commit and checks actually performed. Do not mark the entire
contract complete. If no defects are found, say so with remaining verification gaps.

When the review report is saved, add symphony:review and remove symphony:ready so
the same review does not run repeatedly. The primary orchestrator owns corrections,
integration and final acceptance. If essential source is unavailable or execution
fails, save the precise blocker, add symphony:blocked and remove symphony:ready.
Keep credentials, personal data and raw provider payloads out of comments/logs.
