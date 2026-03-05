from __future__ import annotations

from dataclasses import dataclass, field

DIMENSIONS = ("plan", "monitor", "evaluate", "adapt")


@dataclass(slots=True)
class ScoreResult:
    judge_id: str
    dimensions: dict[str, float]
    confidence: float
    deductions: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    raw_response: str | None = None


@dataclass(slots=True)
class AggregatedResult:
    dimensions: dict[str, float]
    confidence: float
    deductions: list[str]
    disagreement: dict[str, float]
    global_disagreement: float
    alert: bool
    alert_reasons: list[str] = field(default_factory=list)
    raw_results: list[ScoreResult] = field(default_factory=list)
