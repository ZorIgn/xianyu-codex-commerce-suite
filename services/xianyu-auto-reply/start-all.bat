@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
setlocal
set ROOT=%~dp0
set VENV=%ROOT%.venv-xianyu
set PY=%VENV%\Scripts\python.exe

if not exist "%PY%" (
  echo [ERROR] venv not found. Run install-all.bat first.
  pause
  exit /b 1
)

if not exist "%ROOT%websocket\.env" (
  copy "%ROOT%websocket\.env.example" "%ROOT%websocket\.env" >nul
)
findstr /C:"FULFILLMENT_CENTER_ENABLED" "%ROOT%websocket\.env" >nul || (
  echo.>>"%ROOT%websocket\.env"
  echo FULFILLMENT_CENTER_ENABLED=true>>"%ROOT%websocket\.env"
  echo FULFILLMENT_CENTER_URL=http://127.0.0.1:8765>>"%ROOT%websocket\.env"
  echo FULFILLMENT_CENTER_TIMEOUT=30>>"%ROOT%websocket\.env"
)

if not exist "%ROOT%backend-web\.env" copy "%ROOT%backend-web\.env.example" "%ROOT%backend-web\.env" >nul
if not exist "%ROOT%scheduler\.env" copy "%ROOT%scheduler\.env.example" "%ROOT%scheduler\.env" >nul

echo Starting MySQL/Redis infrastructure...
call "%ROOT%start-infra.bat"
if errorlevel 1 (
  echo [ERROR] MySQL/Redis infrastructure failed to start.
  exit /b 1
)
timeout /t 12 /nobreak >nul

call "%ROOT%start-services-logged.bat"

echo Started Xianyu services.
echo Frontend: http://127.0.0.1:9000/
echo Backend docs: http://127.0.0.1:8089/docs
echo WebSocket health: http://127.0.0.1:8090/health
echo Scheduler health: http://127.0.0.1:8091/health
echo Fulfillment center: http://127.0.0.1:8765/






