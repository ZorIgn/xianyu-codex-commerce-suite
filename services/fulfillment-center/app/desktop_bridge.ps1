param(
  [string]$BridgeRoot = "",
  [string]$UiScript = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($BridgeRoot)) {
  $BridgeRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "data\desktop_bridge"
}
if ([string]::IsNullOrWhiteSpace($UiScript)) {
  $UiScript = Join-Path $PSScriptRoot "activation_ui.ps1"
}

$BridgeRoot = [System.IO.Path]::GetFullPath($BridgeRoot)
$UiScript = [System.IO.Path]::GetFullPath($UiScript)
$requestDir = Join-Path $BridgeRoot "requests"
$workingDir = Join-Path $BridgeRoot "working"
$responseDir = Join-Path $BridgeRoot "responses"
$heartbeatPath = Join-Path $BridgeRoot "heartbeat.json"
$stopPath = Join-Path $BridgeRoot "stop"

function Write-JsonAtomic {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)]$Value
  )

  $json = $Value | ConvertTo-Json -Compress -Depth 12
  $temp = "$Path.$PID.$([DateTime]::UtcNow.Ticks).tmp"
  [System.IO.File]::WriteAllText($temp, $json, [System.Text.UTF8Encoding]::new($false))
  Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Write-Heartbeat {
  try {
    $payload = [ordered]@{
      pid = $PID
      ready = $true
      updated_at = [DateTime]::UtcNow.ToString("o")
      ui_script = $UiScript
    } | ConvertTo-Json -Compress
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($payload)
    $stream = [System.IO.FileStream]::new(
      $heartbeatPath,
      [System.IO.FileMode]::OpenOrCreate,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::ReadWrite
    )
    try {
      $stream.SetLength(0)
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Flush()
    } finally {
      $stream.Dispose()
    }
  } catch {
    # A missed heartbeat must never terminate the bridge.
  }
}
function Invoke-UiRequest {
  param([Parameter(Mandatory=$true)]$Request)

  $operation = [string]$Request.operation
  if ($operation -notin @("snapshot", "send", "windows", "prepare")) {
    throw "unsupported operation: $operation"
  }
  $targetPid = [int]$Request.target_pid
  if ($targetPid -le 0) {
    throw "target_pid must be positive"
  }

  $arguments = @{
    Operation = $operation
    TargetPid = $targetPid
    HeartbeatPath = $heartbeatPath
    AllowForegroundFallback = [bool]$Request.allow_foreground_fallback
  }
  if ($operation -eq "send") {
    $arguments.PromptB64 = [string]$Request.prompt_b64
    $arguments.TimeoutSeconds = [int]$Request.timeout_seconds
  }

  $lines = @(& $UiScript @arguments)
  $jsonLine = @($lines | ForEach-Object { [string]$_ } | Where-Object {
    -not [string]::IsNullOrWhiteSpace($_)
  }) | Select-Object -Last 1
  if ([string]::IsNullOrWhiteSpace($jsonLine)) {
    throw "UI Automation returned no result"
  }
  return $jsonLine | ConvertFrom-Json
}

$createdNew = $false
$mutexSuffix = ($BridgeRoot -replace '[^A-Za-z0-9_.-]', '_')
$mutex = [System.Threading.Mutex]::new(
  $true,
  "Local\XianyuCodexDesktopBridge_$mutexSuffix",
  [ref]$createdNew
)
if (-not $createdNew) {
  $mutex.Dispose()
  exit 0
}

try {
  New-Item -ItemType Directory -Force -Path $requestDir, $workingDir, $responseDir | Out-Null
  Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
  Write-Heartbeat

  while (-not (Test-Path -LiteralPath $stopPath)) {
    Write-Heartbeat
    $requests = @(Get-ChildItem -LiteralPath $requestDir -Filter "*.json" -File |
      Sort-Object LastWriteTimeUtc, Name)

    foreach ($requestFile in $requests) {
      if (Test-Path -LiteralPath $stopPath) { break }
      $workingPath = Join-Path $workingDir $requestFile.Name
      try {
        Move-Item -LiteralPath $requestFile.FullName -Destination $workingPath -ErrorAction Stop
      } catch {
        continue
      }

      $requestId = [System.IO.Path]::GetFileNameWithoutExtension($requestFile.Name)
      $responsePath = Join-Path $responseDir "$requestId.json"
      try {
        $request = Get-Content -LiteralPath $workingPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $result = Invoke-UiRequest -Request $request
        $response = [ordered]@{
          ok = $true
          request_id = $requestId
          result = $result
          completed_at = [DateTime]::UtcNow.ToString("o")
        }
      } catch {
        $response = [ordered]@{
          ok = $false
          request_id = $requestId
          error = $_.Exception.Message
          completed_at = [DateTime]::UtcNow.ToString("o")
        }
      }

      Write-JsonAtomic -Path $responsePath -Value $response
      Remove-Item -LiteralPath $workingPath -Force -ErrorAction SilentlyContinue
      Write-Heartbeat
    }

    Start-Sleep -Milliseconds 150
  }
} finally {
  Remove-Item -LiteralPath $heartbeatPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
  try { $mutex.ReleaseMutex() } catch {}
  $mutex.Dispose()
}