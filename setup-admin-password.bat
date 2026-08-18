@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0"
set "SERVICE_ROOT=%REPO_ROOT%services\xianyu-auto-reply"
set "PYTHON=%SERVICE_ROOT%\.venv-xianyu\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python environment not found:
    echo         %PYTHON%
    echo Install the xianyu service dependencies first, then run this script again.
    exit /b 1
)

if not exist "%SERVICE_ROOT%\backend-web\app\admin_password.py" (
    echo [ERROR] Local administrator password command is missing from the repository.
    exit /b 1
)

set "PYTHONPATH=%SERVICE_ROOT%;%SERVICE_ROOT%\backend-web;%PYTHONPATH%"
pushd "%SERVICE_ROOT%\backend-web"
"%PYTHON%" -m app.admin_password setup --username admin
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
