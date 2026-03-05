from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.main import app
from apps.api.routers import evaluation as evaluation_router
from libs.schemas.base import (
    DimScores,
    Discount,
    EvaluationResult,
    EvidenceSpan,
    JudgeVote,
    MetacogDimension,
)

AUTH_HEADERS = {"Authorization": f"Bearer {issue_access_token(subject='admin@company.com', role=AuthRole.ADMIN)[0]}"}


def _score_payload(scaffold_used: dict | None = None) -> dict:
    payload = {
        "rubric_id": "rubric_v1",
        "question": "如何估算一座城市一天卖出多少杯奶茶？",
        "answer_clean_text": "我先定义范围，再拆分人群和时段，随后检查假设并做交叉验证。",
    }
    if scaffold_used is not None:
        payload["scaffold_used"] = scaffold_used
    return payload


def _fake_evaluation(*, discounted: bool = False) -> EvaluationResult:
    monitor_score = 2.1 if discounted else 2.6
    evaluate_score = 2.3 if discounted else 2.8
    discounts = None
    if discounted:
        discounts = [
            Discount(
                reason="scaffold_l2_discount",
                dimension=MetacogDimension.MONITOR,
                multiplier=0.8,
            ),
            Discount(
                reason="scaffold_l2_discount",
                dimension=MetacogDimension.EVALUATE,
                multiplier=0.8,
            ),
        ]

    return EvaluationResult(
        scores=DimScores(
            plan=2.7,
            monitor=monitor_score,
            evaluate=evaluate_score,
            adapt=1.9,
        ),
        evidence=[
            EvidenceSpan(
                dimension=MetacogDimension.PLAN,
                quote="我先定义范围",
                start=0,
                end=6,
                reason="Shows decomposition or explicit planning steps.",
            ),
            EvidenceSpan(
                dimension=MetacogDimension.MONITOR,
                quote="随后检查假设",
                start=15,
                end=21,
                reason="Shows active checking, correction, or control of the process.",
            ),
            EvidenceSpan(
                dimension=MetacogDimension.EVALUATE,
                quote="做交叉验证",
                start=22,
                end=27,
                reason="Shows verification or quality judgment using evidence/comparison.",
            ),
            EvidenceSpan(
                dimension=MetacogDimension.ADAPT,
                quote="再拆分人群和时段",
                start=7,
                end=15,
                reason="Shows strategy adjustment under changed constraints.",
            ),
        ],
        judge_votes=[
            JudgeVote(
                judge_id="judge_llm_1",
                scores=DimScores(plan=2.8, monitor=2.7, evaluate=2.8, adapt=1.8),
                confidence=0.82,
            ),
            JudgeVote(
                judge_id="judge_llm_2",
                scores=DimScores(plan=2.6, monitor=2.5, evaluate=2.9, adapt=1.9),
                confidence=0.79,
            ),
            JudgeVote(
                judge_id="judge_llm_3",
                scores=DimScores(plan=2.7, monitor=2.6, evaluate=2.7, adapt=2.0),
                confidence=0.81,
            ),
        ],
        final_confidence=0.8,
        discounts=discounts,
    )


def test_evaluation_score_route_returns_full_contract_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluation_router.aggregator,
        "score",
        lambda *args, **kwargs: _fake_evaluation(discounted=False),
    )
    client = TestClient(app)
    client.headers.update(AUTH_HEADERS)

    resp = client.post("/api/v1/evaluation/score", json=_score_payload())
    assert resp.status_code == 200
    evaluation = resp.json()["data"]["evaluation"]
    assert set(evaluation["scores"].keys()) == {"plan", "monitor", "evaluate", "adapt"}
    assert len(evaluation["judge_votes"]) == 3
    assert len(evaluation["evidence"]) == 4
    for dim in ("plan", "monitor", "evaluate", "adapt"):
        assert 0 <= evaluation["scores"][dim] <= 3


def test_evaluation_score_route_applies_scaffold_discount(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluation_router.aggregator,
        "score",
        lambda *args, **kwargs: _fake_evaluation(
            discounted=kwargs.get("scaffold_level") is not None
        ),
    )
    client = TestClient(app)
    client.headers.update(AUTH_HEADERS)

    baseline_resp = client.post("/api/v1/evaluation/score", json=_score_payload())
    baseline = baseline_resp.json()["data"]["evaluation"]
    discounted = client.post(
        "/api/v1/evaluation/score",
        json=_score_payload(scaffold_used={"used": True, "level": "L2"}),
    ).json()["data"]["evaluation"]

    assert discounted["scores"]["monitor"] <= baseline["scores"]["monitor"]
    assert discounted["scores"]["evaluate"] <= baseline["scores"]["evaluate"]
    assert discounted["discounts"] is not None


def test_evaluation_batch_score_route_returns_stats(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluation_router.aggregator,
        "score",
        lambda *args, **kwargs: _fake_evaluation(discounted=False),
    )
    client = TestClient(app)
    client.headers.update(AUTH_HEADERS)

    resp = client.post(
        "/api/v1/evaluation/batch_score",
        json={"items": [_score_payload(), _score_payload()]},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["stats"]["count"] == 2
    assert len(payload["items"]) == 2
