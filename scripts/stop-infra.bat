@echo off
call "%~dp0..\stop-infra.bat" %*
exit /b %ERRORLEVEL%
