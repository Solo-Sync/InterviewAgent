from __future__ import annotations

import json
import logging
import os
from time import perf_counter
from typing import Any

from libs.llm_gateway.client import LLMGateway
from libs.observability import log_event
from services.evaluation.judges.heuristic import HeuristicJudge
from services.evaluation.models import DIMENSIONS, ScoreResult

_DIMENSION_REASONS = {
    "plan": "Shows decomposition or explicit planning steps.",
    "monitor": "Shows active checking, correction, or control of the process.",
    "evaluate": "Shows verification or quality judgment using evidence/comparison.",
    "adapt": "Shows strategy adjustment under changed constraints.",
}

_DIMENSION_ALIASES = {
    "plan": ["plan", "planning"],
    "monitor": ["monitor", "monitoring"],
    "evaluate": ["evaluate", "evaluation"],
    "adapt": ["adapt", "adaptability", "transfer"],
}

_DEFAULT_MODELS = ("eval-judge-a", "eval-judge-b", "eval-judge-c")
_SINGLE_MODEL_ENV_KEYS = ("LLM_MODEL_NAME", "ALIYUN_LLM_MODEL", "LLM_GATEWAY_MODEL")
logger = logging.getLogger(__name__)


class LLMJudge:
    def __init__(
        self,
        judge_id: str,
        model: str,
        *,
        gateway: LLMGateway,
        timeout_s: float = 3.0,
    ) -> None:
        self.judge_id = judge_id
        self.model = model
        self.gateway = gateway
        self.timeout_s = timeout_s
        self._fallback = HeuristicJudge(f"{judge_id}_fallback", strictness=0.25)

    def invoke(
        self,
        answer: str,
        *,
        question: str = "",
        features: dict[str, Any] | None = None,
    ) -> ScoreResult:
        started = perf_counter()
        prompt = self._build_prompt(answer=answer, question=question, features=features)
        log_event(
            logger,
            logging.INFO,
            "llm_judge_started",
            judge_id=self.judge_id,
            model=self.model,
            timeout_s=self.timeout_s,
            question=question,
            answer=answer,
            features=features or {},
            prompt=prompt,
        )
        try:
            raw = self.gateway.complete_sync(self.model, prompt, timeout_s=self.timeout_s)
        except Exception as exc:  # noqa: BLE001
            reason = f"llm_call_error:{exc.__class__.__name__}"
            log_event(
                logger,
                logging.WARNING,
                "llm_judge_gateway_error",
                judge_id=self.judge_id,
                model=self.model,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            return self._fallback_result(answer, question, features, reason=reason)

        content = raw.get("content")
        if not isinstance(content, str) or not content.strip():
            log_event(
                logger,
                logging.WARNING,
                "llm_judge_empty_content",
                judge_id=self.judge_id,
                model=self.model,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                raw=raw,
            )
            return self._fallback_result(answer, question, features, reason="llm_empty_content")

        try:
            payload = self._parse_payload(content)
            result = self._to_score_result(payload=payload, answer=answer, raw_content=content)
            log_event(
                logger,
                logging.INFO,
                "llm_judge_completed",
                judge_id=self.judge_id,
                model=self.model,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                llm_content=content,
                parsed_payload=payload,
                dimensions=result.dimensions,
                confidence=result.confidence,
                deductions=result.deductions,
                evidence=result.evidence,
            )
            return result
        except Exception:  # noqa: BLE001
            log_event(
                logger,
                logging.WARNING,
                "llm_judge_parse_error",
                judge_id=self.judge_id,
                model=self.model,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                llm_content=content,
            )
            return self._fallback_result(answer, question, features, reason="llm_parse_error")

    def _build_prompt(
        self,
        *,
        answer: str,
        question: str,
        features: dict[str, Any] | None,
    ) -> str:
        feature_block = json.dumps(features or {}, ensure_ascii=False)
        return (
            "请作为元认知评估评委，对候选人回答打分。输出必须是 JSON 对象，不要输出任何额外文本。\n"
            "评分维度: plan, monitor, evaluate, adapt，取值 0~3。\n"
            "必须包含字段:\n"
            "1) dimension_scores: 对象，4个维度分数\n"
            "2) confidence: 0~1\n"
            "3) deductions: 字符串数组\n"
            "4) evidence: 对象，4个维度对应引用原话片段\n"
            f"问题: {question or 'N/A'}\n"
            f"回答: {answer or ''}\n"
            f"特征: {feature_block}\n"
            "严格按 JSON 返回。"
        )

    def _parse_payload(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no json object found")
        parsed = json.loads(content[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("parsed payload must be object")
        return parsed

    def _to_score_result(
        self,
        *,
        payload: dict[str, Any],
        answer: str,
        raw_content: str,
    ) -> ScoreResult:
        dimensions_payload = payload.get("dimension_scores") or payload.get("dimensions") or {}
        if not isinstance(dimensions_payload, dict):
            raise ValueError("dimension_scores must be object")

        dimensions: dict[str, float] = {}
        for dimension in DIMENSIONS:
            dimensions[dimension] = self._extract_dimension_score(dimensions_payload, dimension)

        confidence = self._extract_confidence(payload.get("confidence"))
        deductions = payload.get("deductions")
        if not isinstance(deductions, list):
            deductions = []
        deductions = [str(item).strip() for item in deductions if str(item).strip()]

        evidence = self._extract_evidence(payload.get("evidence"), answer)

        return ScoreResult(
            judge_id=self.judge_id,
            dimensions=dimensions,
            confidence=confidence,
            deductions=deductions,
            evidence=evidence,
            raw_response=raw_content,
        )

    def _extract_dimension_score(self, payload: dict[str, Any], dimension: str) -> float:
        aliases = _DIMENSION_ALIASES[dimension]
        for key in aliases:
            if key not in payload:
                continue
            try:
                value = float(payload[key])
                return round(max(0.0, min(3.0, value)), 2)
            except (TypeError, ValueError):
                continue
        return 0.0

    def _extract_confidence(self, confidence: Any) -> float:
        if isinstance(confidence, dict):
            maybe = confidence.get("overall")
            try:
                return round(max(0.0, min(1.0, float(maybe))), 2)
            except (TypeError, ValueError):
                return 0.0
        try:
            return round(max(0.0, min(1.0, float(confidence))), 2)
        except (TypeError, ValueError):
            return 0.0

    def _extract_evidence(self, payload: Any, answer: str) -> dict[str, str]:
        default_quote = (answer or "").strip()[:80]
        evidence = {dimension: default_quote for dimension in DIMENSIONS}

        if isinstance(payload, dict):
            for dimension in DIMENSIONS:
                quote = payload.get(dimension)
                if quote is None:
                    for alias in _DIMENSION_ALIASES[dimension]:
                        if alias in payload:
                            quote = payload[alias]
                            break
                if isinstance(quote, str) and quote.strip():
                    evidence[dimension] = quote.strip()[:120]
            return evidence

        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                raw_dimension = str(item.get("dimension", "")).strip().lower()
                dimension = self._normalize_dimension(raw_dimension)
                if not dimension:
                    continue
                quote = item.get("quote")
                if isinstance(quote, str) and quote.strip():
                    evidence[dimension] = quote.strip()[:120]
        return evidence

    def _normalize_dimension(self, value: str) -> str | None:
        for dimension, aliases in _DIMENSION_ALIASES.items():
            if value in aliases:
                return dimension
        return None

    def _fallback_result(
        self,
        answer: str,
        question: str,
        features: dict[str, Any] | None,
        *,
        reason: str,
    ) -> ScoreResult:
        fallback = self._fallback.invoke(answer, question=question, features=features)
        degraded_dimensions = {
            dimension: round(max(0.0, min(3.0, score - 0.15)), 2)
            for dimension, score in fallback.dimensions.items()
        }
        degraded_confidence = round(max(0.0, min(1.0, fallback.confidence - 0.1)), 2)
        deductions = [reason, "llm_fallback_degraded", *fallback.deductions]
        result = ScoreResult(
            judge_id=self.judge_id,
            dimensions=degraded_dimensions,
            confidence=degraded_confidence,
            deductions=deductions,
            evidence=fallback.evidence,
            raw_response=fallback.raw_response,
        )
        log_event(
            logger,
            logging.WARNING,
            "llm_judge_fallback_used",
            judge_id=self.judge_id,
            model=self.model,
            fallback_reason=reason,
            dimensions=result.dimensions,
            confidence=result.confidence,
            deductions=result.deductions,
        )
        return result


def build_default_judges() -> list[LLMJudge | HeuristicJudge]:
    models = _resolve_models_from_env()
    if not models:
        models = list(_DEFAULT_MODELS)

    timeout_s = float(os.getenv("EVAL_JUDGE_TIMEOUT_S", "6.0"))
    gateway = LLMGateway()
    llm_judges: list[LLMJudge] = []
    for idx, model in enumerate(models[:3], start=1):
        judge_id = "judge_llm_primary" if idx == 1 and len(models) == 1 else f"judge_llm_{idx}"
        llm_judges.append(
            LLMJudge(
                judge_id=judge_id,
                model=model,
                gateway=gateway,
                timeout_s=timeout_s,
            )
        )

    if len(models) > 1:
        return llm_judges

    # Single-model setups are common in local/dev; add two deterministic heuristics
    # to keep multi-judge aggregation available even when LLM is slow or unavailable.
    return [
        llm_judges[0],
        HeuristicJudge(
            "judge_heuristic_structure",
            dimension_bias={"plan": 0.1, "monitor": 0.05},
            strictness=0.08,
        ),
        HeuristicJudge(
            "judge_heuristic_adapt",
            dimension_bias={"evaluate": 0.1, "adapt": 0.1},
            strictness=0.05,
        ),
    ]


def _resolve_models_from_env() -> list[str]:
    raw_models = os.getenv("EVAL_JUDGE_MODELS", "").strip()
    if raw_models:
        return [model.strip() for model in raw_models.split(",") if model.strip()]

    for key in _SINGLE_MODEL_ENV_KEYS:
        model = os.getenv(key, "").strip()
        if model:
            return [model]
    return []


def default_reason_for_dimension(dimension: str) -> str:
    return _DIMENSION_REASONS[dimension]
