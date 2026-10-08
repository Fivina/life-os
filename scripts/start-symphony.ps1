[CmdletBinding()]
param(
    [string]$WorkflowPath,
    [ValidateSet('Windows', 'WSL')]
    [string]$Runtime = 'Windows',
    [switch]$Doctor
)

$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu-24.04'
$runtimeUser = 'lifeos'
$runtimeRoot = '/opt/lifeos-symphony'

if ($Runtime -eq 'Windows') {
    $nativeRoot = 'E:/LifeOS-Tools/symphony-runtime'
    $env:PATH = "$nativeRoot/erlang-28/bin;$nativeRoot/elixir-1.19.5/bin;E:/Git/bin;$env:PATH"
    $env:SYMPHONY_CODEX_BIN = (Get-Command codex.exe).Source.Replace('\', '/')
    if ($Doctor) {
        & elixir.bat --version
        if ($LASTEXITCODE -ne 0) { throw 'Elixir runtime check failed.' }
        & $env:SYMPHONY_CODEX_BIN --version
        & $env:SYMPHONY_CODEX_BIN login status
        if ($LASTEXITCODE -ne 0) { throw 'Codex sign-in check failed.' }
        & git --version
        if (-not (Test-Path 'E:/LifeOS-Tools/symphony/elixir/bin/symphony')) {
            throw 'The native Symphony executable has not been built.'
        }
        Write-Host 'Native Symphony executable and dependencies are available.'
        return
    }
    if (-not $WorkflowPath) {
        $WorkflowPath = Join-Path $PSScriptRoot '../.codex/symphony/WORKFLOW.windows.idle.md'
    }
    $resolvedWorkflow = (Resolve-Path -LiteralPath $WorkflowPath).Path
    Write-Host "Starting Symphony with $resolvedWorkflow"
    Write-Host 'The bundled idle workflow has an empty task queue. Dashboard: http://localhost:8787'
    Write-Host 'Keep this terminal open. Press Ctrl+C to stop Symphony.'
    & escript.exe E:/LifeOS-Tools/symphony/elixir/bin/symphony --i-understand-that-this-will-be-running-without-the-usual-guardrails --logs-root E:/LifeOS-Tools/symphony-runtime/logs $resolvedWorkflow
    if ($LASTEXITCODE -ne 0) { throw "Symphony exited with code $LASTEXITCODE." }
    return
}

if (-not $WorkflowPath) {
    $WorkflowPath = Join-Path $PSScriptRoot '../.codex/symphony/WORKFLOW.idle.md'
}

if ($Doctor) {
    & wsl.exe -d $distribution -u $runtimeUser --cd /home/lifeos --exec /bin/bash -c 'set -e; test -x /opt/lifeos-symphony/bin/symphony; /opt/lifeos-symphony/codex/bin/codex --version; /opt/lifeos-symphony/codex/bin/codex login status; git --version; printf "Symphony executable and dependencies are available.\n"'
    if ($LASTEXITCODE -ne 0) { throw 'Symphony dependency check failed.' }
    return
}

$resolvedWorkflow = (Resolve-Path -LiteralPath $WorkflowPath).Path
$linuxWorkflow = (& wsl.exe -d $distribution -u $runtimeUser --exec wslpath -a $resolvedWorkflow | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxWorkflow) {
    throw 'Could not resolve the workflow path inside WSL.'
}

Write-Host "Starting Symphony with $resolvedWorkflow"
Write-Host 'The bundled idle workflow has an empty task queue. Dashboard: http://localhost:8787'
Write-Host 'Keep this terminal open. Press Ctrl+C to stop Symphony.'
& wsl.exe -d $distribution -u $runtimeUser --cd /home/lifeos --exec "$runtimeRoot/bin/symphony" --i-understand-that-this-will-be-running-without-the-usual-guardrails --logs-root /home/lifeos/.local/state/symphony $linuxWorkflow
if ($LASTEXITCODE -ne 0) { throw "Symphony exited with code $LASTEXITCODE." }
