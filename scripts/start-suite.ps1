[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$XianyuRoot = Join-Path $Root "services\xianyu-auto-reply"
$FulfillmentRoot = Join-Path $Root "services\fulfillment-center"
$FrontendRoot = Join-Path $XianyuRoot "frontend"
$LogRoot = Join-Path $Root "run-logs"
$StateRoot = Join-Path $Root "run-state"
$StateFile = Join-Path $StateRoot "processes.json"
$CacheRoot = Join-Path $Root ".cache"
$BrowserRoot = Join-Path $XianyuRoot ".playwright"
$DockerConfigRoot = Join-Path $Root ".docker"
$script:StartedProcesses = @()

function Write-Step([string]$Message) {
    Write-Host "`n== $Message ==" -ForegroundColor Cyan
}

function Require-Command([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "缺少命令 $Name，请先安装后重新运行 start-all.bat。"
    }
    return $command.Source
}

function Copy-ExampleIfMissing([string]$Directory) {
    $target = Join-Path $Directory ".env"
    $example = Join-Path $Directory ".env.example"
    if (-not (Test-Path -LiteralPath $target)) {
        if (-not (Test-Path -LiteralPath $example)) {
            throw "缺少配置模板：$example"
        }
        Copy-Item -LiteralPath $example -Destination $target
        Write-Host "已创建配置：$target"
    }
}

function Get-DependencyFingerprint([string[]]$Paths) {
    $parts = foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "缺少依赖文件：$path"
        }
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    return $parts -join ":"
}

function Ensure-PythonEnvironment(
    [string]$Name,
    [string]$VenvRoot,
    [string[]]$DependencyFiles,
    [scriptblock]$Install
) {
    $python = Join-Path $VenvRoot "Scripts\python.exe"
    $marker = Join-Path $VenvRoot ".suite-dependencies"
    $fingerprint = Get-DependencyFingerprint $DependencyFiles

    if (-not (Test-Path -LiteralPath $python)) {
        if ($SkipInstall) { throw "$Name 虚拟环境不存在：$VenvRoot" }
        Write-Host "正在创建 $Name 虚拟环境：$VenvRoot"
        & $script:BasePython -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "$Name 虚拟环境创建失败。" }
    }

    $installedFingerprint = if (Test-Path -LiteralPath $marker) {
        (Get-Content -LiteralPath $marker -Raw).Trim()
    } else { "" }
    if ($installedFingerprint -ne $fingerprint) {
        if ($SkipInstall) { throw "$Name 依赖尚未安装或已经变化。" }
        Write-Host "正在安装 $Name 依赖..."
        & $Install $python | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "$Name 依赖安装失败。" }
        [System.IO.File]::WriteAllText($marker, $fingerprint, [System.Text.UTF8Encoding]::new($false))
    }
    return $python
}

function Ensure-FrontendDependencies([string]$Npm) {
    $lockFile = Join-Path $FrontendRoot "package-lock.json"
    $modules = Join-Path $FrontendRoot "node_modules"
    $marker = Join-Path $modules ".suite-dependencies"
    $fingerprint = Get-DependencyFingerprint @($lockFile)
    $installedFingerprint = if (Test-Path -LiteralPath $marker) {
        (Get-Content -LiteralPath $marker -Raw).Trim()
    } else { "" }

    if ($installedFingerprint -eq $fingerprint) { return }
    if ($SkipInstall) { throw "前端依赖不存在或已经变化。" }
    Write-Host "正在安装前端依赖..."
    Push-Location $FrontendRoot
    try {
        & $Npm ci
        if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
        [System.IO.File]::WriteAllText($marker, $fingerprint, [System.Text.UTF8Encoding]::new($false))
    } finally {
        Pop-Location
    }
}

