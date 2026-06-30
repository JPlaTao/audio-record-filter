"""Voice call quality scoring — Layer 2 of the three-tier pipeline.

Measures objective quality signals from the transcript that are NOT about
step coverage: student engagement, consultant skill, conversational depth.

Design is data-driven — add new signals by appending to the config list, no
code changes needed for the scoring loop.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

from .models import QualityResult, QualitySignalResult

logger = logging.getLogger(__name__)

# ── Signal configuration ──────────────────────────────────────────────────


@dataclass
class SignalConfig:
    """Configuration for one quality signal."""

    key: str
    label: str
    weight: float
    enabled: bool = True
    # For higher_is_better signals: value >= good_threshold → score 1.0
    # For lower_is_better signals:  value <= good_threshold → score 1.0
    higher_is_better: bool = True
    good_threshold: float = 0.30


# ── Parser helpers ────────────────────────────────────────────────────────

_SPEAKER_RE = re.compile(r"^(顾问|学员)[：:]")

_QUESTION_RE = re.compile(r"[？?]|为什么|怎么|具体说|可以[吗么]|是不是|有没有|能不能")
_FOLLOWUP_RE = re.compile(r"为什么|怎么说|具体[说讲]|比如|能说说|详细[说讲]|"
                          r"什么原因|怎么回事|然后呢|意思是|举个例子")
_FILLER_RE = re.compile(r"嗯|啊|呃|那个|就是说|然后[呢么]?|这个[嘛]?|对吧|"
                        r"是吧|就是[说]?|反正|其实")


def _parse_speaker_lines(text: str) -> dict[str, list[str]] | None:
    """Parse cleaned transcript into speaker-labeled line groups.

    Returns None if no speaker labels found (raw transcript without
    ``顾问:``/``学员:`` markers).
    """
    consultant: list[str] = []
    student: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        m = _SPEAKER_RE.match(line)
        if not m:
            continue
        content = line[m.end():].strip()
        if m.group(1) == "顾问":
            consultant.append(content)
        else:
            student.append(content)

    if not consultant and not student:
        return None

    return {"consultant": consultant, "student": student}


# ── Signal implementations ───────────────────────────────────────────────-
# Each takes the parsed dict and returns a raw value (float).
# The scoring loop normalises against the signal's config thresholds.


def _calc_student_ratio(parsed: dict) -> float:
    """Fraction of total chars spoken by the student (学员)."""
    con_chars = sum(len(l) for l in parsed["consultant"])
    stu_chars = sum(len(l) for l in parsed["student"])
    total = con_chars + stu_chars
    return stu_chars / total if total > 0 else 0.0


def _calc_avg_reply_len(parsed: dict) -> float:
    """Average characters per student utterance."""
    lines = parsed["student"]
    if not lines:
        return 0.0
    return sum(len(l) for l in lines) / len(lines)


def _calc_student_questions(parsed: dict) -> float:
    """Number of student utterances containing question patterns."""
    count = 0
    for line in parsed["student"]:
        if _QUESTION_RE.search(line):
            count += 1
    return float(count)


def _calc_followup_density(parsed: dict) -> float:
    """Follow-up question occurrences per 100 chars of consultant speech."""
    text = " ".join(parsed["consultant"])
    if not text:
        return 0.0
    matches = _FOLLOWUP_RE.findall(text)
    return len(matches) / (len(text) / 100)


def _calc_filler_density(parsed: dict, raw_text: str = "") -> float:
    """Filler word occurrences per 100 chars.

    Works on **all** text (both speakers) — gives a global fluency signal.
    Falls back to ``raw_text`` when ``parsed`` has no data.
    """
    text = " ".join(parsed.get("consultant", []) + parsed.get("student", []))
    if not text:
        text = raw_text
    if not text:
        return 0.0
    matches = _FILLER_RE.findall(text)
    return len(matches) / (len(text) / 100)


def _calc_turn_count(parsed: dict) -> float:
    """Number of speaker switches — higher = more interactive."""
    return float(max(len(parsed["consultant"]), len(parsed["student"])))


# ── Registry ─────────────────────────────────────────────────────────────-
# To add a new signal: append a new entry here.  The scoring loop picks it up
# automatically.  Each entry can also be overridden at init time.

DEFAULT_SIGNALS: list[SignalConfig] = [
    # The higher these signals are, the better the call quality
    SignalConfig(
        key="student_speaking_ratio",
        label="学员说话占比",
        weight=0.25,
        good_threshold=0.25,
    ),
    SignalConfig(
        key="student_avg_reply_length",
        label="学员平均回复长度(字)",
        weight=0.20,
        good_threshold=20,
    ),
    SignalConfig(
        key="student_question_count",
        label="学员主动提问次数",
        weight=0.20,
        good_threshold=3,
    ),
    SignalConfig(
        key="consultant_followup_density",
        label="顾问追问密度(次/百字)",
        weight=0.15,
        good_threshold=0.04,
    ),
    SignalConfig(
        key="turn_count",
        label="对话轮次",
        weight=0.10,
        good_threshold=10,
    ),
    # Lower filler density is better — override default
    SignalConfig(
        key="filler_word_density",
        label="语气词密度(次/百字)",
        weight=0.10,
        higher_is_better=False,
        good_threshold=5,
    ),
]

# Signals that require speaker labels parsed from the cleaned transcript.
_SPEAKER_DEPENDENT = {
    "student_speaking_ratio",
    "student_avg_reply_length",
    "student_question_count",
    "consultant_followup_density",
    "turn_count",
}

# Signal → calc function mapping
_SIGNAL_FUNCS: dict[str, Callable] = {
    "student_speaking_ratio": _calc_student_ratio,
    "student_avg_reply_length": _calc_avg_reply_len,
    "student_question_count": _calc_student_questions,
    "consultant_followup_density": _calc_followup_density,
    "filler_word_density": _calc_filler_density,
    "turn_count": _calc_turn_count,
}

# ── Scorer ────────────────────────────────────────────────────────────────


def _assess(score: float) -> str:
    if score >= 0.80:
        return "优秀"
    if score >= 0.60:
        return "良好"
    if score >= 0.40:
        return "一般"
    return "差"


class QualityScorer:
    """Measure objective quality signals from a transcript.

    Usage::

        scorer = QualityScorer()
        result = scorer.score(display_text, raw_text)

    The ``result`` is a :class:`QualityResult` with per-signal breakdown and
    a weighted ``overall_score``.

    Configurable via ``signals`` — pass a custom list of
    :class:`SignalConfig` to override thresholds, weights, or add new
    signals.
    """

    def __init__(self, signals: list[SignalConfig] | None = None) -> None:
        self._signals = signals or DEFAULT_SIGNALS

    def score(
        self,
        display_text: str,
        raw_text: str = "",
    ) -> QualityResult:
        """Compute quality signals and return a scored result.

        Args:
            display_text: The text shown to the user (preferably cleaned
                transcript with ``顾问:``/``学员:`` labels).  When
                cleaning succeeded this is what we parse for speaker data.
            raw_text: Fallback raw whisper text used by
                ``filler_word_density`` when display_text has no speaker
                data.

        Returns:
            QualityResult with per-signal breakdown and overall score.
        """
        parsed = _parse_speaker_lines(display_text)
        has_speakers = parsed is not None
        if not has_speakers:
            parsed = {"consultant": [], "student": []}

        results: list[QualitySignalResult] = []
        total_weight = 0.0

        for cfg in self._signals:
            if not cfg.enabled:
                continue

            # Skip speaker-dependent signals when no speaker labels
            if cfg.key in _SPEAKER_DEPENDENT and not has_speakers:
                continue

            fn = _SIGNAL_FUNCS.get(cfg.key)
            if fn is None:
                logger.warning("未知质量信号: %s", cfg.key)
                continue

            try:
                if cfg.key == "filler_word_density":
                    value = fn(parsed, raw_text)
                else:
                    value = fn(parsed)
            except Exception:
                logger.exception("质量信号计算失败: %s", cfg.key)
                continue

            # Normalise to 0-1 score based on config
            score = self._normalise(value, cfg)
            results.append(
                QualitySignalResult(
                    key=cfg.key,
                    label=cfg.label,
                    value=round(value, 2),
                    score=round(score, 2),
                    weight=cfg.weight,
                    assessment=_assess(score),
                )
            )
            total_weight += cfg.weight

        # Weighted average (normalise for skipped signals)
        overall = (
            sum(r.score * r.weight for r in results) / total_weight
            if total_weight > 0
            else 0.0
        )

        if not has_speakers and results:
            logger.info(
                "质量评分完成（仅全局信号，无说话人标签）: overall=%.2f",
                overall,
            )
        else:
            logger.info("质量评分完成: overall=%.2f (%d 个信号)", overall, len(results))

        return QualityResult(overall_score=round(overall, 2), signals=results)

    @staticmethod
    def _normalise(value: float, cfg: SignalConfig) -> float:
        """Normalise a raw signal value to a 0-1 score.

        For ``higher_is_better`` signals::

            score = min(1.0, value / good_threshold)

        For ``lower_is_better`` signals (filler words)::

            score = max(0.0, 1.0 - value / good_threshold)
        """
        if cfg.good_threshold <= 0:
            return 0.0
        if cfg.higher_is_better:
            return min(1.0, value / cfg.good_threshold)
        return max(0.0, 1.0 - value / cfg.good_threshold)
