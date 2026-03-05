from services.evaluation.aggregator import ScoreAggregator
from services.evaluation.models import ScoreResult


def test_build_evidence_marks_weak_signal_reason() -> None:
    aggregator = ScoreAggregator()
    raw = [
        ScoreResult(
            judge_id="judge_test",
            dimensions={"plan": 0.2, "monitor": 0.2, "evaluate": 0.2, "adapt": 0.2},
            confidence=0.2,
            deductions=[
                "weak_plan_signal",
                "weak_monitor_signal",
                "weak_evaluate_signal",
                "weak_adapt_signal",
            ],
            evidence={},
        )
    ]

    evidence = aggregator._build_evidence("不知道。", raw)

    assert len(evidence) == 4
    assert all(item.reason.startswith("Weak explicit signal") for item in evidence)