function Test-Http([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Get-ListeningPid([int]$Port) {
    try {
        return Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
            Select-Object -First 1 -ExpandProperty OwningProcess
    } catch {
        return $null
    }
}

function Test-DockerDaemon([string]$DockerPath) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $DockerPath info *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Save-ProcessState {
    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
    $payload = @($script:StartedProcesses) | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($StateFile, $payload, [System.Text.UTF8Encoding]::new($false))
}

function Wait-Http(
    [string]$Name,
    [string]$Url,
    [System.Diagnostics.Process]$Process,
    [string]$ErrorLog,
    [int]$TimeoutSeconds = 120
) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Http $Url) {
            Write-Host "$Name 已就绪：$Url" -ForegroundColor Green
            return
        }
        if ($Process.HasExited) {
            $tail = if (Test-Path -LiteralPath $ErrorLog) {
                (Get-Content -LiteralPath $ErrorLog -Tail 20) -join [Environment]::NewLine
            } else { "无错误日志" }
            throw "$Name 启动后退出。`n$tail"
        }
        Start-Sleep -Milliseconds 800
    }
    throw "$Name 在 $TimeoutSeconds 秒内未通过健康检查，查看 $ErrorLog"
}

function Start-ManagedProcess(
    [string]$Name,
    [int]$Port,
    [string]$HealthUrl,
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [int]$TimeoutSeconds = 120
) {
    if (Test-Http $HealthUrl) {
        Write-Host "$Name 已在运行：$HealthUrl" -ForegroundColor DarkGreen
        return
    }
    $listeningPid = Get-ListeningPid $Port
    if ($listeningPid) {
        throw "端口 $Port 已被 PID $listeningPid 占用，但 $Name 健康检查失败。请先运行 stop-all.bat。"
    }

    $safeName = $Name.ToLowerInvariant().Replace(" ", "-")
    $outLog = Join-Path $LogRoot "$safeName.out.log"
    $errLog = Join-Path $LogRoot "$safeName.err.log"
    Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $script:StartedProcesses += [pscustomobject]@{
        name = $Name
        pid = $process.Id
        port = $Port
        started_at = (Get-Date).ToString("o")
    }
    Save-ProcessState
    Wait-Http $Name $HealthUrl $process $errLog $TimeoutSeconds
}

Write-Step "检查本机环境"
$script:BasePython = Require-Command "python.exe"
$Docker = Require-Command "docker.exe"
$Npm = Require-Command "npm.cmd"
$Cmd = Join-Path $env:SystemRoot "System32\cmd.exe"

if ($CheckOnly) {
    Write-Host "仓库：$Root"
    Write-Host "Python：$script:BasePython"
    Write-Host "Docker：$Docker"
    Write-Host "npm：$Npm"
    Write-Host "启动脚本检查完成。"
    exit 0
}

New-Item -ItemType Directory -Path $LogRoot, $StateRoot, $CacheRoot, $DockerConfigRoot -Force | Out-Null
$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
$env:npm_config_cache = Join-Path $CacheRoot "npm"
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowserRoot
$env:DOCKER_CONFIG = $DockerConfigRoot

Write-Step "准备本地配置"
Copy-ExampleIfMissing $FulfillmentRoot
Copy-ExampleIfMissing (Join-Path $XianyuRoot "backend-web")
Copy-ExampleIfMissing (Join-Path $XianyuRoot "websocket")
Copy-ExampleIfMissing (Join-Path $XianyuRoot "scheduler")

