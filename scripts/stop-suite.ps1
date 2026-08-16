[CmdletBinding()]
param([switch]$ForcePorts)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StateFile = Join-Path $Root "run-state\processes.json"
$TaskKill = Join-Path $env:SystemRoot "System32\taskkill.exe"

function Stop-Tree([int]$ProcessId) {
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        & $TaskKill /PID $ProcessId /T /F *> $null
    }
}

if (Test-Path -LiteralPath $StateFile) {
    $records = @(Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json)
    foreach ($record in $records) {
        Stop-Tree ([int]$record.pid)
    }
    Remove-Item -LiteralPath $StateFile -Force
}

if ($ForcePorts) {
    foreach ($port in @(8765, 8089, 8090, 8091, 9000)) {
        $pids = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($processId in $pids) { Stop-Tree ([int]$processId) }
    }
}

Write-Host "应用服务已停止。MySQL/Redis 保持运行；需要停止基础设施时运行 stop-infra.bat。"
