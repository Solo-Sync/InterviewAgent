from __future__ import annotations

import logging
from typing import Any

from libs.observability import log_event
from libs.schemas.base import (
    DimScores,
    EvaluationResult,
    EvidenceSpan,
    JudgeVote,
    MetacogDimension,
    ScaffoldLevel,
)
from services.evaluation.discount import DiscountPolicy
from services.evaluation.judges import (
    build_default_judges,
    build_turn_level_judges,
    default_reason_for_dimension,
)
from services.evaluation.interfaces import EvaluationJudge
from services.evaluation.models import DIMENSIONS, ScoreResult
from services.evaluation.result_aggregator import ResultAggregator
from services.evaluation.scorer import Scorer

_DIMENSION_TO_ENUM = {
    "plan": MetacogDimension.PLAN,
    "monitor": MetacogDimension.MONITOR,
    "evaluate": MetacogDimension.EVALUATE,
    "adapt": MetacogDimension.ADAPT,
}
logger = logging.getLogger(__name__)


class ScoreAggregator:
    def __init__(
        self,
        *,
        judge_mode: str = "llm",
        judges: list[EvaluationJudge] | None = None,
    ) -> None:
        if judges is None:
            if judge_mode == "turn_aux":
                judges = build_turn_level_judges()
            elif judge_mode == "llm":
                judges = build_default_judges()
            else:
                raise ValueError(f"unknown judge_mode: {judge_mode}")
        self.scorer = Scorer(judges)
        self.result_aggregator = ResultAggregator()
        self.discount_policy = DiscountPolicy()

    def score(
        self,
        text: str,
        *,
        question: str = "",
        features: dict[str, Any] | None = None,
        scaffold_level: ScaffoldLevel | None = None,
    ) -> EvaluationResult:
        raw_results = self.scorer.score(text, question=question, features=features)
        log_event(
            logger,
            logging.INFO,
            "evaluation_judge_votes_collected",
            question=question,
            answer=text,
            features=features or {},
            scaffold_level=scaffold_level.value if scaffold_level else None,
            judge_votes=[
                {
                    "judge_id": result.judge_id,
                    "dimensions": result.dimensions,
                    "confidence": result.confidence,
                    "deductions": result.deductions,
                    "evidence": result.evidence,
                    "raw_response": result.raw_response,
                }
                for result in raw_results
            ],
        )
        aggregated = self.result_aggregator.aggregate(raw_results)

        base_scores = self._to_dim_scores(aggregated.dimensions)
        discounts = self.discount_policy.build(scaffold_level)
        final_scores = self.discount_policy.apply(base_scores, discounts)
        evidence = self._build_evidence(text, raw_results)
        judge_votes = [
            JudgeVote(
                judge_id=result.judge_id,
                scores=self._to_dim_scores(result.dimensions),
                confidence=max(0.0, min(1.0, result.confidence)),
            )
            for result in raw_results
        ]
        confidence_penalty = aggregated.global_disagreement * 0.05
        final_confidence = round(max(0.0, min(1.0, aggregated.confidence - confidence_penalty)), 2)

        result = EvaluationResult(
            scores=final_scores,
            evidence=evidence,
            judge_votes=judge_votes,
            final_confidence=final_confidence,
            discounts=discounts or None,
        )
        log_event(
            logger,
            logging.INFO,
            "evaluation_aggregated",
            aggregated_dimensions=aggregated.dimensions,
            aggregated_confidence=aggregated.confidence,
            global_disagreement=aggregated.global_disagreement,
            discounts=[discount.model_dump(mode="json") for discount in discounts],
            final_scores=result.scores.model_dump(mode="json"),
            evidence=[item.model_dump(mode="json") for item in result.evidence or []],
            final_confidence=result.final_confidence,
        )
        return result

    def _to_dim_scores(self, dims: dict[str, float]) -> DimScores:
        return DimScores(
            plan=round(self._clamp(dims.get("plan", 0.0), 0.0, 3.0), 2),
            monitor=round(self._clamp(dims.get("monitor", 0.0), 0.0, 3.0), 2),
            evaluate=round(self._clamp(dims.get("evaluate", 0.0), 0.0, 3.0), 2),
            adapt=round(self._clamp(dims.get("adapt", 0.0), 0.0, 3.0), 2),
        )

    def _build_evidence(self, text: str, raw_results: list[ScoreResult]) -> list[EvidenceSpan]:
        items: list[EvidenceSpan] = []
        source_text = (text or "").strip()
        for dimension in DIMENSIONS:
            quote = self._pick_quote(dimension, raw_results, source_text)
            start, end = self._locate_quote(source_text, quote)
            items.append(
                EvidenceSpan(
                    dimension=_DIMENSION_TO_ENUM[dimension],
                    quote=quote,
                    start=start,
                    end=end,
                    reason=self._reason_for_dimension(dimension, raw_results),
                )
            )
        return items

    def _pick_quote(self, dimension: str, raw_results: list[ScoreResult], text: str) -> str:
        candidates = [result.evidence.get(dimension, "").strip() for result in raw_results]
        candidates = [item for item in candidates if item]
        if candidates:
            candidates.sort(key=len, reverse=True)
            return candidates[0][:120]
        return text[:120]

    def _locate_quote(self, text: str, quote: str) -> tuple[int | None, int | None]:
        if not text or not quote:
            return None, None
        idx = text.find(quote)
        if idx == -1:
            return None, None
        return idx, idx + len(quote)

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _reason_for_dimension(self, dimension: str, raw_results: list[ScoreResult]) -> str:
        weak_flag = f"weak_{dimension}_signal"
        if raw_results and all(weak_flag in result.deductions for result in raw_results):
            return "Weak explicit signal in the answer; evidence is contextual and low-confidence."
        return default_reason_for_dimension(dimension)
