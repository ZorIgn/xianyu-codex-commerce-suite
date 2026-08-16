@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\stop-suite.ps1" -ForcePorts
exit /b %ERRORLEVEL%
