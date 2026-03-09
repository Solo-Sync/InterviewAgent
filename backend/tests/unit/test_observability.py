import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.dependencies import orchestrator
from apps.api.main import app
from apps.api.middleware import trace as trace_middleware
from apps.api.routers import health
from libs.observability import get_trace_id
from libs.schemas.base import NextActionType
from services.orchestrator.next_action_decider import NextActionDecision


def _candidate_headers(candidate_id: str = "cand_001") -> dict[str, str]:
    token, _ = issue_access_token(
        subject="candidate@example.com",
        role=AuthRole.CANDIDATE,
        candidate_id=candidate_id,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _mock_next_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orchestrator.next_action_decider,
        "decide",
        lambda *args, **kwargs: NextActionDecision(  # noqa: ARG005
            action_type=NextActionType.ASK,
            interviewer_reply="请继续说明你的思路。",
            reasons=("继续",),
        ),
    )


def test_unhandled_exception_logs_trace_id(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _boom():
        raise RuntimeError("boom")

    def _capture_exception(message: str, *args, **kwargs) -> None:
        captured["message"] = message
        captured["event_type"] = (kwargs.get("extra") or {}).get("event_type")
        captured["trace_id"] = get_trace_id()

    monkeypatch.setattr(trace_middleware.logger, "exception", _capture_exception)
    monkeypatch.setattr(health, "_get_llm_readiness", _boom)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/health")

    assert resp.status_code == 500
    trace_id = resp.json()["trace_id"]
    assert captured["message"] == "Unhandled exception"
    assert captured["event_type"] == "unhandled_exception"
    assert captured["trace_id"] == trace_id


def test_metrics_endpoint_exposes_request_and_turn_metrics() -> None:
    client = TestClient(app)
    client.headers.update(_candidate_headers())

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "cand_001", "display_name": "Candidate One"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "我先定义范围再估算结果。"}},
    )
    assert turn_resp.status_code == 200

    metrics_resp = client.get("/api/v1/metrics")

    assert metrics_resp.status_code == 200
    assert metrics_resp.headers["content-type"].startswith("text/plain")
    body = metrics_resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "turn_stage_latency_seconds" in body
    assert 'stage="preprocess"' in body
    assert 'stage="evaluation"' in body
    assert "turn_total_latency_seconds" in body
