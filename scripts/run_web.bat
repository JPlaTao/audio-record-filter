@echo off
REM 通话录音分级系统 — Web UI 一键启动 (Windows)
cd /d "%~dp0.."

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [31m虚拟环境不存在，请先执行: python -m venv venv ^&^& pip install -r requirements.txt[0m
    exit /b 1
)

echo [36m启动 Web UI 服务... http://localhost:8080[0m
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080
