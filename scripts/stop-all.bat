@echo off
call "%~dp0..\stop-all.bat" %*
exit /b %ERRORLEVEL%
