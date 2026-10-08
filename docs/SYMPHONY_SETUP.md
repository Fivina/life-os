# Development orchestration installation

OpenAI Symphony is installed as development tooling outside the Life OS application.
The agents inside the application remain a separate system.

## Installed components

- Official source checkout: `E:\LifeOS-Tools\symphony` (source revision
  `be10a1b79df723d6d7612b5651c8522704dafb2e`).
- Native Windows Symphony is built from the official source in
  `E:\LifeOS-Tools\symphony\elixir\bin\symphony`.
- Portable Erlang/OTP `28.5.0.7` and Elixir `1.19.5` are installed under
  `E:\LifeOS-Tools\symphony-runtime`. Downloads were checked against the official
  GitHub release asset digest (Erlang) and published checksum (Elixir).
- The native launcher uses the existing Windows Codex `0.159.0` and ChatGPT sign-in.
  It sets runtime paths only in its process, without changing the global PATH.
- Logs go to `E:\LifeOS-Tools\symphony-runtime\logs`.
- The Linux Symphony `v0.0.3` release and matching Codex package were also installed
  under `/opt/lifeos-symphony` in the newly installed WSL `Ubuntu-24.04` distro.
  Their download checksums were verified. However, the existing WSL `3.0.1` runtime
  intermittently fails to start Ubuntu (`CreateInstance/E_FAIL`, code 6, step 2;
  also `E_UNEXPECTED`). The native launcher is the default to avoid this issue.
- The optional WSL account `lifeos` has no sudo privileges and reuses the existing
  sign-in through a local auth-file symlink. No credentials are added to the repo.

Download files and the runtime installer are retained at
`E:\LifeOS-Tools\symphony-runtime`.

## Start and check

From PowerShell in `D:\Life OS`:

```powershell
.\scripts\start-symphony.ps1 -Doctor
.\scripts\start-symphony.ps1
```

The second command runs in the foreground. Keep the terminal open; press Ctrl+C
to stop it. Open <http://localhost:8787> for the dashboard. The API is available
at <http://localhost:8787/api/v1/state>.

The default `.codex/symphony/WORKFLOW.windows.idle.md` uses Symphony's empty in-memory
tracker. It verifies startup and the dashboard without dispatching work. It is
not a persistent task tracker, PDF ingestion pipeline, or configured development
team. Its Codex execution policy is read-only and it caps concurrent runs at two.
The upstream executable requires a preview acknowledgement flag; the launcher
supplies it while the workflow explicitly sets its execution policy.

The native build runs the official source rather than an upstream Windows release
binary (upstream release binaries target Linux and macOS). The empty-queue check
does not verify an actual coding task. WSL files are retained for diagnosis; the
optional `-Runtime WSL` launcher currently depends on resolving the startup issue.

The upstream locked dependency set reports security advisories during `mix deps.get`.
This installation preserves the upstream lockfile. Keep this evaluation dashboard
bound to localhost; review and update the dependency set before exposing the service
or relying on it for unattended production operation.

## Connecting real development work

Installation does not configure the complete planning and review loop. Before a
live workflow can run, Life OS needs a committed, cloneable source repository
and a chosen task tracker with credentials. At installation time the current
repository has no commits, Git remote, or configured tracker credentials.
Do not commit `.env` files or credentials when preparing the source repository.

The intended follow-up is a lead agent that reads the user's brief, inspects the
existing application, creates tasks with dependencies and acceptance criteria,
and assigns bounded work. An independent reviewer returns findings to workers;
the lead integrates and verifies full workflows. The user supplies requirements,
not a hand-written task plan. This planning/review layer has not been installed
or verified by the installation step.

Use a separately configured workflow when ready:

```powershell
.\scripts\start-symphony.ps1 -WorkflowPath 'D:\Life OS\WORKFLOW.md'
```

Preserve existing `AGENTS.md` rules, Phengos milestone feedback gates, and routed
features when creating that workflow. Use isolated workspaces and enforce the
project-wide agent limit in the complete configuration, including any nested
subagents; the Symphony concurrency setting alone only caps top-level runs.

Official references:

- <https://github.com/openai/symphony>
- <https://github.com/openai/symphony/blob/main/elixir/README.md>
- <https://github.com/openai/symphony/blob/main/SPEC.md>

## Installation verification (2026-10-08)

- Official source built successfully with `mix build`; the upstream source and
  lockfile have no local edits.
- `scripts/start-symphony.ps1 -Doctor` passes: Erlang/Elixir, Codex version,
  ChatGPT sign-in, Git, and the built Symphony executable are available.
- Codex App Server initializes successfully both directly and through Git Bash,
  which is the shell used by Symphony on Windows. No agent turn was started.
- Dashboard `/` and `/api/v1/state` return HTTP 200. The listener binds only to
  `127.0.0.1:8787`. The empty tracker reports zero running, retrying, and blocked
  tasks and zero model tokens.
- Life OS frontend (`5173`) and backend health (`8000/health`) still return HTTP 200.
- The Windows build emits a Phoenix colocated-JS symlink warning; dashboard and
  state API checks pass without elevation. Live task execution remains unverified.
