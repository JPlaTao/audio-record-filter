# Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a local Web UI (FastAPI + Vue 3 CDN) on top of the existing CLI pipeline.

**Architecture:** FastAPI serves a single-page Vue 3 app. The backend wraps existing `stt.py` / `analyzer.py`, exposes SSE for batch processing progress, and generates ZIP exports. Summary fields are YAML-configurable, not hardcoded.

**Tech Stack:** FastAPI 0.121+, uvicorn 0.34+, PyYAML 6.0+, Vue 3 (CDN importmap), Python 3.13

**Global Constraints:**
- All existing `src/` modules (`stt.py`, `analyzer.py`, `models.py`, `cli.py`) must remain untouched
- Frontend: zero build tools, zero npm, pure `<script type="importmap">` Vue 3
- Summary fields driven by YAML config — not hardcoded in Python or HTML
- ZIP file name auto-generated from summary field values
- SSE for real-time batch progress

---

### Task 1: Config module + summary fields YAML

**Files:**
- Create: `config/summary_fields.yaml`
- Create: `src/web/config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `load_summary_fields() -> list[SummaryField]` — all later tasks call this

- [ ] **Step 1: Create `config/summary_fields.yaml`**

```yaml
# 摘要字段配置 — 修改此文件即可增减字段，UI 和 ZIP 命名自动生效
fields:
  - key: name
    label: 姓名
    type: text
    extract_from: filename
    required: true
    filename_order: 1

  - key: status
    label: 状态
    type: enum
    options: [在职, 离职, 待业, 未识别]
    extract_from: analysis
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

- [ ] **Step 2: Create `src/web/__init__.py`**

```python
"""Web UI module for audio record filter."""
```

- [ ] **Step 3: Create `src/web/config.py`**

```python
"""Load config from config/summary_fields.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = HERE / "config" / "summary_fields.yaml"


class SummaryField:
    """A single configurable summary field."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.key: str = data["key"]
        self.label: str = data["label"]
        self.type: str = data.get("type", "text")
        self.options: list[str] = data.get("options", [])
        self.extract_from: str = data.get("extract_from", "")
        self.required: bool = data.get("required", False)
        self.filename_order: int = data.get("filename_order", 99)


def load_summary_fields(path: str | Path | None = None) -> list[SummaryField]:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [SummaryField(item) for item in raw.get("fields", [])]


def build_zip_filename(
    records: list[dict[str, str]],
    fields: list[SummaryField],
    separator: str = "_",
) -> str:
    """Build a ZIP filename by joining ordered field values.

    `records` is a list of per-record summary dicts.  Returns individual
    filenames joined with '+'.
    """
    filenames: list[str] = []
    sorted_fields = sorted(fields, key=lambda f: f.filename_order)
    for rec in records:
        parts: list[str] = []
        for f in sorted_fields:
            val = rec.get(f.key, "未知").strip()
            if not val or val == "未识别":
                val = "未知"
            parts.append(val)
        filenames.append(separator.join(parts))
    return "+".join(filenames)
```

- [ ] **Step 4: Verify it loads correctly**

Run: `cd E:\1.Projects\audio_record_filter && python -c "from src.web.config import load_summary_fields; fields = load_summary_fields(); print([(f.key, f.label) for f in fields])"`

Expected: `[('name', '姓名'), ('status', '状态'), ('intention', '意向'), ('school', '学历')]`

- [ ] **Step 5: Commit**

```bash
git add config/summary_fields.yaml src/web/
git commit -m "feat: add configurable summary fields module"
```

---

### Task 2: FastAPI app with all routes

**Files:**
- Create: `src/web/app.py` (FastAPI app + routes, SSE, ZIP export)

**Interfaces:**
- Consumes: `load_summary_fields()` from Task 1, existing `stt.py`/`analyzer.py`/`models.py`
- Produces: HTTP API at `http://localhost:8080`

- [ ] **Step 1: Create `src/web/app.py`**

