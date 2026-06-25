@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
set ROOT=%~dp0
cd /d "%ROOT%"
docker compose -f docker-compose.yml -f docker-compose.local-infra.yml stop mysql redis
