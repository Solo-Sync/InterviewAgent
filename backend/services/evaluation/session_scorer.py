from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from libs.llm_gateway.client import LLMGateway
from libs.observability import log_event
from libs.readiness import ReadinessProbe
from libs.schemas.base import DimScores, Turn

logger = logging.getLogger(__name__)

_SIGNAL_TERMS = (
    "目标",
    "计划",
    "步骤",
    "拆分",
    "假设",
    "检查",
    "验证",
    "对比",
    "证据",
    "如果",
    "调整",
    "适应",
    "plan",
    "monitor",
    "evaluate",
    "adapt",
    "step",
    "check",
    "validate",
    "compare",
    "fallback",
)
_SIGNAL_TERMS_SORTED = sorted(_SIGNAL_TERMS, key=len, reverse=True)
_REFUSAL_PATTERNS = (
    "不知道",
    "不太会",
    "答不出来",
    "不想答",
    "拒绝回答",
    "跳过",
    "结束",
    "抱歉",
)
_TOKEN_RE = re.compile(r"[0-9A-Za-z_]{2,}|[\u4e00-\u9fff]+")
_NON_SEMANTIC_RE = re.compile(r"[\s,.;:!?，。；：！？、*\\-_/]+")


@dataclass(slots=True)
class SessionScoreResult:
    scores: DimScores
    confidence: float | None
    source: str
    notes: list[str]


