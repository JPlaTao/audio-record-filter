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
