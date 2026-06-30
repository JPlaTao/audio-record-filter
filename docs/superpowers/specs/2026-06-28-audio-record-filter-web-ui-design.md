# 通话录音分级系统 Web UI 设计

> 状态: 已完成（已演进为 Vite + Vue 3 SFC 项目）
> 类型: 功能设计文档

## 1. 概述

在现有 CLI 基础上添加本地 Web UI，使业务方（销售主管）能在 Windows 浏览器中：
1. 批量处理录音 → 转文字 + 分级
2. 编辑/确认每条录音的摘要信息
3. 勾选后导出为 ZIP 包（文件名含摘要信息，方便微信转发）

**核心理念：** 简单实用工具，不是大系统。只做三件事：录音→文字、分析评级、规范命名打包。

## 2. 技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 后端框架 | **FastAPI** | Python 异步、自动文档、复用现有 `src/` 代码 |
| 前端 | **Vue 3 + Vite SFC**（演进后） | 最初用 CDN importmap，2026-06-30 重构为 Vite + Vue 3 SFC + Vue Router，支持多页面、组件化、按需加载 |
| 打包 | **Python zipfile** | 标准库，无额外依赖 |
| 样式 | **简单 CSS**（不引入 UI 框架） | UI 简陋是刻意的，不为 3 页页面引入重型框架 |

## 3. 架构

```
src/web/
├── app.py                  # FastAPI 入口，启动 Web 服务
├── static/
│   └── index.html          # 单页面 SPA（Vue 3 CDN）
└── routes/
    ├── scan.py             # 扫描 input/ 目录
    ├── process.py          # 调用 stt + analyzer，异步处理
    └── export.py           # 生成 ZIP 包下载
```

流程：

```
Browser                    FastAPI                      src/
  │                          │                           │
  │  POST /scan              │                           │
  │ ─────────────────────→   │── 扫描 input/ 目录 ──→    │
  │  ←── 录音列表 ────────── │                           │
  │                          │                           │
  │  POST /process           │                           │
  │ ─────────────────────→   │── stt.transcribe() ───→   │
  │  ←── 流式进度 SSE ────── │── analyzer.analyze() ─→   │
  │                          │                           │
  │  PUT /records/{id}       │  ← 更新摘要字段           │
  │  POST /export            │── zipfile 打包 ───→       │
  │  ←── ZIP 文件下载 ────── │                           │
```

## 4. 可配置摘要字段

**设计原则：** 不加死字段，全部从配置读取。

```yaml
# config/summary_fields.yaml
fields:
  - key: name
    label: 姓名
    type: text
    extract_from: filename    # 从文件名自动提取（_ 前内容）
    required: true
    filename_order: 1          # ZIP 文件名中排第几位

  - key: status
    label: 状态
    type: enum
    options: [在职, 离职, 待业, 未识别]
    extract_from: analysis     # 从分析结果推断
    filename_order: 2

  - key: intention
    label: 意向
    type: enum
    options: [高, 中, 低, 未识别]
    extract_from: analysis
    filename_order: 3

  - key: school
    label: 学历
    type: enum
    options: [全日制本科, 非全日制本科, 大专, 硕士, 未识别]
    extract_from: analysis
    filename_order: 4
```

- **新增字段：** 在配置里加一条即可，UI 和 ZIP 文件名自动生效
- **删除字段：** 从配置删掉即可
- **排序：** `filename_order` 控制 ZIP 文件名中字段顺序
- **自动提取：** 第一期 `extract_from: analysis` 字段先用"未识别"占位，后续细化 LLM 提取提示词

## 5. 页面布局

单页面 SPA，上/下分两屏：

### 上半屏：批处理与控制区

```
┌──────────────────────────────────────────────┐
│  📁 input/ 目录  3 条录音待处理               │
│  [📥 扫描] [▶ 批量处理]   ████████░░ 70%     │
│                                              │
│  文件名               │ 时长   │ 状态         │
│  ─────────────────────┼────────┼─────────     │
│  张三_20250628.mp3    │ 5:12   │ ✅ 已完成     │
│  李四_20250630.mp3    │ 8:03   │ 🔄 转写中... │
│  王五_20260701.mp3    │ 3:45   │ ⏳ 排队中     │
└──────────────────────────────────────────────┘
```

- 扫描按钮：列出 input/ 下所有音频文件（排除已处理的）
- 批量处理：逐个串行处理，SSE 推送进度到前端
- 每完成一条，该行状态实时更新

### 下半屏：结果编辑区

```
┌──────────────────────────────────────────────┐
│ ☐ 全选  [📦 导出选中 (3/5)]  搜索: [_____]  │
│                                              │
│ ☑ 张三.mp3 🟢初级                            │
│   姓名: [张三 ✓]  状态: [在职 ▼]  意向: [高 ▼]│
│   学历: [全日制本科 ▼]                        │
│   [查看详情] [📄 文字稿]                     │
│                                              │
│ ☑ 李四.mp3 🟡中级                            │
│   姓名: [李四 ✓]  状态: [离职 ▼]  意向: [中 ▼]│
│   ...                                        │
│                                              │
│ ☐ 王五.mp3 🟢初级 (⚠️ 姓名未识别，请填写)      │
│   姓名: [_________] ⚠️                        │
│   ...                                        │
└──────────────────────────────────────────────┘
```

