@echo off
setlocal
set "NETSTAT=%SystemRoot%\System32\netstat.exe"
set "TASKKILL=%SystemRoot%\System32\taskkill.exe"
for %%p in (8765 8089 8090 8091 9000) do (
  for /f "tokens=5" %%a in ('"%NETSTAT%" -ano ^| findstr ":%%p "') do "%TASKKILL%" /PID %%a /F >nul 2>nul
)
echo Stopped local app ports 8765/8089/8090/8091/9000.
endlocal
