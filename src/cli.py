"""CLI entry point for the audio record filter system."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Allow both `python src/cli.py` and `python -m src.cli`
if __name__ == "__main__" and __package__ is None:
    __package__ = "src"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .analyzer import Analyzer, RuleAnalyzer  # noqa: E402
from .analyzer import LLMAnalyzer  # noqa: E402
from .models import Level, RecordResult  # noqa: E402
from .stt import STTEngine  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Default paths ───────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = HERE / "input"
DEFAULT_TRANSCRIPT_DIR = HERE / "transcripts"
DEFAULT_OUTPUT_DIR = HERE / "output"

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".amr"}


# ── Report helpers ──────────────────────────────────────────────────────


LEVEL_COLORS = {
    Level.BEGINNER: "\033[92m",  # green
    Level.INTERMEDIATE: "\033[93m",  # yellow
    Level.ADVANCED: "\033[91m",  # red
}
RESET = "\033[0m"


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def print_result(result: RecordResult) -> None:
    color = LEVEL_COLORS.get(result.level, "")
    print(
        f"  {result.level.emoji}  "
        f"{result.file} ({fmt_duration(result.duration)})"
    )
    print(f"    等级: {color}{result.level.label_cn}{RESET} ({result.score:.0%})")
    if result.details.get("reasoning"):
        print(f"    💡 LLM 理由: {result.details['reasoning']}")
    details = result.details
    if "step_results" in details:
        print(f"    完成步骤: {details['completed_steps']}/{details['total_steps']}")
        for sr in details["step_results"]:
            icon = "✅" if sr["matched"] else "❌"
            print(f"      {icon} {sr['step_name']} ({sr['score']:.0%})")
    if details.get("missing_keywords"):
        missing = details["missing_keywords"]
        if missing:
            print(f"    缺失关键词: {'、'.join(missing[:5])}")
    if result.transcript:
        preview = result.transcript[:150].replace("\n", " ")
        print(f"    文字稿预览: {preview}...")
    print()


def print_summary(results: list[RecordResult], elapsed: float) -> None:
    levels = [r.level for r in results]
    counts = {lvl: levels.count(lvl) for lvl in Level}
    print("=" * 48)
    print(f"  处理完成  {len(results)} 条录音 ({elapsed:.1f}s)")
    print(f"    🟢 初级: {counts[Level.BEGINNER]}")
    print(f"    🟡 中级: {counts[Level.INTERMEDIATE]}")
    print(f"    🔴 高级: {counts[Level.ADVANCED]}")
    print("=" * 48)


# ── Core processing ─────────────────────────────────────────────────────


def process_file(
    audio_path: Path,
    stt: STTEngine,
    analyzer: Analyzer,
    transcript_dir: Path,
    output_dir: Path,
    language: str,
) -> RecordResult:
    """Transcribe one audio file, analyze it, save outputs, return result."""

    # 1. Transcribe
    transcribe_result = stt.transcribe(str(audio_path), language=language)

    # Save transcript
    transcript_path = transcript_dir / f"{audio_path.stem}.json"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "file": transcribe_result.file,
                "duration": transcribe_result.duration,
                "text": transcribe_result.text,
                "segments": transcribe_result.segments,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 2. Analyze
    analysis = analyzer.analyze(transcribe_result.text)

    result = RecordResult(
        file=audio_path.name,
        duration=transcribe_result.duration,
        transcript=transcribe_result.text,
        level=analysis.level,
        score=analysis.score,
        details={
            "total_steps": analysis.total_steps,
            "completed_steps": analysis.completed_steps,
            "step_results": [
                {
                    "step_name": sr.step_name,
                    "matched": sr.matched,
                    "score": sr.score,
                    "matched_keywords": sr.matched_keywords,
                }
                for sr in analysis.step_results
            ],
            "missing_keywords": analysis.missing_keywords,
            "reasoning": analysis.reasoning,
            "transcript_preview": transcribe_result.text[:200],
        },
    )

    # Save analysis
    output_path = output_dir / f"{audio_path.stem}_result.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "file": result.file,
                "duration": result.duration,
                "level": result.level.value,
                "score": result.score,
                "details": result.details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result


# ── CLI ─────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="通话录音分级系统 — 将录音自动转文字并按话术完整度分级",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  %(prog)s                              # 处理 input/ 下所有录音\n"
            "  %(prog)s -i call.mp3                  # 处理单个文件\n"
            "  %(prog)s -i input/ -l en              # 英文录音\n"
            "  %(prog)s --model base                 # 用小模型（更快、更省显存）\n"
            "  %(prog)s --device cpu                 # 只用 CPU\n"
        ),
    )
    parser.add_argument(
        "-i", "--input",
        default=str(DEFAULT_INPUT_DIR),
        help=f"输入目录或文件 (默认: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--transcript-dir",
        default=str(DEFAULT_TRANSCRIPT_DIR),
        help=f"文字稿输出目录 (默认: {DEFAULT_TRANSCRIPT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"结果输出目录 (默认: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper 模型大小 (默认: large-v3，small/base 更快但准确率略低)",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="运行设备 (默认: auto → 有 CUDA 则用 GPU)",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="语言代码 (默认: zh，英文用 en，或留空自动检测)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出详细日志",
    )
    parser.add_argument(
        "--analyzer",
        default="rule",
        choices=["rule", "llm"],
        help="分析器类型: rule=关键词匹配, llm=DeepSeek大模型 (默认: rule)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="DeepSeek API 密钥 (或用环境变量 DEEPSEEK_API_KEY)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input)
    transcript_dir = Path(args.transcript_dir)
    output_dir = Path(args.output_dir)

    # Collect audio files
    if input_path.is_file():
        audio_files = [input_path]
    elif input_path.is_dir():
        audio_files = sorted(
            p for p in input_path.iterdir()
            if p.suffix.lower() in AUDIO_EXTENSIONS
        )
    else:
        parser.error(f"输入路径不存在: {input_path}")

    if not audio_files:
        print(f"在 {input_path} 中没有找到录音文件 ({', '.join(AUDIO_EXTENSIONS)})")
        return 1

    analyzer_label = "LLM (DeepSeek)" if args.analyzer == "llm" else "规则引擎 (关键词)"
    print(f"\n🎯 通话录音分级系统")
    print(f"   模型: {args.model}  设备: {args.device}  语言: {args.language or '自动'}")
    print(f"   分析器: {analyzer_label}")
    print(f"   待处理: {len(audio_files)} 条录音\n")

    # Init engine & analyzer
    stt = STTEngine(model_size=args.model, device=args.device)
    if args.analyzer == "llm":
        analyzer: Analyzer = LLMAnalyzer(api_key=args.api_key)
    else:
        analyzer: Analyzer = RuleAnalyzer()

    # Process
    results: list[RecordResult] = []
    start = time.time()

    for i, af in enumerate(audio_files, 1):
        print(f"[{i}/{len(audio_files)}] 正在处理: {af.name}")
        try:
            result = process_file(af, stt, analyzer, transcript_dir, output_dir, args.language)
            results.append(result)
            print_result(result)
        except Exception:
            logger.exception("处理 %s 失败", af.name)
            print(f"  ❌ {af.name} 处理失败，跳过\n")

    elapsed = time.time() - start
    print_summary(results, elapsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
