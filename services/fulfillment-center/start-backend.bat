@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
cd /d %~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-desktop-bridge.ps1"
if errorlevel 1 (
  echo [ERROR] Desktop activation bridge failed to start.
  pause
  exit /b 1
)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765