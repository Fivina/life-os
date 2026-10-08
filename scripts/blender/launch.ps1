$ErrorActionPreference = 'Stop'
$blender = 'E:\Blender\blender.exe'
if (-not (Test-Path -LiteralPath $blender)) { throw "Blender not found: $blender" }
if (Get-Process blender -ErrorAction SilentlyContinue) {
    Write-Output 'Blender is already open. Existing sessions were left untouched.'
    exit 0
}
$env:BLENDERMCP_NO_UPDATE_CHECK = '1'
$env:BLENDER_MCP_DISABLE_TELEMETRY = '1'
# The user requested a visible Blender editor, not a background service window.
Start-Process -FilePath $blender -WindowStyle Normal
