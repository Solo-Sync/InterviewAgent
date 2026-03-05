from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median

from services.evaluation.models import DIMENSIONS, AggregatedResult, ScoreResult


class ResultAggregator:
    def __init__(
        self,
        *,
        dimension_agg: str = "median",
        confidence_agg: str = "median",
        disagreement_metric: str = "iqr",
        alert_config: dict[str, float] | None = None,
    ) -> None:
        self.dimension_agg = dimension_agg
        self.confidence_agg = confidence_agg
        self.disagreement_metric = disagreement_metric
        self.alert_config = alert_config or {
            "dimension_iqr_threshold": 1.0,
            "global_iqr_threshold": 0.8,
            "min_confidence": 0.55,
        }

    def aggregate(self, results: list[ScoreResult]) -> AggregatedResult:
        if not results:
            raise ValueError("results cannot be empty")

        by_dimension: dict[str, list[float]] = defaultdict(list)
        for result in results:
            for dimension in DIMENSIONS:
                by_dimension[dimension].append(float(result.dimensions.get(dimension, 0.0)))

        dimensions: dict[str, float] = {}
        for dimension, values in by_dimension.items():
            dimensions[dimension] = mean(values) if self.dimension_agg == "mean" else median(values)

        confidences = [self._clamp_confidence(result.confidence) for result in results]
        confidence = mean(confidences) if self.confidence_agg == "mean" else median(confidences)

        deductions = self._dedupe([item for result in results for item in result.deductions])

        disagreement: dict[str, float] = {}
        spread_values: list[float] = []
        for dimension, values in by_dimension.items():
            spread = self._spread(values)
            disagreement[dimension] = spread
            spread_values.append(spread)
        global_disagreement = mean(spread_values) if spread_values else 0.0

        alert = False
        reasons: list[str] = []
        for dimension, spread in disagreement.items():
            if spread > self.alert_config["dimension_iqr_threshold"]:
                alert = True
                reasons.append(f"high_disagreement:{dimension}:{spread:.2f}")
        if global_disagreement > self.alert_config["global_iqr_threshold"]:
            alert = True
            reasons.append(f"high_disagreement:global:{global_disagreement:.2f}")
        if confidence < self.alert_config["min_confidence"]:
            alert = True
            reasons.append(f"low_confidence:{confidence:.2f}")

        return AggregatedResult(
            dimensions=dimensions,
            confidence=confidence,
            deductions=deductions,
            disagreement=disagreement,
            global_disagreement=global_disagreement,
            alert=alert,
            alert_reasons=reasons,
            raw_results=results,
        )

    def _spread(self, values: list[float]) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return 0.0
        if self.disagreement_metric == "std":
            avg = mean(values)
            variance = mean((value - avg) ** 2 for value in values)
            return math.sqrt(variance)
        if self.disagreement_metric == "range":
            return max(values) - min(values)
        q1 = self._percentile(values, 25)
        q3 = self._percentile(values, 75)
        return q3 - q1

    def _percentile(self, values: list[float], percentile_value: float) -> float:
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * (percentile_value / 100.0)
        low = math.floor(rank)
        high = math.ceil(rank)
        if low == high:
            return ordered[low]
        low_value = ordered[low]
        high_value = ordered[high]
        return low_value + (high_value - low_value) * (rank - low)

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _clamp_confidence(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))