Write-Step "准备仓库内依赖"
$XianyuPython = Ensure-PythonEnvironment "闲鱼服务" (Join-Path $XianyuRoot ".venv-xianyu") @(
    (Join-Path $XianyuRoot "backend-web\pyproject.toml"),
    (Join-Path $XianyuRoot "websocket\pyproject.toml"),
    (Join-Path $XianyuRoot "scheduler\pyproject.toml")
) {
    param($Python)
    & $Python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { return }
    & $Python -m pip install -e (Join-Path $XianyuRoot "backend-web") -e (Join-Path $XianyuRoot "websocket") -e (Join-Path $XianyuRoot "scheduler")
}
$FulfillmentPython = Ensure-PythonEnvironment "履约中心" (Join-Path $FulfillmentRoot ".venv") @(
    (Join-Path $FulfillmentRoot "requirements.txt")
) {
    param($Python)
    & $Python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { return }
    & $Python -m pip install -r (Join-Path $FulfillmentRoot "requirements.txt")
}
if (-not (Get-ChildItem -LiteralPath $BrowserRoot -Directory -Filter "chromium-*" -ErrorAction SilentlyContinue)) {
    if ($SkipInstall) { throw "仓库内尚未安装 Playwright Chromium。" }
    Write-Host "正在把 Playwright Chromium 安装到 $BrowserRoot ..."
    & $XianyuPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium 安装失败。" }
}
Ensure-FrontendDependencies $Npm

Write-Step "启动 MySQL 和 Redis"
if (-not (Test-DockerDaemon $Docker)) {
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $dockerDesktop) {
        Write-Host "Docker Desktop 尚未运行，正在启动..."
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
        $dockerDeadline = (Get-Date).AddSeconds(120)
        while ((Get-Date) -lt $dockerDeadline -and -not (Test-DockerDaemon $Docker)) {
            Start-Sleep -Seconds 2
        }
    }
}
if (-not (Test-DockerDaemon $Docker)) {
    throw "Docker Desktop 未能在 120 秒内启动，请检查 WSL/Docker 状态。"
}
$ComposeArgs = @(
    "compose",
    "-f", (Join-Path $XianyuRoot "docker-compose.yml"),
    "-f", (Join-Path $XianyuRoot "docker-compose.local-infra.yml")
)
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $Docker @ComposeArgs up -d mysql redis | Out-Host
    $composeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($composeExitCode -ne 0) { throw "MySQL/Redis 启动失败。" }

$infraDeadline = (Get-Date).AddSeconds(120)
do {
    $mysqlHealth = (& $Docker inspect --format "{{.State.Health.Status}}" xianyu-mysql 2>$null)
    $redisHealth = (& $Docker inspect --format "{{.State.Health.Status}}" xianyu-redis 2>$null)
    if ($mysqlHealth -eq "healthy" -and $redisHealth -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $infraDeadline)
if ($mysqlHealth -ne "healthy" -or $redisHealth -ne "healthy") {
    throw "MySQL/Redis 未在 120 秒内就绪。"
}

Write-Step "启动应用服务"
Start-ManagedProcess "fulfillment-center" 8765 "http://127.0.0.1:8765/health" `
    $FulfillmentPython @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765") $FulfillmentRoot 90
Start-ManagedProcess "xianyu-backend-web" 8089 "http://127.0.0.1:8089/api/v1/health/ping" `
    $XianyuPython @("main.py") (Join-Path $XianyuRoot "backend-web") 150
Start-ManagedProcess "xianyu-websocket" 8090 "http://127.0.0.1:8090/health" `
    $XianyuPython @("main.py") (Join-Path $XianyuRoot "websocket") 120
Start-ManagedProcess "xianyu-scheduler" 8091 "http://127.0.0.1:8091/health" `
    $XianyuPython @("main.py") (Join-Path $XianyuRoot "scheduler") 120
$frontendCommand = "`"$Npm`" run dev -- --host 127.0.0.1 --port 9000"
Start-ManagedProcess "xianyu-frontend" 9000 "http://127.0.0.1:9000/" `
    $Cmd @("/d", "/s", "/c", $frontendCommand) $FrontendRoot 120

Write-Step "服务入口"
Write-Host "闲鱼管理后台  http://127.0.0.1:9000/"
Write-Host "本地库存中心  http://127.0.0.1:8765/"
Write-Host "后端接口文档  http://127.0.0.1:8089/docs"
Write-Host "运行日志目录  $LogRoot"
