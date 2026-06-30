"""Text analysis engine for evaluating call transcripts against sales scripts.

Designed with a strategy pattern so you can swap in an LLM-based analyzer
later — just implement the same Analyzer interface.
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

try:
    from zhconv import convert as zhconvert
except ImportError:
    zhconvert = None  # fallback: no conversion

from .models import (
    AnalysisResult,
    Level,
    Script,
    ScriptStep,
    StepMatchResult,
)

logger = logging.getLogger(__name__)


# ── Interface ────────────────────────────────────────────────────────────


class Analyzer(ABC):
    """Abstract analyzer. Implement this to add an LLM-based judge later."""

    @abstractmethod
    def analyze(self, transcript: str, script: Script | None = None) -> AnalysisResult:
        """Analyze a transcript and return a level + breakdown."""
        ...


# ── Rule-based (第一期) ─────────────────────────────────────────────────


class RuleAnalyzer(Analyzer):
    """Keyword/step-matching analyzer.

    Matches each step's primary/secondary keywords against the transcript
    and computes a coverage score → level mapping.
    """

    # ── 沃林电销话术脚本（根据实际话术整理） ───────────────────────────────
    # 四大价值观：先舍后得，正面积极，终身学习，建立关系
    # 愿景：提升一千万人职场价值
    # 使命：通过精准的职业定位高效技术赋能，帮助每一位职场人梦想高新就职
    #
    # 四部分：①基本信息了解 → ②过往情况了解 → ③未来期望了解 → ④合作模式介绍+促成

    FALLBACK_STEPS: list[ScriptStep] = [
        # ── 第一部分：基本信息了解 ──────────────────────────────────────
        ScriptStep(
            name="①开场介绍身份",
            description="自我介绍，表明是深圳沃林公司HR/猎聘身份",
            primary_keywords=["你好", "我是", "深圳沃林", "沃林"],
            secondary_keywords=["HR", "猎聘", "经理", "公司", "人才服务"],
        ),
        ScriptStep(
            name="①确认接听状态",
            description="询问是否方便接电话、是否还在找工作",
            primary_keywords=["方便接电话", "找工作", "还在找工作"],
            secondary_keywords=["方便", "接电话", "在找工作", "在职", "离职"],
        ),
        ScriptStep(
            name="①核实学历城市",
            description="确认全日制本科学历、学信网可查、所在城市",
            primary_keywords=["全日制本科", "学信网", "学历", "毕业证"],
            secondary_keywords=["学位证", "双证", "哪个城市", "在深圳"],
        ),

        # ── 第二部分：学员过往情况了解 ──────────────────────────────────
        ScriptStep(
            name="②了解在职状态",
            description="了解是在职还是离职、是否在看新机会",
            primary_keywords=["在职", "离职", "辞职", "看新的工作机会"],
            secondary_keywords=["离职流程", "走完离职", "找到才离职", "什么原因想离职"],
        ),
        ScriptStep(
            name="②了解Offer情况",
            description="询问是否收到意向offer及满意度",
            primary_keywords=["offer", "意向", "满意"],
            secondary_keywords=["收到", "入职", "不满意", "薪资"],
        ),
        ScriptStep(
            name="②了解离职原因与薪资",
            description="了解上份工作离职原因和薪资情况",
            primary_keywords=["离职原因", "上份工作", "上份薪资"],
            secondary_keywords=["方便问", "屈才", "薪资"],
        ),

        # ── 第三部分：学员未来期望了解 ──────────────────────────────────
        ScriptStep(
            name="③了解期望薪资",
            description="询问期望薪资待遇",
            primary_keywords=["期望薪资", "期望", "期望多少"],
            secondary_keywords=["薪资", "待遇"],
        ),
        ScriptStep(
            name="③了解职业诉求",
            description="了解更看重公司发展、个人提升还是薪资",
            primary_keywords=["公司发展", "个人提升", "看重"],
            secondary_keywords=["行业发展", "方向", "发展机会"],
        ),

        # ── 第四部分：合作模式介绍 + 促成 ──────────────────────────────
        ScriptStep(
            name="④介绍岗前实训",
            description="介绍75天免费岗前实训、对接企业上岗模式",
            primary_keywords=["岗前实训", "免费", "AI大模型", "对接企业"],
            secondary_keywords=["75天", "熟手", "企业上岗", "实训结束"],
        ),
        ScriptStep(
            name="④说明收费方式",
            description="说明入职后每月支付服务费，拿不到薪资不收费",
            primary_keywords=["服务费", "工资到账", "4900", "保障"],
            secondary_keywords=["15-25K", "拿到薪资", "不收费", "承诺薪资", "100%"],
        ),
        ScriptStep(
            name="④异议处理",
            description="处理客户对收费/培训的顾虑",
            primary_keywords=["免费", "不用先付费", "放心", "保障"],
            secondary_keywords=["理解", "担心", "考虑", "顾虑", "信用"],
        ),
        ScriptStep(
            name="④促成邀约试听",
            description="邀约参加三天免费试听，促成下一步",
            primary_keywords=["试听", "过来", "新开一个班", "过来看看"],
            secondary_keywords=["实操课", "免费试听", "方便", "安排", "约"],
        ),
    ]

    def __init__(
        self,
        script: Script | None = None,
        primary_weight: float = 0.6,
        secondary_weight: float = 0.4,
        # Score thresholds for level mapping
        advanced_threshold: float = 0.55,
        intermediate_threshold: float = 0.25,
        # Minimum score per step to count as "completed"
        step_min_score: float = 0.25,
    ) -> None:
        self.script = script
        self.primary_weight = primary_weight
        self.secondary_weight = secondary_weight
        self.advanced_threshold = advanced_threshold
        self.intermediate_threshold = intermediate_threshold
        self.step_min_score = step_min_score

    def analyze(
        self,
        transcript: str,
        script: Script | None = None,
    ) -> AnalysisResult:
        steps = (script or self.script).steps if (script or self.script) else self.FALLBACK_STEPS
        # Normalize: convert traditional Chinese → simplified for consistent matching
        normalized = zhconvert(transcript, "zh-cn") if zhconvert else transcript
        text_lower = normalized.lower()

        step_results: list[StepMatchResult] = []
        total_keywords_matched = 0
        total_keywords = 0

        for step in steps:
            matched_pris: list[str] = []
            matched_secs: list[str] = []

            for kw in step.primary_keywords:
                total_keywords += 1
                if re.search(re.escape(kw.lower()), text_lower):
                    matched_pris.append(kw)
                    total_keywords_matched += 1

            for kw in step.secondary_keywords:
                total_keywords += 1
                if re.search(re.escape(kw.lower()), text_lower):
                    matched_secs.append(kw)
                    total_keywords_matched += 1

            # Step score: weighted completion
            pri_score = (
                len(matched_pris) / len(step.primary_keywords)
                if step.primary_keywords
                else 0
            )
            sec_score = (
                len(matched_secs) / len(step.secondary_keywords)
                if step.secondary_keywords
                else 0
            )
            step_score = pri_score * self.primary_weight + sec_score * self.secondary_weight

            step_results.append(
                StepMatchResult(
                    step_name=step.name,
                    matched=step_score >= self.step_min_score,
                    matched_keywords=matched_pris + matched_secs,
                    score=round(step_score, 2),
                )
            )

        completed_steps = sum(1 for s in step_results if s.matched)
        overall_score = (
            total_keywords_matched / total_keywords if total_keywords > 0 else 0
        )

        # Level mapping
        if overall_score >= self.advanced_threshold:
            level = Level.ADVANCED
        elif overall_score >= self.intermediate_threshold:
            level = Level.INTERMEDIATE
        else:
            level = Level.BEGINNER

        # Collect missing keywords
        missing: list[str] = []
        for step in steps:
            for kw in step.primary_keywords:
                if not re.search(re.escape(kw.lower()), text_lower):
                    missing.append(kw)

        return AnalysisResult(
            total_steps=len(steps),
            completed_steps=completed_steps,
            score=round(overall_score, 2),
            level=level,
            step_results=step_results,
            missing_keywords=missing,
        )


# ── LLM Analyzer (DeepSeek) ────────────────────────────────────────────

DEFAULT_CRITERIA_PATH = Path(__file__).resolve().parent.parent / "docs" / "录音等级判断标准.md"


class LLMAnalyzer(Analyzer):
    """LLM-based analyzer using DeepSeek (OpenAI-compatible) API.

    Reads the grading criteria from docs/录音等级判断标准.md and injects
    it into the system prompt.  Update that document → the LLM follows it.

    Usage:
        analyzer = LLMAnalyzer()
        result = analyzer.analyze(transcript)

    Env:
        DEEPSEEK_API_KEY  — your DeepSeek API key (or pass via `api_key`).
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        api_key: str | None = None,
        criteria_path: str | Path | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.criteria_path = Path(criteria_path) if criteria_path else DEFAULT_CRITERIA_PATH

        # Read grading criteria at init so editing the doc takes effect on next run
        self._criteria = self._load_criteria()
        self._client = None

    # ── Lazy client ────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # noqa: PLC0415
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def _load_criteria(self) -> str:
        if not self.criteria_path.exists():
            logger.warning("判断标准文档未找到: %s，使用内置默认标准", self.criteria_path)
            return "使用4阶段12步骤评估话术完整度，判断初级/中级/高级。"
        return self.criteria_path.read_text(encoding="utf-8")

    # ── Bad case examples (few-shot) ────────────────────────────────────

    _BAD_CASE_EXAMPLES = """
## ⚠️ 重要：先看反例 —— 避免"看起来像中级，实际是初级"的陷阱

以下两个案例中，系统曾经误判为中级，但业务方确认为初级。
请特别注意它们的特征，判断当前录音是否有类似问题：

示例 1：
  录音：林明杰
  覆盖度：57%（中），质量分：0.28（低）
  学员状态：全程被动，"嗯"、"好"、"知道了"
  问题：按清单走流程，无追问、无应变、全程机械
  正确等级：初级
  原因：覆盖度够但质量低。学员不主动、顾问不追问 → 只适合新手听

示例 2：
  录音：冷松芮
  覆盖度：39%（中），质量分：0.31（低）
  学员状态：被动应答，有明显内容错误（人力资源描述有误）
  问题：转折生硬、缺乏深度追问、内容有硬伤
  正确等级：初级
  原因：刚过覆盖度门槛 + 质量分低 + 内容硬伤 → 只适合新手听"""

    def _bad_case_block(self) -> str:
        return self._BAD_CASE_EXAMPLES

    def _build_system_prompt(self) -> str:
        return f"""你是一位专业的电话销售录音评估专家。你的任务是根据以下判断标准，对通话录音的文字稿进行等级评估。

## 核心原则（极其重要）

⚠️ **"完成了步骤" ≠ "做得好"。** 判断"做了没有"是基础，判断"做得怎么样"才是关键。

一条录音如果只是机械地按清单走完了流程、没有出彩之处、客户全程被动应答，即使 12 个步骤全部覆盖，也只能评 **初级**。

- **初级** = 走了流程，但只是"把词念了"。客户反应平淡，电销员没有展现出超出背稿水平的沟通技巧。
- **中级** = 流程完整 + 展现出一定的应变、追问、共情、说服能力。
- **高级** = 流程纯熟 + 面对异议灵活化解 + 客户被说服 / 主动感兴趣 + 自然促成。

请严格区分"做了"和"做好"之间的区别。

## 判断标准

{self._criteria}

{self._bad_case_block()}

## 输出格式

请以 JSON 格式返回分析结果，不要包含其他文字：

```json
{{
  "level": "beginner" | "intermediate" | "advanced",
  "score": 0.0-1.0 之间的数字,
  "reasoning": "简要说明判定理由，指出哪些做得好、哪些不足，特别说明是否参考了质量分析数据",
  "steps": [
    {{
      "name": "步骤名称（如①开场介绍身份）",
      "matched": true 或 false,
      "score": 0.0-1.0,
      "evidence": "该步骤的文字证据摘录"
    }}
  ]
}}
```

注意：
- score 是整体完成度，0-1 之间
- 每个步骤的 score 表示该步骤的完成质量
- level 严格按照判断标准中的"二维矩阵"来定"""

    # ── Matrix judge ────────────────────────────────────────────────────

    @staticmethod
    def _matrix_judge(coverage: float, quality: float) -> str:
        """Determine suggested level from the 2D coverage × quality matrix.

        This is a **reference** for the LLM, not a hard rule.
        """
        if coverage < 0.35:
            cov = "low"
        elif coverage < 0.70:
            cov = "medium"
        else:
            cov = "high"

        if quality < 0.4:
            qual = "low"
        elif quality < 0.7:
            qual = "medium"
        else:
            qual = "high"

        matrix = {
            ("low", "low"): "beginner",
            ("low", "medium"): "beginner",
            ("low", "high"): "intermediate",
            ("medium", "low"): "beginner",
            ("medium", "medium"): "intermediate",
            ("medium", "high"): "advanced",
            ("high", "low"): "beginner",
            ("high", "medium"): "advanced",
            ("high", "high"): "advanced",
        }
        return matrix.get((cov, qual), "beginner")

    # ── Build user prompt ───────────────────────────────────────────────

    def _build_user_prompt(
        self,
        transcript: str,
        quality_data: dict | None = None,
        coverage_data: dict | None = None,
    ) -> str:
        parts: list[str] = []

        if coverage_data:
            parts.append("## 客观分析数据 — 规则分析结果")
            parts.append(f"- 整体覆盖度: {coverage_data.get('score', 0) * 100:.0f}%")
            parts.append(
                f"- 完成步骤: {coverage_data.get('completed_steps', 0)}/"
                f"{coverage_data.get('total_steps', 12)}"
            )
            steps = coverage_data.get("step_results", [])
            for s in steps:
                icon = "✅" if s.get("matched") else "⭕"
                parts.append(f"  {icon} {s.get('name', '?')} ({s.get('score', 0) * 100:.0f}%)")
            parts.append("")

        if quality_data:
            parts.append("## 客观分析数据 — 通话质量分析")
            q_score = quality_data.get("overall_score", 0)
            q_label = "低" if q_score < 0.4 else "中" if q_score < 0.7 else "高"
            parts.append(f"- 综合质量分: {q_score:.2f}（{q_label}）")
            for sig in quality_data.get("signals", []):
                parts.append(
                    f"  - {sig.get('label', '?')}: {sig.get('value', 0)}"
                    f"（{sig.get('assessment', '?')}）"
                )
            parts.append("")

        if coverage_data and quality_data:
            cov_score = coverage_data.get("score", 0)
            qual_score = quality_data.get("overall_score", 0)
            matrix_level = self._matrix_judge(cov_score, qual_score)
            cov_label = "低" if cov_score < 0.35 else "中" if cov_score < 0.7 else "高"
            qual_label = "低" if qual_score < 0.4 else "中" if qual_score < 0.7 else "高"
            parts.append("## 二维矩阵参考")
            parts.append(f"覆盖度: {cov_score * 100:.0f}% → {cov_label}")
            parts.append(f"质量分: {qual_score:.2f} → {qual_label}")
            parts.append(f"📋 矩阵建议等级: **{matrix_level}**")
            parts.append("（矩阵仅为参考建议，请结合文字稿内容做出最终判断）")
            parts.append("")

        # Append transcript
        max_chars = 7000  # reduced to make room for structured data
        text = transcript[:max_chars]
        if len(transcript) > max_chars:
            text += "\n\n[注意：文字稿过长，已截断。仅根据以上内容评估。]"

        parts.append("---")
        parts.append(f"请评估以下通话录音文字稿：\n\n{text}")
        return "\n".join(parts)

    # ── Analyze ────────────────────────────────────────────────────────

    def analyze(
        self,
        transcript: str,
        script: Script | None = None,
        quality_data: dict | None = None,
        coverage_data: dict | None = None,
    ) -> AnalysisResult:
        if not self.api_key:
            raise RuntimeError(
                "DeepSeek API 密钥未设置。请通过环境变量 DEEPSEEK_API_KEY 或 "
                "--api-key 参数提供。\n"
                "  申请地址: https://platform.deepseek.com"
            )

        client = self._get_client()
        logger.info("LLM 分析中 (model=%s, quality_data=%s)...", self.model, quality_data is not None)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": self._build_user_prompt(transcript, quality_data, coverage_data)},
            ],
            temperature=0.1,
            max_tokens=2048,
        )

        content = response.choices[0].message.content or ""
        return self._parse_response(content)

    def _parse_response(self, content: str) -> AnalysisResult:
        # Extract JSON from markdown code block or bare JSON
        import json as json_mod  # noqa: PLC0415

        json_str = content.strip()
        # Try to extract from ```json ... ``` block
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        try:
            data = json_mod.loads(json_str)
        except json_mod.JSONDecodeError as exc:
            logger.error("LLM 返回的 JSON 解析失败: %s\n原始内容: %s", exc, content[:300])
            raise RuntimeError(f"LLM 返回格式错误: {exc}") from exc

        level_str = data.get("level", "beginner")
        try:
            level = Level(level_str)
        except ValueError:
            logger.warning("未知等级 '%s'，默认初级", level_str)
            level = Level.BEGINNER

        score = float(data.get("score", 0))
        steps_data = data.get("steps", [])

        step_results: list[StepMatchResult] = []
        missing_keywords: list[str] = []

        for s in steps_data:
            name = s.get("name", "未知步骤")
            matched = s.get("matched", False)
            step_score = float(s.get("score", 0))
            step_results.append(
                StepMatchResult(
                    step_name=name,
                    matched=matched,
                    score=round(step_score, 2),
                )
            )
            if not matched:
                missing_keywords.append(name)

        completed = sum(1 for s in step_results if s.matched)

        reasoning = data.get("reasoning", "")

        return AnalysisResult(
            total_steps=len(step_results) or 12,
            completed_steps=completed,
            score=round(score, 2),
            level=level,
            step_results=step_results,
            missing_keywords=missing_keywords,
            reasoning=reasoning,
        )