class SessionScorer:
    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        allow_test_mode_llm: bool = False,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.model = (
            model
            or os.getenv("SESSION_EVAL_MODEL")
            or os.getenv("LLM_MODEL_NAME")
            or os.getenv("LLM_GATEWAY_MODEL")
            or "qwen-plus"
        )
        self.timeout_s = timeout_s if timeout_s is not None else float(os.getenv("SESSION_EVAL_TIMEOUT_S", "20"))
        self.allow_test_mode_llm = allow_test_mode_llm

    def score_session(self, turns: list[Turn]) -> SessionScoreResult:
        if not turns:
            return self._fallback(turns, reason="empty_session")

        if "PYTEST_CURRENT_TEST" in os.environ and not self.allow_test_mode_llm:
            return self._fallback(turns, reason="pytest_mode")

        readiness = self.gateway.readiness()
        if readiness.status != "ready":
            return self._fallback(
                turns,
                reason=f"gateway_not_ready:{readiness.status}",
                readiness=readiness,
            )

        prompt = self._build_prompt(turns)
        log_event(
            logger,
            logging.INFO,
            "session_scorer_started",
            model=self.model,
            timeout_s=self.timeout_s,
            turns=len(turns),
        )
        try:
            raw = self.gateway.complete_sync(self.model, prompt, timeout_s=self.timeout_s)
        except Exception as exc:  # noqa: BLE001
            return self._fallback(turns, reason=f"llm_call_error:{exc.__class__.__name__}")

        content = raw.get("content")
        if not isinstance(content, str) or not content.strip():
            return self._fallback(turns, reason="llm_empty_content")

        try:
            payload = self._parse_payload(content)
            scores = self._extract_scores(payload)
            confidence = self._extract_confidence(payload.get("confidence"))
            summary = str(payload.get("summary", "")).strip()
            notes = ["session_score_source:llm", f"session_score_confidence:{confidence:.2f}"]
            if summary:
                notes.append(f"session_score_summary:{summary[:180]}")
            scores, guard_notes = self._apply_post_guards(scores, turns)
            notes.extend(guard_notes)
            return SessionScoreResult(
                scores=scores,
                confidence=confidence,
                source="llm",
                notes=notes,
            )
        except Exception as exc:  # noqa: BLE001
            return self._fallback(turns, reason=f"llm_parse_error:{exc.__class__.__name__}")

    def _build_prompt(self, turns: list[Turn]) -> str:
        lines: list[str] = []
        for turn in turns:
            question = turn.question.text if turn.question and turn.question.text else "(no question)"
            answer = (
                turn.preprocess.clean_text
                if turn.preprocess and turn.preprocess.clean_text
                else str(turn.input.text or "")
            )
            scaffold_prompt = (
                turn.scaffold.prompt if turn.scaffold and turn.scaffold.fired and turn.scaffold.prompt else None
            )
            lines.append(f"Turn {turn.turn_index + 1}")
            lines.append(f"Q: {question[:220]}")
            lines.append(f"A: {answer[:280]}")
            if scaffold_prompt:
                lines.append(f"Scaffold: {scaffold_prompt[:220]}")
            lines.append("")

        transcript = "\n".join(lines).strip()
        return (
            "你是面试质量评分器。请对整场对话进行一次性评分，不要按单轮平均。\n"
            "重点关注：方法完整性、一致性、反思校验能力、在约束变化下的调整能力。\n"
            "对拒答、跑题、提示词探测、关键词堆砌应显著扣分。\n"
            "仅输出 JSON：\n"
            "{\n"
            '  "dimension_scores": {"plan": 0-3, "monitor": 0-3, "evaluate": 0-3, "adapt": 0-3},\n'
            '  "confidence": 0-1,\n'
            '  "summary": "一句话总结"\n'
            "}\n"
            f"对话如下：\n{transcript}"
        )

    def _parse_payload(self, content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no_json_object")
        payload = json.loads(content[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("payload_not_object")
        return payload

    def _extract_scores(self, payload: dict[str, Any]) -> DimScores:
        values = payload.get("dimension_scores") or payload.get("scores") or {}
        if not isinstance(values, dict):
            raise ValueError("dimension_scores_not_object")
        return DimScores(
            plan=self._score(values, "plan"),
            monitor=self._score(values, "monitor"),
            evaluate=self._score(values, "evaluate"),
            adapt=self._score(values, "adapt"),
        )

    def _score(self, payload: dict[str, Any], key: str) -> float:
        raw = payload.get(key, 0.0)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        return round(max(0.0, min(3.0, value)), 2)

    def _extract_confidence(self, value: Any) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 2)
        except (TypeError, ValueError):
            return 0.0

    def _fallback(
        self,
        turns: list[Turn],
        *,
        reason: str,
        readiness: ReadinessProbe | None = None,
    ) -> SessionScoreResult:
        votes = [turn.evaluation.scores for turn in turns if turn.evaluation is not None]
        if not votes:
            scores = DimScores(plan=0.0, monitor=0.0, evaluate=0.0, adapt=0.0)
        else:
            count = len(votes)
            scores = DimScores(
                plan=round(sum(item.plan for item in votes) / count, 2),
                monitor=round(sum(item.monitor for item in votes) / count, 2),
                evaluate=round(sum(item.evaluate for item in votes) / count, 2),
                adapt=round(sum(item.adapt for item in votes) / count, 2),
            )

        notes = [f"session_score_source:fallback_turn_mean", f"session_score_fallback_reason:{reason}"]
        if readiness and readiness.detail:
            notes.append(f"session_score_gateway_detail:{readiness.detail[:180]}")
        scores, guard_notes = self._apply_post_guards(scores, turns)
        notes.extend(guard_notes)
        return SessionScoreResult(
            scores=scores,
            confidence=None,
            source="fallback_turn_mean",
            notes=notes,
        )

    def _apply_post_guards(self, scores: DimScores, turns: list[Turn]) -> tuple[DimScores, list[str]]:
        guarded = scores
        notes: list[str] = []
        if self._is_refusal_dominant(turns):
            guarded = self._cap_all(guarded, 0.2)
            notes.append("session_score_guard:refusal_dominant_cap")
        if self._is_keyword_stuffing_dominant(turns):
            guarded = self._cap_all(guarded, 0.8)
            notes.append("session_score_guard:keyword_stuffing_cap")
        return guarded, notes

    def _cap_all(self, scores: DimScores, cap: float) -> DimScores:
        return DimScores(
            plan=round(min(scores.plan, cap), 2),
            monitor=round(min(scores.monitor, cap), 2),
            evaluate=round(min(scores.evaluate, cap), 2),
            adapt=round(min(scores.adapt, cap), 2),
        )

    def _is_refusal_dominant(self, turns: list[Turn]) -> bool:
        if not turns:
            return False
        refusal_hits = 0
        for turn in turns:
            answer = self._turn_answer(turn)
            if any(pattern in answer for pattern in _REFUSAL_PATTERNS):
                refusal_hits += 1
        return refusal_hits / len(turns) >= 0.5

    def _is_keyword_stuffing_dominant(self, turns: list[Turn]) -> bool:
        if not turns:
            return False
        stuffing_hits = 0
        for turn in turns:
            answer = self._turn_answer(turn)
            if len(answer) < 12:
                continue
            token_count = len(_TOKEN_RE.findall(answer))
            if token_count <= 0:
                continue
            signal_hits = sum(1 for term in _SIGNAL_TERMS if term in answer)
            residual = answer
            for term in _SIGNAL_TERMS_SORTED:
                residual = residual.replace(term, " ")
            residual = _NON_SEMANTIC_RE.sub("", residual)
            if signal_hits >= 6 and len(residual) <= 4:
                stuffing_hits += 1
        return stuffing_hits / len(turns) >= 0.34

    def _turn_answer(self, turn: Turn) -> str:
        if turn.preprocess and turn.preprocess.clean_text:
            return turn.preprocess.clean_text.lower()
        return str(turn.input.text or "").lower()
