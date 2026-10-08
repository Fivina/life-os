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

The private repository is <https://github.com/Fivina/life-os>; `origin` points to
its HTTPS Git URL. GitHub Issues is the tracker. GitHub CLI is installed at
`E:\LifeOS-Tools\github-cli\bin\gh.exe` and authorized as `Fivina`.

The connected development workflow is `.codex/symphony/WORKFLOW.github.md`:

- Only open issues with `symphony:ready` are dispatchable. Ordinary issues do not
  start agent work. `symphony:review` and `symphony:blocked` are handoff labels.
- A lead creates the dependency-ordered task checklist from the user's brief,
  assigns bounded work, requires independent review, routes corrections back to
  workers, and verifies integration. Progress belongs in an issue workpad and Git.
- One top-level issue runs at a time, with at most two nested subagents. The lead
  keeps integration ownership and respects the existing milestone feedback gates.
- Changes run in isolated workspaces on codex/ branches. Completion produces a PR;
  the workflow does not authorize merging or deploying.
- The launcher obtains the tracker token from GitHub CLI into its process environment.
  Symphony strips declared tracker token variables from the Codex child. No token
  is written into the repository or workflow.

Run the connected checks and service:

```powershell
.\scripts\start-symphony.ps1 -GitHub -Doctor
.\scripts\start-symphony.ps1 -GitHub
```

Stop the existing idle/dashboard process with Ctrl+C before starting another
instance on port 8787. No file attached to a chat is automatically ingested by
Symphony: the brief must be represented by an issue body or accessible referenced
material. When the user supplies the brief here, the assistant can prepare that
issue; the lead is responsible for task decomposition.

This is an instruction-based planning/review workflow atop the official scheduler.
Live implementation, subagent review, and correction cycles need verification with
a bounded real brief; merely connecting the queue does not prove those behaviors.

## Switching accounts

GitHub identity and Codex/ChatGPT identity are separate. Switching the Codex account
does not transfer repository ownership or replace the GitHub CLI credential.
Stop active Symphony workers before changing the Codex sign-in. Preserve in-progress
branches and the issue workpad, verify `codex login status`, and restart the service
under the intended account. Do not assume an already-running Codex process changes
accounts when the desktop app does. Account-specific plan entitlements and usage
limits still apply. This setup does not automatically rotate accounts.

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
- GitHub setup completed as `Fivina`: `Fivina/life-os` is verified `PRIVATE`, Issues
  is enabled, source and workflow commits are pushed, and local/remote heads match.
- Gitleaks passes for the uploaded source. Exact synthetic test fixtures have
  path-scoped exceptions; environment files, databases, runtime screenshots, logs,
  and generated artifacts are excluded from Git.
- The official Symphony GitHub adapter successfully reads the private issue queue
  using the GitHub CLI credential. The connected service is running on port 8787;
  it reports no active or queued work and zero model tokens at setup completion.
