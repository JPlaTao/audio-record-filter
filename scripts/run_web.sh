#!/usr/bin/env bash
# 通话录音分级系统 — Web UI 一键启动
set -euo pipefail

cd "$(dirname "$0")/.."

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/Scripts/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ 虚拟环境不存在，请先执行: python -m venv venv && pip install -r requirements.txt"
    exit 1
fi

echo "启动 Web UI 服务... http://localhost:8080"
exec python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080
