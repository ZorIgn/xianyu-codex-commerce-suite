@echo off
setlocal
set "ROOT=%~dp0..\services\xianyu-auto-reply"
cd /d "%ROOT%"
docker compose -f docker-compose.yml -f docker-compose.local-infra.yml stop mysql redis
endlocal
