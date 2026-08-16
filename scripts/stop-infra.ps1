Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$XianyuRoot = Join-Path $Root "services\xianyu-auto-reply"
$DockerConfigRoot = Join-Path $Root ".docker"
New-Item -ItemType Directory -Path $DockerConfigRoot -Force | Out-Null
$env:DOCKER_CONFIG = $DockerConfigRoot
$Docker = (Get-Command docker.exe -ErrorAction Stop).Source
& $Docker compose `
    -f (Join-Path $XianyuRoot "docker-compose.yml") `
    -f (Join-Path $XianyuRoot "docker-compose.local-infra.yml") `
    stop mysql redis
if ($LASTEXITCODE -ne 0) { throw "MySQL/Redis 停止失败。" }
Write-Host "MySQL/Redis 已停止。"
