@echo off
REM 下载 Whisper 模型
REM 用法: download_model.bat [tiny|base|small|medium|large-v3]
setlocal enabledelayedexpansion

set "MODEL_SIZE=%~1"
if "%MODEL_SIZE%"=="" set "MODEL_SIZE=large-v3"

set "MODEL_DIR=%cd%\models\faster-whisper-%MODEL_SIZE%"

echo ==== 通话录音分级系统 — 模型下载工具 ====
echo 正在下载: %MODEL_SIZE% (Systran/faster-whisper-%MODEL_SIZE%)
echo.
echo 注意：如果下载失败，请尝试以下方法：
echo 1. 关闭代理/翻墙软件后重试
echo 2. 手动从 https://hf-mirror.com/Systran/faster-whisper-%MODEL_SIZE% 下载
echo 3. 或使用浏览器打开 HuggingFace 页面手动下载
echo.

mkdir "%MODEL_DIR%" 2>nul

echo [1/3] 下载配置文件...
:: 尝试通过 HF 镜像下载
curl --noproxy * -sL -o "%MODEL_DIR%\config.json" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/config.json"
if %ERRORLEVEL% NEQ 0 (
    echo 直连失败，尝试通过代理...
    curl --proxy http://127.0.0.1:7897 -sL -o "%MODEL_DIR%\config.json" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/config.json"
)
if not exist "%MODEL_DIR%\config.json" (
    echo 下载失败！请手动下载模型文件。
    echo 下载地址: https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/tree/main
    echo 将文件放入: %MODEL_DIR%
    exit /b 1
)
echo 配置文件下载完成

echo [2/3] 下载 tokenizer 文件...
curl --noproxy * -sL -o "%MODEL_DIR%\tokenizer.json" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/tokenizer.json"
if %ERRORLEVEL% NEQ 0 (
    curl --proxy http://127.0.0.1:7897 -sL -o "%MODEL_DIR%\tokenizer.json" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/tokenizer.json"
)

echo [3/3] 下载模型文件 (这步最慢，可能需要几分钟)...
curl --noproxy * -sL -o "%MODEL_DIR%\model.bin" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/model.bin"
if %ERRORLEVEL% NEQ 0 (
    echo 直连失效，尝试代理...
    curl --proxy http://127.0.0.1:7897 -sL -o "%MODEL_DIR%\model.bin" "https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/model.bin"
)
if not exist "%MODEL_DIR%\model.bin" (
    echo 模型文件下载失败！
    echo 请手动下载: https://huggingface.co/Systran/faster-whisper-%MODEL_SIZE%/resolve/main/model.bin
    echo 放入: %MODEL_DIR%\model.bin
    exit /b 1
)
echo 模型下载完成！
echo 模型路径: %MODEL_DIR%
echo.
echo 使用方式:
echo   python src/cli.py --model %MODEL_SIZE%
