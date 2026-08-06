param(
  [string]$BridgeRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $MyInvocation.MyCommand.Path -Parent
if ([string]::IsNullOrWhiteSpace($BridgeRoot)) {
  $BridgeRoot = Join-Path $projectRoot "data\desktop_bridge"
}
$BridgeRoot = [System.IO.Path]::GetFullPath($BridgeRoot)
$heartbeatPath = Join-Path $BridgeRoot "heartbeat.json"
$bridgeScript = Join-Path $projectRoot "app\desktop_bridge.ps1"
$uiScript = Join-Path $projectRoot "app\activation_ui.ps1"
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

function Test-BridgeOnline {
  if (-not (Test-Path -LiteralPath $heartbeatPath)) { return $false }
  try {
    $heartbeat = Get-Content -LiteralPath $heartbeatPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $process = Get-Process -Id ([int]$heartbeat.pid) -ErrorAction Stop
    $updated = [DateTime]::Parse([string]$heartbeat.updated_at).ToUniversalTime()
    return $process.ProcessName -like "powershell*" -and
      (([DateTime]::UtcNow - $updated).TotalSeconds -lt 10)
  } catch {
    return $false
  }
}

if (Test-BridgeOnline) {
  Write-Host "Desktop activation bridge is already running."
  exit 0
}

New-Item -ItemType Directory -Force -Path $BridgeRoot | Out-Null
Remove-Item -LiteralPath (Join-Path $BridgeRoot "stop") -Force -ErrorAction SilentlyContinue
$arguments = @(
  "-NoProfile",
  "-STA",
  "-ExecutionPolicy", "Bypass",
  "-File", $bridgeScript,
  "-BridgeRoot", $BridgeRoot,
  "-UiScript", $uiScript
)
Start-Process -FilePath $powershell -ArgumentList $arguments -WindowStyle Hidden | Out-Null

$deadline = [DateTime]::UtcNow.AddSeconds(15)
while ([DateTime]::UtcNow -lt $deadline) {
  if (Test-BridgeOnline) {
    Write-Host "Desktop activation bridge is ready."
    exit 0
  }
  Start-Sleep -Milliseconds 250
}

throw "Desktop activation bridge did not become ready within 15 seconds."