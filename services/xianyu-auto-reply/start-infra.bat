@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
set "DOCKER_CONFIG=E:\account\.docker-codex"
set ROOT=%~dp0
cd /d "%ROOT%"
docker version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker Desktop is not running or current user cannot access Docker.
  echo Please start Docker Desktop and try again.
  exit /b 1
)
docker compose -f docker-compose.yml -f docker-compose.local-infra.yml up -d mysql redis
if errorlevel 1 exit /b 1
