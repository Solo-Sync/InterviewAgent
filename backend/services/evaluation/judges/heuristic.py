from __future__ import annotations

import re
from typing import Any

from services.evaluation.models import DIMENSIONS, ScoreResult

_LATIN_TOKEN_RE = re.compile(r"[0-9A-Za-z_]{2,}")
_CJK_SEQ_RE = re.compile(r"[\u4e00-\u9fff]+")

_SIGNALS = {
    "plan": [
        "目标",
        "计划",
        "步骤",
        "拆分",
        "假设",
        "范围",
        "因子",
        "简化",
        "第一步",
        "第二步",
        "最后",
        "先",
        "first",
        "step",
        "plan",
    ],
    "monitor": [
        "检查",
        "修正",
        "调整",
        "回头",
        "验证过程",
        "监控",
        "发现问题",
        "误差",
        "偏差",
        "复盘",
        "控制",
        "check",
        "adjust",
        "monitor",
    ],
    "evaluate": [
        "验证",
        "对比",
        "交叉",
        "反证",
        "合理",
        "证据",
        "评估",
        "上下界",
        "区间",
        "敏感性",
        "校验",
        "validate",
        "compare",
        "evidence",
    ],
    "adapt": [
        "如果",
        "改成",
        "变化",
        "迁移",
        "重构",
        "备选",
        "替代",
        "if",
        "adapt",
        "fallback",
    ],
}

_DIMENSION_REASONS = {
    "plan": "Shows decomposition or explicit planning steps.",
    "monitor": "Shows active checking, correction, or control of the process.",
    "evaluate": "Shows verification or quality judgment using evidence/comparison.",
    "adapt": "Shows strategy adjustment under changed constraints.",
}


