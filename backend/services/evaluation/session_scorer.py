from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import mean
from typing import Any

from libs.llm_gateway.client import LLMGateway
from libs.observability import log_event
from libs.readiness import ReadinessProbe
from libs.schemas.base import DimScores, Turn

logger = logging.getLogger(__name__)

_DIMENSIONS = ("plan", "monitor", "evaluate", "adapt")
_DIMENSION_LABELS = {
    "plan": "planning",
    "monitor": "monitoring",
    "evaluate": "evaluating",
    "adapt": "adaptating",
}

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
        runs_per_dimension: int = 3,
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
        self.runs_per_dimension = max(1, runs_per_dimension)

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

        try:
            ensemble = self._run_dimension_ensemble(turns)
        except Exception as exc:  # noqa: BLE001
            return self._fallback(turns, reason=f"llm_call_error:{exc.__class__.__name__}")

        if not ensemble["complete"]:
            return self._fallback(turns, reason="llm_ensemble_incomplete")

        scores = DimScores(
            plan=ensemble["scores"]["plan"],
            monitor=ensemble["scores"]["monitor"],
            evaluate=ensemble["scores"]["evaluate"],
            adapt=ensemble["scores"]["adapt"],
        )
        notes = [
            "session_score_source:llm_dimension_ensemble",
            f"session_score_call_success:{ensemble['success_calls']}/{ensemble['total_calls']}",
            *ensemble["dimension_notes"],
        ]
        if ensemble["confidence"] is not None:
            notes.append(f"session_score_confidence:{ensemble['confidence']:.2f}")

        scores, guard_notes = self._apply_post_guards(scores, turns)
        notes.extend(guard_notes)
        return SessionScoreResult(
            scores=scores,
            confidence=ensemble["confidence"],
            source="llm_dimension_ensemble",
            notes=notes,
        )

    def _run_dimension_ensemble(self, turns: list[Turn]) -> dict[str, Any]:
        coro = self._run_dimension_ensemble_async(turns)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    async def _run_dimension_ensemble_async(self, turns: list[Turn]) -> dict[str, Any]:
        transcript = self._build_transcript(turns)
        total_calls = len(_DIMENSIONS) * self.runs_per_dimension
        log_event(
            logger,
            logging.INFO,
            "session_scorer_started",
            model=self.model,
            timeout_s=self.timeout_s,
            turns=len(turns),
            mode="dimension_ensemble",
            runs_per_dimension=self.runs_per_dimension,
            total_calls=total_calls,
        )

        tasks = []
        for dimension in _DIMENSIONS:
            for attempt in range(1, self.runs_per_dimension + 1):
                prompt = self._build_dimension_prompt(transcript, dimension=dimension, attempt=attempt)
                tasks.append(self._score_one_call(dimension=dimension, attempt=attempt, prompt=prompt))

        raw = await asyncio.gather(*tasks, return_exceptions=True)
        dimension_votes: dict[str, list[float]] = {dimension: [] for dimension in _DIMENSIONS}
        confidences: list[float] = []
        success_calls = 0
        failed_calls = 0

        for item in raw:
            if isinstance(item, Exception):
                failed_calls += 1
                continue
            dimension, score, confidence = item
            if score is None:
                failed_calls += 1
                continue
            dimension_votes[dimension].append(score)
            success_calls += 1
            if confidence is not None:
                confidences.append(confidence)

        complete = all(len(dimension_votes[dimension]) == self.runs_per_dimension for dimension in _DIMENSIONS)
        if not complete:
            return {
                "complete": False,
                "scores": {},
                "confidence": None,
                "success_calls": success_calls,
                "failed_calls": failed_calls,
                "total_calls": total_calls,
                "dimension_notes": ["session_score_ensemble_incomplete"],
            }

        scores = {
            dimension: round(mean(votes), 2)
            for dimension, votes in dimension_votes.items()
        }
        confidence = round(mean(confidences), 2) if confidences else None
        dimension_notes = [
            f"session_score_votes:{dimension}:{len(dimension_votes[dimension])}"
            for dimension in _DIMENSIONS
        ]
        return {
            "complete": True,
            "scores": scores,
            "confidence": confidence,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "total_calls": total_calls,
            "dimension_notes": dimension_notes,
        }

    async def _score_one_call(
        self,
        *,
        dimension: str,
        attempt: int,
        prompt: str,
    ) -> tuple[str, float | None, float | None]:
        if hasattr(self.gateway, "complete"):
            raw = await self.gateway.complete(self.model, prompt, timeout_s=self.timeout_s)
        else:
            raw = await asyncio.to_thread(self.gateway.complete_sync, self.model, prompt, self.timeout_s)

        content = raw.get("content") if isinstance(raw, dict) else None
        if not isinstance(content, str) or not content.strip():
            return dimension, None, None

        payload = self._parse_payload(content)
        score = self._extract_dimension_score(payload, dimension)
        confidence = self._extract_confidence(payload.get("confidence"))
        return dimension, score, confidence

    def _build_transcript(self, turns: list[Turn]) -> str:
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
        return "\n".join(lines).strip()

    def _build_dimension_prompt(self, transcript: str, *, dimension: str, attempt: int) -> str:
        label = _DIMENSION_LABELS[dimension]
        return (
            "你是面试质量评分器。你只能评估一个能力维度，禁止评价其它维度。\n"
            f"Dimension key: {dimension}\n"
            f"Dimension label: {label}\n"
            f"Attempt: {attempt}\n"
            "评分范围 0~3。\n"
            "请只返回 JSON："
            '{"dimension":"<dimension key>","score":0-3,"confidence":0-1,"reason":"一句话"}\n'
            "如果对话主要是拒答、跑题、提示词探测或关键词堆砌，请严格扣分。\n"
            f"Conversation transcript:\n{transcript}"
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

    def _extract_dimension_score(self, payload: dict[str, Any], dimension: str) -> float:
        # Preferred: single-dimension output.
        for key in (
            "score",
            dimension,
            f"{dimension}_score",
            _DIMENSION_LABELS[dimension],
            f"{_DIMENSION_LABELS[dimension]}_score",
        ):
            if key not in payload:
                continue
            try:
                value = float(payload[key])
                return round(max(0.0, min(3.0, value)), 2)
            except (TypeError, ValueError):
                continue

        # Compatible: nested dimension_scores map.
        dim_map = payload.get("dimension_scores") or payload.get("scores")
        if isinstance(dim_map, dict):
            try:
                value = float(dim_map.get(dimension, 0.0))
                return round(max(0.0, min(3.0, value)), 2)
            except (TypeError, ValueError):
                pass

        raise ValueError("missing_dimension_score")

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
