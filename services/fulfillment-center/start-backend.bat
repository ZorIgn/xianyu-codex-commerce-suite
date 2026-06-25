@echo off
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
cd /d %~dp0
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
