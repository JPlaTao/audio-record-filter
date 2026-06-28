# Transcript Cleaner + ZIP Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add LLM-based transcript cleaning (speaker diarization + text cleanup) and ZIP internal file renaming.

**Architecture:** New `src/transcript_cleaner.py` module calls DeepSeek API. ZIP rename is a small change to `export_zip()` in `src/web/app.py`.

**Tech Stack:** Same as existing (DeepSeek API via openai SDK)

**Global Constraints:**
- All existing `src/` modules (`stt.py`, `analyzer.py`, `models.py`, `cli.py`) must remain untouched
- LLM cleaning failure must NOT block the processing pipeline (graceful fallback to raw text)
- ZIP rename changes only the archive entry name, never the on-disk files
- Reuse DEEPSEEK_API_KEY env var from existing setup

---

### Task 1: ZIP internal file renaming

**Files:**
- Modify: `src/web/app.py` (export_zip route)

**Interfaces:**
- Consumes: `build_zip_filename()` from config module (existing)
- Should use `zip_base` variable (already computed) to rename arcnames

**Change:**
In the `export_zip` route, `zip_base` is already computed. When writing files to the ZIP:
- Get the extension from each file
- Rename arcname to `{zip_base}{ext}` instead of original filename

Example: `260624李玉堂.m4a` → `张三_在职_高意向_全日制本科.m4a`

Implement this, commit with `feat: rename ZIP internal files to match ZIP package name`

---

### Task 2: Create transcript_cleaner.py module

**Files:**
- Create: `src/transcript_cleaner.py`

**Interfaces:**
- Produces: `clean_transcript(segments, transcript, api_key, base_url, model) -> CleanResult`
- Consumes: `DEEPSEEK_API_KEY` env var, openai SDK

```python
@dataclass
class CleanResult:
    text: str          # cleaned transcript with 顾问:/学员: labels
    success: bool       # whether LLM call succeeded

def clean_transcript(
    segments: list[dict],    # [{"start": 0.0, "end": 2.5, "text": "..."}]
    transcript: str,         # raw transcript full text as fallback
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> CleanResult:
```

Prompt design:
- System: "你是一位通话录音整理专家..." (Chinese instructions for speaker labeling + text cleanup)
- User: The raw segments formatted with timestamps
- On failure: return CleanResult(text=transcript, success=False) — raw text as fallback
- On success: return CleanResult(text=cleaned_text, success=True)

Implement, commit with `feat: add LLM-based transcript cleaning module`

---

### Task 3: Wire cleaner into processing pipeline

**Files:**
- Modify: `src/web/app.py` (_transcribe_and_analyze function)

**Changes to `_transcribe_and_analyze`:**
1. After `tr = stt.transcribe(...)` and before analysis
2. Call `clean_transcript(tr.segments, tr.text, api_key=...)`
3. If success=True, save `transcript_path` with cleaned text instead of raw text
4. Log whether cleaning succeeded or failed
5. `analysis = analyzer.analyze(tr.text)` still uses raw text

Implement, commit with `feat: wire transcript cleaner into processing pipeline`
