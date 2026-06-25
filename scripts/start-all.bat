@echo off
setlocal
set "ROOT=%~dp0.."
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
echo Starting local fulfillment center and Xianyu services...
start "fulfillment-center 8765" /D "%ROOT%\services\fulfillment-center" cmd /c start-backend.bat
call "%ROOT%\services\xianyu-auto-reply\start-all.bat"
echo.
echo Open fulfillment center: http://127.0.0.1:8765/
echo Open Xianyu frontend:   http://127.0.0.1:9000/
endlocal
