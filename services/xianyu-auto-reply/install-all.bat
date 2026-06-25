@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
setlocal
set ROOT=%~dp0
set VENV=%ROOT%.venv-xianyu

if not exist "%VENV%\Scripts\python.exe" (
  echo [1/5] Creating Python venv...
  python -m venv "%VENV%"
)

echo [2/5] Upgrading pip...
"%VENV%\Scripts\python.exe" -m pip install -U pip setuptools wheel

echo [3/5] Installing backend-web/websocket/scheduler dependencies...
"%VENV%\Scripts\python.exe" -m pip install -e "%ROOT%backend-web" -e "%ROOT%websocket" -e "%ROOT%scheduler"

echo [4/5] Installing frontend dependencies...
cd /d "%ROOT%frontend"
if exist package-lock.json (
  call npm install
) else (
  call npm install
)

echo [5/5] Done.
echo Python: %VENV%\Scripts\python.exe
echo Frontend: %ROOT%frontend


