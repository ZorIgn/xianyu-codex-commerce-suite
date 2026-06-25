@echo off
rem =====================================================================
rem 按端口停止服务
rem 参数 1：服务名（用于显示）
rem 参数 2：监听端口
rem 功能：查询指定端口上的 LISTENING 进程并强制结束
rem =====================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "SERVICE_NAME=%~1"
set "PORT=%~2"

if "%SERVICE_NAME%"=="" (
    echo [错误] 未指定服务名
    exit /b 1
)
if "%PORT%"=="" (
    echo [错误] 未指定端口号
    exit /b 1
)

echo.
echo ===============================================
echo   正在停止 %SERVICE_NAME%（端口：%PORT%）
echo ===============================================

set "FOUND=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "PID=%%P"
    if not "!PID!"=="0" (
        set "FOUND=1"
        echo [信息] 发现占用端口 %PORT% 的进程 PID=!PID!，正在停止...
        taskkill /F /PID !PID! >nul 2>&1
        if !errorlevel! equ 0 (
            echo [成功] 进程 !PID! 已停止
        ) else (
            echo [警告] 停止进程 !PID! 失败（可能已退出或权限不足）
        )
    )
)

if "%FOUND%"=="0" (
    echo [提示] 端口 %PORT% 上未发现运行中的 %SERVICE_NAME%
    endlocal
    exit /b 0
)

echo.
echo [完成] %SERVICE_NAME% 已停止
endlocal
exit /b 0
