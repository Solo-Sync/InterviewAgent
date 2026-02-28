from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.main import app

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


def test_evaluation_score_route_returns_full_contract_shape() -> None:
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


def test_evaluation_score_route_applies_scaffold_discount() -> None:
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


def test_evaluation_batch_score_route_returns_stats() -> None:
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
