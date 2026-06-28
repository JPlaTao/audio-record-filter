"""LLM-based summary field extractor.

Uses DeepSeek to extract configurable summary fields (name, status,
intention, school, etc.) from the cleaned transcript.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractResult:
    """Result of extracting summary fields."""
    values: dict[str, str] = field(default_factory=dict)
    success: bool = False


def _build_field_descriptions(
    fields: list,
) -> tuple[str, str]:
    """Build the prompt section and JSON schema for a list of field objects.

    Each field object must have: key, label, type, options (list for enums).

    Returns (field_descriptions_text, json_keys_list).
    """
    lines: list[str] = []
    json_keys: list[str] = []
    for f in fields:
        json_keys.append(f.key)
        if f.type == "enum":
            opts = ", ".join(f.options)
            lines.append(f'- {f.key} ({f.label}): 可选值：{opts}。如果无法从对话中确认，返回"未识别"。')
        else:
            lines.append(f'- {f.key} ({f.label})：从对话中提取。如果无法确认，返回"未识别"。')
    return "\n".join(lines), json.dumps(
        {k: "" for k in json_keys}, ensure_ascii=False, indent=2
    )


def extract_summary(
    transcript: str,
    fields: list,
    api_key: str | None = None,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> ExtractResult:
    """Extract summary fields from a transcript using DeepSeek.

    Args:
        transcript: The cleaned transcript (with 顾问:/学员: labels preferred).
        fields: List of SummaryField objects defining what to extract.
        api_key: DeepSeek API key (or DEEPSEEK_API_KEY env var).
        base_url: API base URL.
        model: Model name.

    Returns:
        ExtractResult with values dict on success, empty on failure.
    """
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set, skipping summary extraction")
        return ExtractResult(success=False)

    # Only extract fields that depend on analysis (not filename-based)
    analysis_fields = [f for f in fields if f.extract_from != "filename"]
    if not analysis_fields:
        return ExtractResult(values={}, success=True)

    field_text, field_schema = _build_field_descriptions(analysis_fields)

    system_prompt = f"""你是一位通话录音信息提取专家。你会收到一段销售顾问与学员之间的通话录音转写文本。

请根据对话内容提取以下字段，以 JSON 格式返回。不要包含其他文字，只返回 JSON。

字段定义：
{field_text}

返回格式：
{field_schema}"""

    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请从以下通话录音中提取字段：\n\n{transcript[:8000]}"},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        # Extract JSON from the response (handle markdown fences)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LLM did not return a JSON object")

        # Validate: ensure all expected keys are present
        result: dict[str, str] = {}
        for f in analysis_fields:
            val = parsed.get(f.key)
            if val and isinstance(val, str) and val.strip():
                result[f.key] = val.strip()
            else:
                result[f.key] = "未识别"

        logger.info("摘要提取完成: %s", {k: v for k, v in result.items()})
        return ExtractResult(values=result, success=True)

    except Exception as e:
        logger.exception("摘要提取失败: %s", e)
        return ExtractResult(success=False)
