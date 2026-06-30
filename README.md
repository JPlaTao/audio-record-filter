# 通话录音分级系统 (Audio Record Filter)

自动将通话录音（MP3/AMR/M4A）转文字，通过三层管线智能分级为 **新手 / 中级 / 高级**，并提供 Web UI 方便业务人员使用。

> 🏛️ 档案室风格 Web UI · 三维评级 · 质量信号 · LLM 辅助

---

## 功能

| 功能 | 说明 |
|------|------|
| 🎤 **语音转文字** | faster-whisper large-v3，GPU/CUDA 加速 |
| 📊 **三级评级** | 覆盖度 → 质量信号 → LLM 综合判定 |
| 🧪 **7 个质量信号** | 学员发言占比、追问密度、话题一致性、话轮数…… |
| 🧠 **LLM 辅助** | DeepSeek 做说话人分离、文字稿整理、摘要提取、综合评级 |
| 🌐 **Web UI** | Vue 3 SPA — 档案室风格，批量处理 + 详情查看 + 编辑导出 |
| 📦 **智能导出** | ZIP 打包，文件名自动拼接摘要字段（姓名_状态_意向_学历） |
| 📋 **可配字段** | YAML 配置摘要字段，UI 和 ZIP 命名自动生效 |
| 🔌 **CLI 模式** | 无头运行，适合服务器批量处理 |

## 评级体系

核心理念：**评级不是"这通电话打得好不好"，而是"这条录音适合什么阶段的顾问听来学习"。**

```
┌─────────────────────────────────────────────────┐
│               三层评级管线                         │
│                                                   │
│  通话录音 → ① 话术覆盖度打分                      │
│           → ② 7 项质量信号评分                    │
│           → ③ LLM 综合判决（含 2D 矩阵 + Bad Case）│
│           → 新手 / 中级 / 高级                     │
└─────────────────────────────────────────────────┘
```

详见 [docs/录音等级判断标准.md](docs/录音等级判断标准.md)。

---

## 快速开始

### 环境要求

