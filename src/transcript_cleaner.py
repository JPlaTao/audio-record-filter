"""LLM-based transcript cleaner — speaker diarization + text cleanup.

Uses DeepSeek to label speakers (顾问/学员) and clean up raw Whisper output.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    """Result of cleaning a transcript."""
    text: str       # cleaned text with 顾问:/学员: labels
    success: bool   # whether LLM call succeeded


def clean_transcript(
    segments: list[dict],
    transcript: str,
    api_key: str | None = None,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> CleanResult:
    """Clean and label a transcript using DeepSeek.

    Args:
        segments: List of dicts with "start", "end", "text" keys from Whisper.
        transcript: Full raw text fallback if LLM call fails.
        api_key: DeepSeek API key (or DEEPSEEK_API_KEY env var).
        base_url: API base URL.
        model: Model name.

    Returns:
        CleanResult with labeled text on success, raw transcript on failure.
    """
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set, skipping transcript cleaning")
        return CleanResult(text=transcript, success=False)

    # Build input with timestamps for context
    input_lines = []
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = seg.get("text", "")
        input_lines.append(f"[{start:.1f}s → {end:.1f}s] {text}")
    raw_with_timestamps = "\n".join(input_lines)

    system_prompt = """你是一位通话录音整理专家。请对以下销售顾问与学员之间的通话录音转写文本进行整理。

要求：
1. 说话人分离 — 每句话前标注「顾问:」或「学员:」
   - 顾问：提问、介绍产品、促成邀约的人
   - 学员：接电话、回答问题、提出疑问的人

2. 文字清理：
   - 去掉"嗯"、"啊"、"那个"、"就是说"等不影响语义的语气词和口头禅
   - 根据上下文语义修正 Whisper 转写错误的谐音字/错别字
   - 合并同一人的连续短句为完整句子
   - 中英文标点规范化

3. 输出格式（纯文本，不要 JSON 或 markdown 标记）：
顾问: 你好，请问是张三吗？
学员: 是的，我是。
顾问: 我这边是深圳沃林公司的..."""

    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请整理以下通话录音：\n\n{raw_with_timestamps}"},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        cleaned = response.choices[0].message.content or ""
        if cleaned.strip():
            return CleanResult(text=cleaned.strip(), success=True)

        logger.warning("LLM returned empty content, using raw transcript")
        return CleanResult(text=transcript, success=False)

    except Exception as e:
        logger.exception("Transcript cleaning failed: %s", e)
        return CleanResult(text=transcript, success=False)
