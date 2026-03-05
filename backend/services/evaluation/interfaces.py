from __future__ import annotations

from typing import Any, Protocol

from services.evaluation.models import ScoreResult


class EvaluationJudge(Protocol):
    judge_id: str

    def invoke(
        self,
        answer: str,
        *,
        question: str = "",
        features: dict[str, Any] | None = None,
    ) -> ScoreResult:
        """Return one judge vote for the provided answer."""
