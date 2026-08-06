param(
  [string]$BridgeRoot = ""
)

$projectRoot = Split-Path $MyInvocation.MyCommand.Path -Parent
if ([string]::IsNullOrWhiteSpace($BridgeRoot)) {
  $BridgeRoot = Join-Path $projectRoot "data\desktop_bridge"
}
$BridgeRoot = [System.IO.Path]::GetFullPath($BridgeRoot)
$heartbeatPath = Join-Path $BridgeRoot "heartbeat.json"
$stopPath = Join-Path $BridgeRoot "stop"

if (-not (Test-Path -LiteralPath $heartbeatPath)) {
  Write-Host "Desktop activation bridge is not running."
  exit 0
}

New-Item -ItemType Directory -Force -Path $BridgeRoot | Out-Null
New-Item -ItemType File -Force -Path $stopPath | Out-Null
$deadline = [DateTime]::UtcNow.AddSeconds(10)
while ([DateTime]::UtcNow -lt $deadline) {
  if (-not (Test-Path -LiteralPath $heartbeatPath)) {
    Write-Host "Desktop activation bridge stopped."
    exit 0
  }
  Start-Sleep -Milliseconds 200
}
throw "Desktop activation bridge did not stop within 10 seconds."