- Python 3.10+
- NVIDIA GPU（推荐，large-v3 约需 5GB 显存）
- CUDA Toolkit 11.8+（GPU 加速时）
- ffmpeg（系统 PATH 中可用）
- DeepSeek API Key（[免费注册](https://platform.deepseek.com/)）

### 1. 克隆

```bash
git clone https://github.com/JPlaTao/audio-record-filter.git
cd audio-record-filter
```

### 2. 配置 API 密钥

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

### 3. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# Windows (Git Bash / WSL)
source venv/Scripts/activate
# Windows (CMD)
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# 安装 Python 包
pip install -r requirements.txt

# 验证 ffmpeg
ffmpeg -version
```

> **首次运行会自动下载 Whisper large-v3 模型（约 3GB）**。网络不畅时：
> - 设置代理后再启动：`export https_proxy=http://127.0.0.1:7897`
> - 或先用小模型体验：`python -m src --model base`（~300MB，下载更快）
> - 或用脚本手动下载：`scripts\download_model.bat`（Windows）

### 4. 放录音

把音频文件放到 `input/` 目录（支持 `.mp3` `.wav` `.m4a` `.ogg` `.flac` `.amr`）：

```
input/
├── 张三_20250628.mp3
├── 李四_20250630.m4a
└── ...
```

### 5. 启动 Web UI

```bash
# Windows
scripts\run_web.bat

# Linux / macOS
bash scripts/run_web.sh

# 或直接
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080
```

浏览器打开 **http://localhost:8080**

### 6. 或者使用 CLI

```bash
# 处理 input/ 下所有录音
python -m src

# 处理单个文件
python -m src -i input/call.mp3

# 用小模型（更快、省显存）
python -m src --model base

# 只用 CPU
python -m src --device cpu
```

---

## Web UI 使用指南

### 首页（Dashboard）

```
┌─────────────────────────────────────────────────────┐
│  📁 录音档案 v0.3     [首页] [趋势] [设置]           │
├─────────────────────────────────────────────────────┤
│  [📥 扫描] [▶ 处理选中] [☐ 全选] [🗑 清除]         │
│  ████████████░░░░ 75%                               │
│                                                     │
│  ☐ 张三.mp3    🟢 初级   姓名: [张三]  状态:[在职 ▼]│
│  ☑ 李四.m4a    🟡 中级   姓名: [李四]  状态:[离职 ▼]│
│                                                     │
│  已选 1 条                              [📦 导出]   │
└─────────────────────────────────────────────────────┘
```

- **扫描** — 列出 `input/` 下所有音频文件
- **处理选中** — 勾选后批量处理，SSE 实时推送进度
- **编辑** — 每个摘要字段可直接 inline 修改
- **导出** — ZIP 打包，文件名含摘要信息

### 详情页（RecordDetail）

点击录音条目进入详情页，可查看：
- 等级火漆徽章 + LLM 评级理由
- 左侧：说话人分离后的文字稿
- 右侧：LLM 推理过程、质量信号评分、规则分析详情

---

## 项目结构

```
audio_record_filter/
├── input/                     # 放入录音文件
├── output/                    # 分析结果 JSON
├── transcripts/               # 文字稿 JSON
├── config/
│   └── summary_fields.yaml    # 摘要字段配置
├── docs/
│   ├── 录音等级判断标准.md     # 评级"宪法"（编辑此文件 = 编辑 LLM 行为）
│   └── superpowers/           # 设计文档与计划
├── scripts/
│   ├── run.bat / run.sh       # CLI 启动脚本
│   ├── run_web.bat / run_web.sh  # Web UI 启动脚本
│   └── download_model.bat     # Whisper 模型下载工具
├── src/
│   ├── cli.py                 # CLI 入口
│   ├── stt.py                 # faster-whisper 封装
│   ├── analyzer.py            # RuleAnalyzer + LLMAnalyzer（策略模式）
│   ├── quality_scorer.py      # 质量信号评分模块
│   ├── transcript_cleaner.py  # LLM 说话人分离 + 文字稿整理
│   ├── summary_extractor.py   # LLM 摘要字段提取
│   ├── models.py              # 数据模型
│   └── web/
│       ├── app.py             # FastAPI 入口
│       ├── config.py          # 配置加载
│       └── frontend/          # Vue 3 前端源码
├── .env.example               # 环境变量模板
├── .env                       # API 密钥（已 gitignore）
├── requirements.txt
└── README.md
```

---

## 自定义配置

### 摘要字段

编辑 `config/summary_fields.yaml`：

```yaml
fields:
  - key: name
    label: 姓名
    type: text
    extract_from: filename      # 从文件名自动提取
    required: true
    filename_order: 1            # ZIP 文件名中排第几位

  - key: status
    label: 状态
    type: enum
    options: [在职, 离职, 待业, 未识别]
    extract_from: analysis       # LLM 从对话中提取
    filename_order: 2
```

新增/删除/排序字段只需修改此文件，UI 和 ZIP 命名自动生效。

### 评级标准

编辑 `docs/录音等级判断标准.md`：

- 修改 2D 矩阵的阈值（覆盖度 × 质量分）
- 调整质量信号权重
- 添加 Bad Case 示例

此文件同时作为 LLM 的 system prompt 来源。

---

## 前端开发（可选）

如果你需要修改 Web UI：

```bash
cd src/web/frontend
pnpm install       # 需要 Node.js + pnpm
pnpm dev           # Vite 开发服务器（端口 5173）
pnpm build         # 构建到 ../static/
```

后端 FastAPI 已配置代理，`pnpm dev` 下的 `/api` 请求会自动转发到 `localhost:8080`。

---

## 技术栈

| 领域 | 技术 |
|------|------|
| STT | faster-whisper (large-v3, CTranslate2) |
| 分析引擎 | RuleAnalyzer（规则）+ LLMAnalyzer（DeepSeek） |
| 质量信号 | 7 项可配置指标，加权评分 |
| 后端 | FastAPI + uvicorn |
| 前端 | Vue 3 + Vite + Vue Router |
| 设计 | 手写 CSS（档案室风格） |
| 配置 | YAML + .env |

---

## License

[MIT](LICENSE)
