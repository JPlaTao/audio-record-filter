#!/usr/bin/env bash
# 通话录音分级系统 — 一键运行脚本
set -euo pipefail

cd "$(dirname "$0")/.."

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/Scripts/activate
else
    echo "❌ 虚拟环境不存在，请先执行: python -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# 检查 ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "⚠ ffmpeg 未安装，Whisper 无法处理音频文件"
    echo "  请安装 ffmpeg 并确保在 PATH 中"
fi

exec python src/cli.py "$@"
