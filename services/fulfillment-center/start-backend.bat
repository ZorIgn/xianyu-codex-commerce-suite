@echo off
setlocal
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%~dp0"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
endlocal
