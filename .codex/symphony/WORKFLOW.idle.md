---
tracker:
  kind: memory
  active_states: [Todo, In Progress]
  terminal_states: [Done, Closed, Cancelled]
polling:
  interval_ms: 30000
workspace:
  root: /home/lifeos/symphony-workspaces
agent:
  max_concurrent_agents: 2
  max_turns: 20
codex:
  command: /opt/lifeos-symphony/codex/bin/codex app-server
  approval_policy:
    reject:
      sandbox_approval: true
      rules: true
      mcp_elicitations: true
  thread_sandbox: read-only
  turn_sandbox_policy:
    type: readOnly
server:
  host: 127.0.0.1
  port: 8787
observability:
  dashboard_enabled: false
---

This is an empty local tracker for verifying the Symphony installation.
It does not ingest a PDF, dispatch development tasks, or modify Life OS.
Configure a real tracker and an agreed development workflow before running work.
