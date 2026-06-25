@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8089 "') do taskkill /PID %%a /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8090 "') do taskkill /PID %%a /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8091 "') do taskkill /PID %%a /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9000 "') do taskkill /PID %%a /F >nul 2>nul
echo Stopped Xianyu ports 8089/8090/8091/9000.


