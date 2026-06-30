"""Data models for the audio record filter system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Level(str, Enum):
    """Proficiency level for a call recording."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def label_cn(self) -> str:
        return {
            "beginner": "初级",
            "intermediate": "中级",
            "advanced": "高级",
        }[self.value]

    @property
    def emoji(self) -> str:
        return {
            "beginner": "🟢",
            "intermediate": "🟡",
            "advanced": "🔴",
        }[self.value]


@dataclass
class ScriptStep:
    """A single step in the sales script with matching rules."""

    name: str
    description: str
    # Keywords that MUST appear to consider this step completed
    primary_keywords: list[str] = field(default_factory=list)
    # Keywords that STRENGTHEN the match but aren't required alone
    secondary_keywords: list[str] = field(default_factory=list)


@dataclass
class Script:
    """The reference sales script used for evaluation."""

    name: str
    steps: list[ScriptStep]


@dataclass
class StepMatchResult:
    """Match result for a single script step."""

    step_name: str
    matched: bool
    matched_keywords: list[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 - 1.0 how well this step was covered


@dataclass
class AnalysisResult:
    """Result of analyzing a transcript against a script."""

    total_steps: int
    completed_steps: int
    score: float  # 0.0 - 1.0 overall completion rate
    level: Level
    step_results: list[StepMatchResult] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    reasoning: str = ""  # LLM's explanation for the decision (LLM-only)


@dataclass
class QualitySignalResult:
    """Result for a single quality signal (Layer 2 of the pipeline)."""

    key: str
    label: str
    value: float
    score: float = 0.0  # 0-1 normalized score
    weight: float = 1.0
    assessment: str = ""  # "优秀" / "良好" / "一般" / "差"


@dataclass
class QualityResult:
    """Overall quality assessment (Layer 2 pipeline output)."""

    overall_score: float = 0.0  # 0-1 weighted average
    signals: list[QualitySignalResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "signals": [
                {
                    "key": s.key,
                    "label": s.label,
                    "value": s.value,
                    "score": s.score,
                    "weight": s.weight,
                    "assessment": s.assessment,
                }
                for s in self.signals
            ],
        }


@dataclass
class TranscribeResult:
    """Result of transcribing an audio file."""

    file: str
    duration: float  # seconds
    text: str
    segments: list[dict] = field(default_factory=list)


@dataclass
class RecordResult:
    """Final analysis output for one recording."""

    file: str
    duration: float
    transcript: str
    level: Level
    score: float
    details: dict