```python
"""FastAPI web app for the audio record filter system.

Usage:
    python -m src.web.app
    # or
    uvicorn src.web.app:app --port 8080
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Allow running as `python src/web/app.py`
if __name__ == "__main__" and __package__ is None:
    __package__ = "src.web"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analyzer import LLMAnalyzer, RuleAnalyzer  # noqa: E402
from src.models import Level  # noqa: E402
from src.stt import STTEngine  # noqa: E402
from src.web.config import (  # noqa: E402
    SummaryField,
    build_zip_filename,
    load_summary_fields,
)

logger = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = HERE / "input"
TRANSCRIPT_DIR = HERE / "transcripts"
OUTPUT_DIR = HERE / "output"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

# ── In-memory "DB" ──────────────────────────────────────────────────────

RECORDS: dict[str, dict] = {}  # id -> record dict
SUMMARY_FIELDS: list[SummaryField] = []

# ── Shared engine instances (reused across requests) ────────────────────

_stt: STTEngine | None = None
_analyzer: RuleAnalyzer | None = None


def get_stt() -> STTEngine:
    global _stt
    if _stt is None:
        _stt = STTEngine(model_size="large-v3", device="auto")
    return _stt


def get_analyzer() -> RuleAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RuleAnalyzer()
    return _analyzer


# ── API models ──────────────────────────────────────────────────────────


class ScanResponse(BaseModel):
    files: list[dict]


class RecordUpdate(BaseModel):
    summary: dict[str, str]


class ExportRequest(BaseModel):
    record_ids: list[str]


# ── Helpers ─────────────────────────────────────────────────────────────


def _auto_extract_summary(filename: str) -> dict[str, str]:
    """Auto-populate summary fields from filename + analysis (placeholder)."""
    result: dict[str, str] = {}
    stem = Path(filename).stem  # "张三_20250628" from "张三_20250628.mp3"
    for f in SUMMARY_FIELDS:
        if f.extract_from == "filename":
            # Take everything before first "_"
            val = stem.split("_")[0] if "_" in stem else stem
            result[f.key] = val
        else:
            result[f.key] = "未识别"
    return result


def _load_existing_results() -> dict[str, dict]:
    """Load previously-processed results from output/ into RECORDS."""
    records: dict[str, dict] = {}
    if not OUTPUT_DIR.exists():
        return records
    for f in sorted(OUTPUT_DIR.glob("*_result.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, data["file"]))
            summary = _auto_extract_summary(data["file"])
            # Try to read transcript preview from the txt file
            txt_path = TRANSCRIPT_DIR / f"{f.stem.replace('_result', '')}.txt"
            transcript_preview = ""
            if txt_path.exists():
                transcript_preview = txt_path.read_text(encoding="utf-8")[:200]
            records[rid] = {
                "id": rid,
                "file": data["file"],
                "duration": data.get("duration", 0),
                "level": data.get("level", "beginner"),
                "score": data.get("score", 0),
                "summary": summary,
                "status": "completed",
                "transcript": transcript_preview,
                "details": data.get("details", {}),
            }
        except Exception:
            continue
    return records


def _cleanup_tempdir(tmpdir: str) -> None:
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


# ── FastAPI app ─────────────────────────────────────────────────────────

app = FastAPI(title="通话录音分级系统", version="0.2.0")

# Mount static files (Vue SPA)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


@app.on_event("startup")
async def startup() -> None:
    global SUMMARY_FIELDS, RECORDS
    SUMMARY_FIELDS = load_summary_fields()
    RECORDS = _load_existing_results()
    logger.info("已加载 %d 条历史记录，%d 个摘要字段", len(RECORDS), len(SUMMARY_FIELDS))


# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/api/fields")
async def get_fields() -> list[dict]:
    """Return configured summary fields for UI rendering."""
    return [
        {
            "key": f.key,
            "label": f.label,
            "type": f.type,
            "options": f.options,
            "required": f.required,
            "filename_order": f.filename_order,
        }
        for f in SUMMARY_FIELDS
    ]


@app.post("/api/scan")
async def scan_input() -> ScanResponse:
    """Scan input/ directory for audio files."""
    files: list[dict] = []
    if not INPUT_DIR.exists():
        return ScanResponse(files=[])

    for p in sorted(INPUT_DIR.iterdir()):
        if p.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        # Check if already processed
        existing = None
        for rid, rec in RECORDS.items():
            if rec["file"] == p.name:
                existing = rec
                break
        files.append(
            {
                "name": p.name,
                "size": p.stat().st_size,
                "status": existing["status"] if existing else "pending",
                "record_id": rid if existing else None,
            }
        )
    return ScanResponse(files=files)


@app.get("/api/process")
async def process_files() -> StreamingResponse:
    """Batch-process all pending files via SSE.

    ⚠️ GET method required — EventSource only supports GET.
    """
    """Batch-process all pending files via SSE.

    Yields progress events per file, then a final 'complete' event.
    """
    return StreamingResponse(
        _process_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _process_generator() -> AsyncGenerator[str, None]:
    stt = get_stt()
    analyzer = get_analyzer()

    pending = [
        p
        for p in sorted(INPUT_DIR.iterdir())
        if p.suffix.lower() in AUDIO_EXTENSIONS
        and not any(
            rec["file"] == p.name and rec["status"] == "completed"
            for rec in RECORDS.values()
        )
    ]

    if not pending:
        yield "event: complete\ndata: {}\n\n"
        return

    for audio_path in pending:
        yield f"event: progress\ndata: {json.dumps({'file': audio_path.name, 'stage': 'transcribing', 'progress': 0.3}, ensure_ascii=False)}\n\n"

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda p=audio_path: _transcribe_and_analyze(p, stt, analyzer)
            )

            rid = str(uuid.uuid4())
            summary = _auto_extract_summary(audio_path.name)
            RECORDS[rid] = {
                "id": rid,
                "file": audio_path.name,
                "duration": result["duration"],
                "level": result["level"],
                "score": result["score"],
                "summary": summary,
                "status": "completed",
                "transcript": result.get("transcript_preview", ""),
                "details": result.get("details", {}),
            }

            yield f"event: done\ndata: {json.dumps({'file': audio_path.name, 'record_id': rid, 'level': result['level'], 'score': result['score']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception("处理 %s 失败", audio_path.name)
            yield f"event: error\ndata: {json.dumps({'file': audio_path.name, 'error': str(e)}, ensure_ascii=False)}\n\n"

    yield "event: complete\ndata: {}\n\n"


def _transcribe_and_analyze(
    audio_path: Path, stt: STTEngine, analyzer: RuleAnalyzer
) -> dict:
    """Run STT + analysis synchronously (called in thread pool)."""
    from src.web.config import HERE as CFG_HERE

    tr = stt.transcribe(str(audio_path), language="zh")
    analysis = analyzer.analyze(tr.text)

    # Save transcript
    transcript_dir = CFG_HERE / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / f"{audio_path.stem}.txt"
    transcript_path.write_text(tr.text, encoding="utf-8")

    # Save analysis result
    output_dir = CFG_HERE / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{audio_path.stem}_result.json"
    output_path.write_text(
        json.dumps(
            {
                "file": audio_path.name,
                "duration": tr.duration,
                "level": analysis.level.value,
                "score": analysis.score,
                "details": {
                    "total_steps": analysis.total_steps,
                    "completed_steps": analysis.completed_steps,
                    "step_results": [
                        {
                            "step_name": sr.step_name,
                            "matched": sr.matched,
                            "score": sr.score,
                        }
                        for sr in analysis.step_results
                    ],
                    "reasoning": analysis.reasoning,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "duration": tr.duration,
        "level": analysis.level.value,
        "score": analysis.score,
        "transcript_preview": tr.text[:200],
        "details": {
            "total_steps": analysis.total_steps,
            "completed_steps": analysis.completed_steps,
            "reasoning": analysis.reasoning,
        },
    }


@app.get("/api/records")
async def get_records(search: str = "") -> list[dict]:
    """Return all processed records, optionally filtered by search."""
    results = list(RECORDS.values())
    results.sort(key=lambda r: r["file"])
    if search:
        search_lower = search.lower()
        results = [
            r
            for r in results
            if search_lower in r["file"].lower()
            or search_lower in r.get("summary", {}).get("name", "").lower()
        ]
    return results


@app.get("/api/records/{record_id}")
async def get_record_detail(record_id: str) -> dict:
    """Return full details for a single record."""
    record = RECORDS.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录未找到")
    return record


@app.put("/api/records/{record_id}")
async def update_record(record_id: str, body: RecordUpdate) -> dict:
    """Update summary fields for a record."""
    record = RECORDS.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录未找到")
    record["summary"] = body.summary
    return record


@app.post("/api/export")
async def export_zip(body: ExportRequest) -> FileResponse:
    """Create a ZIP with selected records' audio + transcript + result JSON."""
    import zipfile  # noqa: PLC0415

    records_to_export = [
        RECORDS[rid] for rid in body.record_ids if rid in RECORDS
    ]
    if not records_to_export:
        raise HTTPException(status_code=400, detail="未选择有效记录")

    # Build ZIP filename
    zip_base = build_zip_filename(
        [r["summary"] for r in records_to_export], SUMMARY_FIELDS
    )

    tmpdir = tempfile.mkdtemp(prefix="audio_export_")
    zip_path = Path(tmpdir) / f"{zip_base}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in records_to_export:
            audio_file = INPUT_DIR / rec["file"]
            if audio_file.exists():
                zf.write(audio_file, rec["file"])

            # Transcript txt
            txt_path = TRANSCRIPT_DIR / f"{Path(rec['file']).stem}.txt"
            if txt_path.exists():
                zf.write(txt_path, f"{Path(rec['file']).stem}.txt")

            # Result JSON
            result_path = OUTPUT_DIR / f"{Path(rec['file']).stem}_result.json"
            if result_path.exists():
                zf.write(result_path, f"{Path(rec['file']).stem}_result.json")

    return FileResponse(
        path=str(zip_path),
        filename=f"{zip_base}.zip",
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_base}.zip"'},
        background=_cleanup_tempdir,
    )


# ── Entry ───────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    print("🎯 通话录音分级系统 Web UI")
    print(f"   打开 http://localhost:8080 使用\n")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Start the server and verify API**

Run: `cd E:\1.Projects\audio_record_filter && python -m src.web.app`

Expected: server starts on http://localhost:8080

In another terminal:
```bash
curl http://localhost:8080/api/fields
```
Expected: returns the 4 fields as JSON

- [ ] **Step 3: Commit**

```bash
git add src/web/app.py
git commit -m "feat: add FastAPI backend with scan/process/export routes"
```

---

### Task 3: Vue 3 CDN frontend (single-page SPA)

**Files:**
- Create: `src/web/static/index.html`

**Interfaces:**
- Consumes: all `/api/*` routes from Task 2
- Produces: browser UI for batch processing + editing + export

- [ ] **Step 1: Create `src/web/static/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>通话录音分级系统</title>
  <script type="importmap">
  {
    "imports": {
      "vue": "https://unpkg.com/vue@3/dist/vue.esm-browser.js"
    }
  }
  </script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; }
    .app { max-width: 1100px; margin: 0 auto; padding: 20px; }
    h1 { font-size: 22px; margin-bottom: 12px; }
    h1 small { font-size: 14px; color: #888; font-weight: normal; }

    /* Top panel */
    .panel { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    .toolbar .info { font-size: 13px; color: #666; margin-left: auto; }
    .btn { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border: 1px solid #d0d0d0; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
    .btn:hover { background: #f0f0f0; }
    .btn-primary { background: #1677ff; color: #fff; border-color: #1677ff; }
    .btn-primary:hover { background: #4096ff; }
    .btn-primary:disabled { background: #a0c4ff; border-color: #a0c4ff; cursor: not-allowed; }
    .btn-danger { color: #ff4d4f; border-color: #ff4d4f; }
    .btn-danger:hover { background: #fff2f0; }

    /* Table */
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; }
    th { font-weight: 600; color: #555; font-size: 13px; white-space: nowrap; }
    tr:hover td { background: #fafafa; }
    td select, td input { padding: 2px 6px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 13px; width: 100%; }
    td .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .tag-beginner { background: #e8f5e9; color: #2e7d32; }
    .tag-intermediate { background: #fff8e1; color: #f57f17; }
    .tag-advanced { background: #ffebee; color: #c62828; }

    /* Progress bar */
    .progress-bar { height: 4px; background: #e0e0e0; border-radius: 2px; margin: 8px 0; overflow: hidden; }
    .progress-bar .fill { height: 100%; background: #1677ff; border-radius: 2px; transition: width .3s; }
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
    .status-dot.pending { background: #bbb; }
    .status-dot.processing { background: #1677ff; animation: pulse 1s infinite; }
    .status-dot.done { background: #52c41a; }
    .status-dot.error { background: #ff4d4f; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

    .summary-grid { display: flex; gap: 8px; flex-wrap: wrap; }
    .summary-grid > * { flex: 1; min-width: 100px; }

    .link-like { color: #1677ff; cursor: pointer; font-size: 13px; }
    .link-like:hover { text-decoration: underline; }

    /* Modal overlay */
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 1000; display: flex; align-items: center; justify-content: center; }
    .modal { background: #fff; border-radius: 8px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 24px; }
    .modal h2 { font-size: 18px; margin-bottom: 12px; }
    .modal .close { float: right; cursor: pointer; font-size: 20px; color: #999; }
    .modal .close:hover { color: #333; }
    .modal .section { margin-bottom: 16px; }
    .modal .section h3 { font-size: 14px; color: #555; margin-bottom: 6px; }
    .modal .section pre { background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 13px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
  </style>
</head>
<body>
  <div id="app" class="app">
    <h1>🎯 通话录音分级 <small>input/ 目录处理工具</small></h1>

    <!-- Top panel: scan + batch -->
    <div class="panel">
      <div class="toolbar">
        <button class="btn" @click="scanDir" :disabled="scanning">📥 扫描目录</button>
        <button class="btn btn-primary" @click="batchProcess" :disabled="processing || pendingFiles.length === 0">
          ▶ 批量处理
        </button>
        <span class="info" v-if="fileList.length > 0">
          共 {{ fileList.length }} 条，待处理 {{ pendingFiles.length }} 条
        </span>
      </div>

      <div v-if="processing" class="progress-bar">
        <div class="fill" :style="{ width: progressPercent + '%' }"></div>
      </div>

      <table v-if="fileList.length > 0">
        <thead>
          <tr>
            <th>文件名</th>
            <th style="width:60px">时长</th>
            <th style="width:100px">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in fileList" :key="f.name">
            <td>{{ f.name }}</td>
            <td>{{ f.size > 0 ? '--:--' : '--:--' }}</td>
            <td>
              <span class="status-dot" :class="f.status"></span>
              {{ statusLabel(f.status) }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else style="text-align:center;padding:30px;color:#999;font-size:14px;">
        点击「扫描目录」查看 input/ 中的录音文件
      </div>
    </div>

    <!-- Bottom panel: results + export -->
    <div class="panel" v-if="records.length > 0">
      <div class="toolbar">
        <label style="font-size:14px">
          <input type="checkbox" v-model="selectAll" @change="toggleAll"> 全选
        </label>
        <button class="btn btn-primary" @click="exportZip" :disabled="selectedIds.length === 0">📦 导出 ZIP（{{ selectedIds.length }}）</button>
        <div style="flex:1"></div>
        <input type="text" v-model="searchQuery" placeholder="搜索姓名/文件名..." style="padding:4px 10px;border:1px solid #d0d0d0;border-radius:4px;font-size:13px;width:180px;">
      </div>

      <table>
        <thead>
          <tr>
            <th style="width:30px"></th>
            <th>文件名</th>
            <th style="width:70px">等级</th>
            <th v-for="field in fields" :key="field.key" style="min-width:100px">{{ field.label }}</th>
            <th style="width:80px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rec in filteredRecords" :key="rec.id" :class="{ 'warn-missing': hasMissingName(rec) }">
            <td><input type="checkbox" :value="rec.id" v-model="selectedIds"></td>
            <td>{{ rec.file }}</td>
            <td><span class="tag" :class="'tag-' + rec.level">{{ levelLabel(rec.level) }}</span></td>
            <td v-for="field in fields" :key="field.key">
              <select v-if="field.type === 'enum'" v-model="rec.summary[field.key]" @change="onUpdate(rec)">
                <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <input v-else type="text" v-model="rec.summary[field.key]" @change="onUpdate(rec)" :placeholder="field.label">
            </td>
            <td>
              <span class="link-like" @click="showDetail(rec)">详情</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="hasMissingNames" style="margin-top:8px;font-size:13px;color:#e65100;">
        ⚠️ 部分录音姓名未识别，请在表格中填写
      </div>
    </div>

    <!-- Detail modal -->
    <div class="modal-overlay" v-if="detailRecord" @click.self="detailRecord = null">
      <div class="modal">
        <span class="close" @click="detailRecord = null">&times;</span>
        <h2>📊 {{ detailRecord.file }} 分析详情</h2>

        <div class="section">
          <h3>等级判定</h3>
          <p style="font-size:16px;font-weight:600;">
            <span class="tag" :class="'tag-' + detailRecord.level">
              {{ levelLabel(detailRecord.level) }}
            </span>
            ({{ detailRecord.score }}%)
          </p>
        </div>

        <div class="section" v-if="detailRecord.details">
          <h3>步骤完成情况</h3>
          <p v-if="detailRecord.details.reasoning" style="font-size:13px;color:#555;margin-bottom:8px;">{{ detailRecord.details.reasoning }}</p>
          <p style="font-size:13px;color:#888;">{{ detailRecord.details.completed_steps }}/{{ detailRecord.details.total_steps }} 步骤完成</p>
        </div>

        <div class="section" v-if="detailRecord.transcript">
          <h3>文字稿</h3>
          <pre>{{ detailRecord.transcript }}</pre>
        </div>

        <div style="text-align:right;margin-top:12px;">
          <button class="btn" @click="detailRecord = null">关闭</button>
        </div>
      </div>
    </div>
  </div>

  <script type="module">
  import { createApp, ref, computed } from 'vue';

  const BASE = '';

  createApp({
    setup() {
      const fileList = ref([]);
      const records = ref([]);
      const fields = ref([]);
      const scanning = ref(false);
      const processing = ref(false);
      const searchQuery = ref('');
      const selectedIds = ref([]);
      const selectAll = ref(false);
      const progressPercent = ref(0);
      const detailRecord = ref(null);

      const pendingFiles = computed(() => fileList.value.filter(f => f.status === 'pending'));

      const filteredRecords = computed(() => {
        const q = searchQuery.value.toLowerCase().trim();
        if (!q) return records.value;
        return records.value.filter(r =>
          r.file.toLowerCase().includes(q) ||
          (r.summary?.name || '').toLowerCase().includes(q)
        );
      });

      const hasMissingName = (rec) => {
        const nameField = fields.value.find(f => f.key === 'name');
        if (!nameField) return false;
        const val = rec.summary?.[nameField.key];
        return !val || val === '未识别' || val === '';
      };

      const hasMissingNames = computed(() => records.value.some(hasMissingName));

      // Load fields on mount
      fetch(`${BASE}/api/fields`)
        .then(r => r.json())
        .then(data => fields.value = data);

      // Load existing records
      fetch(`${BASE}/api/records`)
        .then(r => r.json())
        .then(data => records.value = data);

      function statusLabel(s) {
        const m = { pending: '待处理', processing: '处理中', completed: '已完成', error: '失败' };
        return m[s] || s;
      }

      function levelLabel(l) {
        const m = { beginner: '初级', intermediate: '中级', advanced: '高级' };
        return m[l] || l;
      }

      async function scanDir() {
        scanning.value = true;
        try {
          const res = await fetch(`${BASE}/api/scan`, { method: 'POST' });
          const data = await res.json();
          fileList.value = data.files;
        } finally {
          scanning.value = false;
        }
      }

      async function batchProcess() {
        processing.value = true;
        progressPercent.value = 0;
        selectedIds.value = [];

        // Mark files as processing
        fileList.value.forEach(f => {
          if (f.status === 'pending') f.status = 'processing';
        });

        const es = new EventSource(`${BASE}/api/process`);
        const total = fileList.value.filter(f => f.status === 'processing' || f.status === 'completed').length;
        let done = 0;

        es.addEventListener('progress', e => {
          const data = JSON.parse(e.data);
          const f = fileList.value.find(f => f.name === data.file);
          if (f) f.status = 'processing';
        });

        es.addEventListener('done', e => {
          const data = JSON.parse(e.data);
          done++;
          progressPercent.value = Math.round((done / total) * 100);

          // Update file status
          const f = fileList.value.find(f => f.name === data.file);
          if (f) f.status = 'completed';

          // Add to records
          fetch(`${BASE}/api/records/${data.record_id}`)
            .then(r => r.json())
            .then(rec => {
              const idx = records.value.findIndex(r => r.id === rec.id);
              if (idx >= 0) records.value[idx] = rec;
              else records.value.push(rec);
            });
        });

        es.addEventListener('error', e => {
          const data = JSON.parse(e.data);
          done++;
          const f = fileList.value.find(f => f.name === data.file);
          if (f) f.status = 'error';
        });

        es.addEventListener('complete', () => {
          es.close();
          processing.value = false;
          progressPercent.value = 100;
        });
      }

      function onUpdate(rec) {
        fetch(`${BASE}/api/records/${rec.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: rec.summary }),
        });
      }

      function toggleAll() {
        if (selectAll.value) {
          selectedIds.value = filteredRecords.value.map(r => r.id);
        } else {
          selectedIds.value = [];
        }
      }

      async function exportZip() {
        if (selectedIds.value.length === 0) return;
        const res = await fetch(`${BASE}/api/export`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ record_ids: selectedIds.value }),
        });
        if (!res.ok) {
          alert('导出失败');
          return;
        }
        const blob = await res.blob();
        const disposition = res.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename="?(.+?)"?$/);
        const filename = match ? match[1] : 'export.zip';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = decodeURIComponent(filename);
        a.click();
        URL.revokeObjectURL(url);
      }

      function showDetail(rec) {
        detailRecord.value = rec;
      }

      return {
        fileList, records, fields, scanning, processing,
        searchQuery, selectedIds, selectAll, progressPercent, detailRecord,
        pendingFiles, filteredRecords, hasMissingName, hasMissingNames,
        statusLabel, levelLabel,
        scanDir, batchProcess, onUpdate, toggleAll, exportZip, showDetail,
      };
    }
  }).mount('#app');
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify the UI loads**

Restart the server: `cd E:\1.Projects\audio_record_filter && python -m src.web.app`

Open `http://localhost:8080` in browser. Expected:
- Page loads with scan button
- Click "扫描目录" → lists files in input/
- Click "批量处理" → processes with progress bar
- Results appear in bottom table with editable fields
- Edit a field → change persists (verify via page refresh)
- Select records → "导出ZIP" downloads a zip

- [ ] **Step 3: Commit**

```bash
git add src/web/static/index.html
git commit -m "feat: add Vue 3 CDN frontend with batch processing and export UI"
```

---

### Task 4: Wire up + update requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

```txt
faster-whisper>=1.1.0
pydantic>=2.0.0
openai>=1.0.0
zhconv>=1.4.3
fastapi>=0.100.0
uvicorn>=0.20.0
pyyaml>=6.0
```

- [ ] **Step 2: Create `src/__main__.py` (update if exists)**

Current content:
```python
from .cli import main

if __name__ == "__main__":
    main()
```

Replace with:
```python
"""Entry points for python -m src."""

import sys


def main() -> None:
    from .cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
```

(This ensures `python -m src --help` still works for CLI, but we also add a way to launch web)

- [ ] **Step 3: Test `python -m src.web.app` starts clean**

Run: `cd E:\1.Projects\audio_record_filter && timeout 5 python -m src.web.app 2>&1 || true`

Expected: starts uvicorn, no import errors

- [ ] **Step 4: Commit**

```bash
git add requirements.txt src/__main__.py
git commit -m "chore: add web dependencies and update entry points"
```