class HeuristicJudge:
    def __init__(
        self,
        judge_id: str,
        *,
        dimension_bias: dict[str, float] | None = None,
        strictness: float = 0.0,
    ) -> None:
        self.judge_id = judge_id
        self.dimension_bias = dimension_bias or {}
        self.strictness = strictness

    def invoke(
        self,
        answer: str,
        *,
        question: str = "",
        features: dict[str, Any] | None = None,
    ) -> ScoreResult:
        text = (answer or "").strip()
        lower_text = text.lower()
        semantic_token_count = len(_semantic_tokens(lower_text))
        char_count = len(text)

        dimensions: dict[str, float] = {}
        evidence: dict[str, str] = {}
        deductions: list[str] = []

        complexity_bonus = 0.1 if "。" in text or "." in text else 0.0
        question_overlap = self._question_overlap(lower_text, question.lower())
        hit_counts = {dimension: self._signal_hits(lower_text, _SIGNALS[dimension]) for dimension in DIMENSIONS}
        total_signal_hits = sum(hit_counts.values())
        structured_steps = self._structured_steps(lower_text)
        refusal_penalty = self._refusal_penalty(lower_text)
        prompt_injection_penalty = 0.5 if self._looks_prompt_injection(lower_text) else 0.0
        relevance_penalty = (
            0.25
            if question.strip()
            and question_overlap < 0.02
            and total_signal_hits == 0
            and structured_steps == 0
            and char_count >= 18
            else 0.0
        )
        common_base = min(0.7, char_count / 80.0) + complexity_bonus

        if relevance_penalty > 0:
            deductions.append("low_relevance")
        if refusal_penalty > 0:
            deductions.append("refusal_or_non_answer")
        if prompt_injection_penalty > 0:
            deductions.append("meta_prompt_attempt")

        for dimension in DIMENSIONS:
            hit_count = hit_counts[dimension]
            structure_bonus = 0.0
            if structured_steps >= 2:
                if dimension == "plan":
                    structure_bonus = 0.25
                elif dimension in {"monitor", "evaluate"}:
                    structure_bonus = 0.1
            score = (
                common_base
                + hit_count * 0.7
                + (0.15 if hit_count > 0 and question_overlap >= 0.18 else 0.0)
                + structure_bonus
                + self.dimension_bias.get(dimension, 0.0)
                - self.strictness
                - refusal_penalty
                - relevance_penalty
                - prompt_injection_penalty
            )
            dimensions[dimension] = round(self._clamp(score, 0.0, 3.0), 2)
            evidence[dimension] = self._extract_quote(text, lower_text, _SIGNALS[dimension])
            if hit_count == 0:
                deductions.append(f"weak_{dimension}_signal")

        confidence = self._estimate_confidence(
            semantic_token_count,
            dimensions,
            deductions,
            features,
            question_overlap,
            structured_steps,
        )

        return ScoreResult(
            judge_id=self.judge_id,
            dimensions=dimensions,
            confidence=confidence,
            deductions=deductions,
            evidence=evidence,
            raw_response="heuristic_judge",
        )

    def _signal_hits(self, text: str, signals: list[str]) -> int:
        return sum(1 for signal in signals if signal and signal in text)

    def _question_overlap(self, answer: str, question: str) -> float:
        if not question.strip():
            return 0.0
        answer_tokens = _semantic_tokens(answer)
        question_tokens = _semantic_tokens(question)
        if not answer_tokens or not question_tokens:
            return 0.0
        overlap = len(answer_tokens & question_tokens) / max(len(question_tokens), 1)
        return self._clamp(overlap, 0.0, 1.0)

    def _estimate_confidence(
        self,
        semantic_token_count: int,
        dimensions: dict[str, float],
        deductions: list[str],
        features: dict[str, Any] | None,
        question_overlap: float,
        structured_steps: int,
    ) -> float:
        density = min(1.0, semantic_token_count / 24.0)
        consistency = 1.0 - (max(dimensions.values()) - min(dimensions.values())) / 3.0
        weak_signal_count = sum(1 for item in deductions if item.startswith("weak_"))
        penalty = min(0.75, weak_signal_count * 0.09)
        if "low_relevance" in deductions:
            penalty += 0.12
        if "refusal_or_non_answer" in deductions:
            penalty += 0.15
        if "meta_prompt_attempt" in deductions:
            penalty += 0.1
        feature_bonus = 0.0
        if features:
            feature_bonus = 0.03
        structure_confidence_bonus = 0.06 if structured_steps >= 2 else 0.0
        confidence = (
            0.22
            + density * 0.25
            + consistency * 0.2
            + min(1.0, question_overlap * 1.5) * 0.3
            + structure_confidence_bonus
            + feature_bonus
            - penalty
        )
        return round(self._clamp(confidence, 0.0, 1.0), 2)

    def _extract_quote(self, text: str, lower_text: str, signals: list[str]) -> str:
        for signal in signals:
            idx = lower_text.find(signal)
            if idx == -1:
                continue
            start = max(0, idx - 18)
            end = min(len(text), idx + len(signal) + 18)
            quote = text[start:end].strip()
            if quote:
                return quote
        return text[:80].strip()

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _refusal_penalty(self, lower_text: str) -> float:
        strong_patterns = (
            "拒绝回答",
            "不回答",
            "不知道",
            "不会",
            "结束吧",
            "不想回答",
            "没法回答",
        )
        weak_patterns = ("随便猜", "无聊", "不确定", "先这么猜", "不太确定")
        if self._contains_any(lower_text, strong_patterns):
            return 0.75
        if self._contains_any(lower_text, weak_patterns):
            return 0.45
        return 0.0

    def _looks_prompt_injection(self, lower_text: str) -> bool:
        patterns = (
            "提示词",
            "系统提示",
            "评分规则",
            "隐藏指令",
            "system prompt",
            "ignore previous",
            "prompt injection",
        )
        return self._contains_any(lower_text, patterns)

    def _contains_any(self, text: str, patterns: tuple[str, ...]) -> bool:
        return any(pattern in text for pattern in patterns)

    def _structured_steps(self, lower_text: str) -> int:
        markers = ("第一步", "第二步", "第三步", "先", "再", "然后", "最后")
        return sum(1 for marker in markers if marker in lower_text)


def _semantic_tokens(text: str) -> set[str]:
    tokens: set[str] = {match.group(0) for match in _LATIN_TOKEN_RE.finditer(text)}
    for seq in _CJK_SEQ_RE.findall(text):
        if len(seq) < 2:
            continue
        if len(seq) == 2:
            tokens.add(seq)
            continue
        for idx in range(len(seq) - 1):
            tokens.add(seq[idx : idx + 2])
    return tokens


def build_default_judges() -> list[HeuristicJudge]:
    return [
        HeuristicJudge(
            "judge_structure",
            dimension_bias={"plan": 0.15, "monitor": 0.1},
            strictness=0.05,
        ),
        HeuristicJudge("judge_evidence", dimension_bias={"evaluate": 0.2}, strictness=0.1),
        HeuristicJudge("judge_adapt", dimension_bias={"adapt": 0.2}, strictness=0.0),
    ]


def default_reason_for_dimension(dimension: str) -> str:
    return _DIMENSION_REASONS[dimension]
