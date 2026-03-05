from __future__ import annotations

from typing import Any

from services.evaluation.interfaces import EvaluationJudge
from services.evaluation.models import DIMENSIONS, ScoreResult


class Scorer:
    def __init__(self, judges: list[EvaluationJudge]) -> None:
        if not judges:
            raise ValueError("at least one judge is required")
        self.judges = judges

    def score(
        self,
        answer: str,
        *,
        question: str = "",
        features: dict[str, Any] | None = None,
    ) -> list[ScoreResult]:
        results: list[ScoreResult] = []
        for judge in self.judges:
            try:
                result = judge.invoke(answer, question=question, features=features)
            except Exception as exc:  # noqa: BLE001
                result = ScoreResult(
                    judge_id=getattr(judge, "judge_id", "judge_unknown"),
                    dimensions={dim: 0.0 for dim in DIMENSIONS},
                    confidence=0.0,
                    deductions=[f"judge_error:{exc.__class__.__name__}"],
                    evidence={},
                )
            results.append(result)
        return results
