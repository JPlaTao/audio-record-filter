#!/usr/bin/env python
"""收集人工反馈 — 当系统判定与人工判定不一致时，记录 bad case。

用法:
    python scripts/feedback.py 录音文件.m4a  correct_level [原因]

示例:
    python scripts/feedback.py input/call.m4a intermediate "完成了实训介绍和邀约，只是关键词没命中"
    python scripts/feedback.py input/call.m4a advanced
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BAD_CASES_DIR = HERE / "bad_cases"
TRANSCRIPTS_DIR = HERE / "transcripts"
OUTPUT_DIR = HERE / "output"

VALID_LEVELS = {"beginner", "intermediate", "advanced", "初级", "中级", "高级"}


def normalize_level(level: str) -> str:
    mapping = {"初级": "beginner", "中级": "intermediate", "高级": "advanced"}
    return mapping.get(level, level)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    human_level = normalize_level(sys.argv[2])
    reason = sys.argv[3] if len(sys.argv) > 3 else ""

    if human_level not in VALID_LEVELS:
        print(f"❌ 无效等级: {human_level}，可选: {', '.join(VALID_LEVELS)}")
        sys.exit(1)

    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        sys.exit(1)

    # Get system level from cached result
    result_path = OUTPUT_DIR / f"{file_path.stem}_result.json"
    system_level = "unknown"
    if result_path.exists():
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
            system_level = data.get("level", "unknown")

    # Build bad case record
    timestamp = date.today().isoformat()
    record = {
        "file": file_path.name,
        "system_level": system_level,
        "human_level": human_level,
        "reason": reason or "（未填写）",
        "date": timestamp,
        "agreed": system_level == human_level,
    }

    # Save
    BAD_CASES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BAD_CASES_DIR / f"{file_path.stem}_{timestamp}.json"
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if record["agreed"]:
        print(f"✅ 已记录: 系统与人工判定一致 ({human_level})")
    else:
        print(f"📝 Bad case 已保存: {out_path}")
        print(f"   系统: {system_level}  →  人工: {human_level}")
        if reason:
            print(f"   原因: {reason}")


if __name__ == "__main__":
    main()
