@echo off
REM 通话录音分级系统 — 一键运行脚本 (Windows)
cd /d "%~dp0.."

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [31m虚拟环境不存在，请先执行: python -m venv venv ^&^& pip install -r requirements.txt[0m
    exit /b 1
)

python src/cli.py %*
