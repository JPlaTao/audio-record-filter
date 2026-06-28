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
import shutil
import sys
import tempfile
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

from src.analyzer import RuleAnalyzer  # noqa: E402
from src.stt import STTEngine  # noqa: E402
from src.transcript_cleaner import clean_transcript  # noqa: E402
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
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".amr"}

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




# ── FastAPI app ─────────────────────────────────────────────────────────

app = FastAPI(title="通话录音分级系统", version="0.2.0")


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
async def process_files(files: str = "") -> StreamingResponse:
    """Batch-process audio files via SSE.

    Optional query param:
      files=file1.mp3,file2.mp3  — process only the specified files (ignore
                                    status check); supports reprocessing
      (no files)                 — process all pending files (current behavior)

    ⚠️ GET method required — EventSource only supports GET.

    Yields progress events per file, then a final 'complete' event.
    """
    return StreamingResponse(
        _process_generator(files_param=files if files else None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _process_generator(files_param: str | None = None) -> AsyncGenerator[str, None]:
    try:
        stt = get_stt()
        analyzer = get_analyzer()

        if not INPUT_DIR.exists():
            logger.error("input/ 目录不存在")
            yield f"event: error\ndata: {json.dumps({'file': '', 'error': 'input/ 目录不存在'}, ensure_ascii=False)}\n\n"
            yield "event: complete\ndata: {}\n\n"
            return

        if files_param:
            # Selective processing mode: process only specified files, clean old
            # records and output/transcript files, then re-process them.
            file_names = {name.strip() for name in files_param.split(",")}
            pending = [
                p
                for p in sorted(INPUT_DIR.iterdir())
                if p.name in file_names and p.suffix.lower() in AUDIO_EXTENSIONS
            ]
            # Clean old RECORDS entries for the specified files
            for rid, rec in list(RECORDS.items()):
                if rec["file"] in file_names:
                    del RECORDS[rid]
            # Clean old output/transcript files
            for p in pending:
                result_path = OUTPUT_DIR / f"{p.stem}_result.json"
                if result_path.exists():
                    result_path.unlink()
                txt_path = TRANSCRIPT_DIR / f"{p.stem}.txt"
                if txt_path.exists():
                    txt_path.unlink()
            logger.info("选择性处理 %d 条录音（含重新识别）: %s", len(pending), files_param)
        else:
            # Existing behavior: process all pending (non-completed) files
            pending = [
                p
                for p in sorted(INPUT_DIR.iterdir())
                if p.suffix.lower() in AUDIO_EXTENSIONS
                and not any(
                    rec["file"] == p.name and rec["status"] == "completed"
                    for rec in RECORDS.values()
                )
            ]
            logger.info("批量处理 %d 条录音", len(pending))

        if not pending:
            logger.info("没有待处理的录音")
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

    except Exception as e:
        logger.exception("批量处理异常")
        yield f"event: error\ndata: {json.dumps({'file': '', 'error': f'服务器内部错误: {e}'}, ensure_ascii=False)}\n\n"
        yield "event: complete\ndata: {}\n\n"


def _transcribe_and_analyze(
    audio_path: Path, stt: STTEngine, analyzer: RuleAnalyzer
) -> dict:
    """Run STT + analysis synchronously (called in thread pool)."""
    tr = stt.transcribe(str(audio_path), language="zh")
    analysis = analyzer.analyze(tr.text)

    # LLM transcript cleaning (speaker diarization + text cleanup)
    clean_result = clean_transcript(tr.segments, tr.text)
    display_text = clean_result.text if clean_result.success else tr.text
    if clean_result.success:
        logger.info("转录整理完成: %s", audio_path.name)
    else:
        logger.warning("转录整理跳过（API 不可用或失败），使用原始文字稿: %s", audio_path.name)

    # Save transcript (cleaned if available, raw as fallback)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"{audio_path.stem}.txt"
    transcript_path.write_text(display_text, encoding="utf-8")

    # Save analysis result
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{audio_path.stem}_result.json"
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
        "transcript_preview": display_text[:200],
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
                zf.write(audio_file, f"{zip_base}{Path(rec['file']).suffix}")

            # Transcript — try .txt first (web UI), fall back to .json (CLI)
            stem = Path(rec['file']).stem
            txt_path = TRANSCRIPT_DIR / f"{stem}.txt"
            if txt_path.exists():
                zf.write(txt_path, f"{zip_base}.txt")
            else:
                # Old CLI transcripts were saved as .json
                old_json = TRANSCRIPT_DIR / f"{stem}.json"
                if old_json.exists():
                    import json as json_mod
                    txt_data = json_mod.loads(old_json.read_text(encoding="utf-8"))
                    zf.writestr(f"{zip_base}.txt", txt_data.get("text", ""))

            # Result JSON
            result_path = OUTPUT_DIR / f"{Path(rec['file']).stem}_result.json"
            if result_path.exists():
                zf.write(result_path, f"{zip_base}_result.json")

    from urllib.parse import quote

    safe_filename = f"{zip_base}.zip"
    # RFC 5987 encoding for non-ASCII filenames in Content-Disposition
    encoded = quote(safe_filename, safe="")

    return FileResponse(
        path=str(zip_path),
        filename=safe_filename,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"
        },
        background=lambda: shutil.rmtree(tmpdir, ignore_errors=True),
    )


# ── Static file mount (after API routes so they take priority) ──────────

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

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