- 每个字段直接 **inline 编辑**（select 或 input）
- 姓名未识别的行黄色高亮，引导补填
- "查看详情"弹出简单 Modal 展示步骤拆解
- 搜索框支持按文件名/姓名搜索

### 详情弹窗（Modal）

```
┌─────────────────────────────────┐
│  📊 张三.mp3 分析详情       [✕] │
│                                 │
│  等级: 🟢 初级 (42%)            │
│  LLM 理由: 话术流程完成但...    │
│                                 │
│  完成步骤: 7/12                  │
│  ✅ ①开场介绍身份              │
│  ✅ ①确认接听状态              │
│  ❌ ①核实学历城市 — 未提及学信网│
│  ...                           │
│                                 │
│  📄 完整文字稿:                 │
│  ┌───────────────────────────┐ │
│  │ 你好，我是深圳沃林公司的... │ │
│  │ 请问你现在方便接电话吗...   │ │
│  └───────────────────────────┘ │
│  [📋 复制文字稿]               │
└─────────────────────────────────┘
```

### ZIP 导出

- 服务端生成 ZIP，流式返回下载
- ZIP 文件名：`{姓名}_{状态}_{意向}_{学历}.zip`（按配置顺序拼接）
- ZIP 内容：录音 MP3 + 文字稿 `.txt` + 分析结果 `.json`
- 未识别字段用 `未知` 占位

## 6. 后端 API 设计

### `POST /api/scan`
扫描 input/ 目录，返回文件列表及处理状态

```json
{
  "files": [
    {"name": "张三_20250628.mp3", "path": "input/...", "size": 5242880, "duration": 312, "status": "pending"}
  ]
}
```

### `POST /api/process` (SSE)
批量触发处理，通过 Server-Sent Events 推送每条录音的进度

```
event: progress
data: {"file": "张三_20250628.mp3", "stage": "transcribing", "progress": 0.5}

event: done
data: {"file": "张三_20250628.mp3", "level": "beginner", "score": 0.42, "summary": {...}}

event: error
data: {"file": "王五_20260701.mp3", "error": "转写失败"}
```

### `GET /api/records`
获取已处理的记录列表（支持搜索/筛选）

### `PUT /api/records/{id}`
更新单条记录的摘要字段（用户手动编辑）

### `POST /api/export`
生成 ZIP 包并返回下载

```json
{
  "record_ids": ["uuid1", "uuid2"],
  "zip_name": "张三_在职_高意向_全日制本科.zip"
}
```

## 7. 文件与项目结构变动

```
E:\1.Projects\audio_record_filter\
├── src/
│   ├── cli.py              # 不变
│   ├── stt.py              # 不变
│   ├── analyzer.py         # 不变
│   ├── models.py           # 不变
│   ├── __init__.py
│   ├── __main__.py
│   └── web/                # 🆕
│       ├── __init__.py
│       ├── app.py           # FastAPI 入口
│       ├── config.py        # 读取配置 + 摘要字段定义
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── scan.py
│       │   ├── process.py
│       │   └── export.py
│       └── static/
│           └── index.html   # Vue 3 SPA
├── config/                  # 🆕
│   └── summary_fields.yaml  # 摘要字段配置
├── output/                  # 保持原有输出目录
└── bad_cases/               # 已有
```

## 8. 迭代空间

- **前端进化路径：** Vue 3 CDN (零构建) → 提取为 `.vue` 单文件 + Vite（如果 UI 变复杂）
- **字段配置进化：** YAML 配置 → 加 DB 字段管理（如果字段变成动态管理）
- **异步处理进化：** SSE 进度推送 → Celery/Task Queue（如果文件量大到卡后端）
- **整体进化：** 本地 FastAPI → 加 Nginx 反代变成局域网服务（如果要多人共用）

每一步都不需要重写，而是渐进增强。

## 9. 当前不做

明确不做的事情（避免 scope creep）：

- ❌ 用户登录/权限系统（单人本地工具）
- ❌ 数据库（现在就是读文件 + 写文件，不需要 DB）
- ❌ 录音下载/回放功能（只有文件管理）
- ❌ 统计看板（第二期再说）
- ❌ 精致 UI 设计（要保持简陋，刻意的）

## 实现记录

### 2026-06-28
- 初始版本：Vue 3 CDN + FastAPI SSE，单文件 index.html
- 功能：扫描目录、SSE 批量处理、摘要字段编辑、ZIP 导出

### 2026-06-29
- 添加复选框选择 + 全选未处理 + 重新识别按钮
- AMR 格式支持
- 详情弹窗展示 LLM 推理内容

### 2026-06-30 — 前端重构（档案室风格）
- 从 Vue 3 CDN 重构为 Vite + Vue 3 SFC + Vue Router 项目
- 项目结构：`src/web/frontend/` 作为 Vite 根，build 输出到 `src/web/static/`
- 设计系统：暖亮"档案室"风格（Instrument Serif + Spectral + Karla 字体）
- 火漆徽章等级标签（TagBadge 组件）
- 组件拆分：AppHeader、ScanToolbar、SearchInput、RecordCard、SummaryChip、ExportBar、ProgressBar
- 状态管理：useRecords composable（响应式 CRUD）
- 路由：Dashboard（首页） + RecordDetail（详情页），预留 /settings、/trends
- SPA fallback：程序化 catch-all 替代 StaticFiles 挂载，支持 Vue Router History 模式
- FastAPI 后端零改动，API 层兼容现有接口
- 适配 13 寸笔记本屏幕，详情页在窄屏自动折叠为上下布局
