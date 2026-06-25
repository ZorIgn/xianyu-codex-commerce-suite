@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv-xianyu"
set "PY=%VENV%\Scripts\python.exe"
set "LOGDIR=%ROOT%run-logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo Starting backend-web... > "%LOGDIR%\backend-web.out.log"
start "xianyu-backend-web 8089" /D "%ROOT%backend-web" cmd /k ""%PY%" main.py 1>>"%LOGDIR%\backend-web.out.log" 2>>&1"

echo Starting websocket... > "%LOGDIR%\websocket.out.log"
start "xianyu-websocket 8090" /D "%ROOT%websocket" cmd /k ""%PY%" main.py 1>>"%LOGDIR%\websocket.out.log" 2>>&1"

echo Starting scheduler... > "%LOGDIR%\scheduler.out.log"
start "xianyu-scheduler 8091" /D "%ROOT%scheduler" cmd /k ""%PY%" main.py 1>>"%LOGDIR%\scheduler.out.log" 2>>&1"

echo Starting frontend... > "%LOGDIR%\frontend.out.log"
start "xianyu-frontend 9000" /D "%ROOT%frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 9000 1>>"%LOGDIR%\frontend.out.log" 2>>&1"
