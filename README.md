# 通话录音分级系统

自动将通话录音转文字，并按话术完整度分为 **初级 / 中级 / 高级**。

```
录音 MP3 → faster-whisper 转文字 → 话术匹配引擎 → 等级判定 → JSON 报告 + 控制台输出
```

## 环境要求

| 环境 | 要求 |
|------|------|
| Python | 3.10+ |
| NVIDIA GPU | 推荐 (Whisper large-v3 约需 5GB 显存) |
| CUDA Toolkit | 11.8+（如果 GPU 加速） |
| ffmpeg | 系统 PATH 中可用 |

## 快速开始

### 1. 安装依赖

```bash
# 激活虚拟环境
python -m venv venv
source venv/Scripts/activate    # Git Bash / WSL
# 或 .\venv\Scripts\activate   # Windows CMD

# 安装 Python 包
pip install -r requirements.txt

# 确保 ffmpeg 在 PATH 中
ffmpeg -version
```

### 2. 放录音

把 MP3 文件放到 `input/` 目录：

```
input/
├── call_20250601_001.mp3
├── call_20250601_002.mp3
└── ...
```

### 3. 运行

```bash
# 处理 input/ 下所有录音（默认 large-v3 模型，GPU 加速）
python src/cli.py

# 处理单个文件
python src/cli.py -i input/call.mp3

# 用小模型（更快、省显存，适合测试）
python src/cli.py --model base

# 只用 CPU
python src/cli.py --device cpu

# 英文录音
python src/cli.py --language en

# 详细日志
python src/cli.py -v
```

### 4. 查看结果

```
📞 call_20250601_001.mp3 (5分45秒)
   等级: 🟡 中级 (55%)
   完成步骤: 5/10
   缺失关键词: 价格异议处理、跟进邀约
```

详细结果 JSON 输出到 `output/` 目录，文字稿 JSON 输出到 `transcripts/` 目录。

## 配置话术脚本

默认使用内置的通用话术步骤（开场白、需求挖掘、产品介绍、异议处理、促成邀约）。

**自定义话术脚本：** 编辑 `src/analyzer.py` 中的 `FALLBACK_STEPS`，或传入自定义 `Script` 对象：

```python
from src.models import Script, ScriptStep
from src.analyzer import RuleAnalyzer

my_script = Script(
    name="销售话术V2",
    steps=[
        ScriptStep("第一步", "...", primary_keywords=[...], ...),
        ...
    ]
)
analyzer = RuleAnalyzer(script=my_script)
```

后续会支持从 YAML/JSON 配置文件加载话术脚本。

## 架构

```
src/
├── cli.py       # CLI 入口 (argparse)
├── stt.py       # faster-whisper 封装（语音转文字）
├── analyzer.py  # 文本分析引擎（策略模式，可替换为 LLM）
└── models.py    # 数据模型
```

文本分析引擎使用**策略模式**：

- **`RuleAnalyzer`**（第一期）— 关键词/步骤匹配
- **`LLMAnalyzer`**（预留）— 后续接入 LLM，接口已对齐

两者实现相同的 `Analyzer` 抽象类，在 `cli.py` 中替换一行即可切换。

## 输出

控制台彩色摘要 + `output/<文件名>_result.json`：

```json
{
  "file": "call.mp3",
  "duration": 345,
  "level": "intermediate",
  "score": 0.55,
  "details": {
    "total_steps": 10,
    "completed_steps": 5,
    "step_results": [...],
    "missing_keywords": [...]
  }
}
```
