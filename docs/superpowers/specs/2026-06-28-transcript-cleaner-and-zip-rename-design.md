# 文字稿整理 + ZIP 文件重命名设计

## 1. 概述

在现有 Web UI 基础上增加两个功能：
1. **ZIP 导出时重命名内部文件** — 音频和文字稿文件名改为 ZIP 包名（含摘要信息）
2. **LLM 文字稿整理** — 用 DeepSeek 对 raw 转写文本做说话人分离（顾问/学员）、去语气词、修正错别字

## 2. ZIP 文件重命名

**改动位置：** `src/web/app.py` → `export_zip()` 路由

**逻辑：** ZIP 包内文件的 basename 改为和 ZIP 包名一致（去掉 `.zip`）

```
张三_在职_高意向_全日制本科.zip
├── 张三_在职_高意向_全日制本科.m4a
├── 张三_在职_高意向_全日制本科.txt
└── 张三_在职_高意向_全日制本科_result.json
```

不改磁盘上的原始文件，只在 `ZipFile.write()` / `writestr()` 时指定 `arcname`。

## 3. LLM 文字稿整理

### 架构

新增 `src/transcript_cleaner.py`，调用 DeepSeek API 完成说话人分离和文字整理。

### 位置

```python
# 在 _transcribe_and_analyze() 中的流程：
transcribe() → 保存 raw.txt → LLM 整理 → 覆盖保存 clean.txt → analyze(raw_text)
```

- `raw.txt` 不再对外暴露，UI 和 ZIP 导出的都是 clean 版本
- `analyze()` 仍然用 raw text，不影响关键词匹配

### 接口

```python
@dataclass
class CleanResult:
    text: str            # 整理后的全文（顾问:/学员: 标记）
    speaker_count: int   # 检测到的说话人数


def clean_transcript(
    segments: list[dict],
    transcript: str,
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> CleanResult:
```

### Prompt

系统提示词：
```
你是一位通话录音整理专家。请对以下销售顾问与学员的通话录音转写文本进行整理。

要求：
1. 说话人分离 - 每句话前标注「顾问:」或「学员:」
   - 顾问：提问、介绍、促成的人
   - 学员：回答提问、提出疑问的人

2. 文字清理：
   - 去掉"嗯"、"啊"、"那个"等不影响语义的语气词和口头禅
   - 修正 Whisper 转写错误（根据上下文语义纠正谐音字/错别字）
   - 合并同一人的连续短句
   - 中英文标点规范化

3. 输出格式（纯文本，不要 JSON 或 markdown 标记）：
   顾问: 你好，请问是张三吗？
   学员: 是的，我是。
   顾问: 我这边是深圳沃林公司的...
```

用户提示词：传入 segments 拼成的带时间戳文本。

### 清理时机

清理失败（API 不可用、返回格式错误）不阻塞流程：
- 清理成功 → 保存 clean.txt
- 清理失败 → 保持原来的 raw.txt 不变，日志记录错误

## 4. 不做的范围

- ❌ 引入额外说话人分离模型（完全依赖 LLM 推断）
- ❌ 分析逻辑改用 clean text（规则分析仍用 raw text）
- ❌ 前端展示原始/清理文本切换（第一期不需要）

## 实现记录

### 2026-06-28
- **Task 1: ZIP 文件重命名** — 修改 `src/web/app.py` `export_zip()`，将 arcname 改为 `{zip_base}{ext}`
- **Task 2: transcript_cleaner.py** — 新增 `src/transcript_cleaner.py`，调用 DeepSeek 做说话人分离+文字整理
- **Task 3: 接入处理管线** — 在 `_transcribe_and_analyze()` 中转写完成后调用 `clean_transcript()`，成功则保存 clean.txt，失败回落 raw text
- 分析逻辑不受影响，仍使用 raw text 做关键词匹配

