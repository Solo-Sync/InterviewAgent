from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.dependencies import orchestrator
from apps.api.main import app
from libs.schemas.base import NextActionType
from services.orchestrator.next_action_decider import NextActionDecision


def _headers(role: AuthRole, *, subject: str, candidate_id: str | None = None) -> dict[str, str]:
    token, _ = issue_access_token(subject=subject, role=role, candidate_id=candidate_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _mock_llm_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orchestrator.next_action_decider,
        "decide",
        lambda *args, **kwargs: NextActionDecision(  # noqa: ARG005
            action_type=NextActionType.ASK,
            interviewer_reply="请继续说明你的思路。",
            reasons=("继续",),
        ),
    )


def test_admin_session_list_returns_real_backend_sessions() -> None:
    client = TestClient(app)
    client.headers.update(
        _headers(
            AuthRole.CANDIDATE,
            subject="real-flow-list@example.com",
            candidate_id="cand_admin_list",
        )
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "cand_admin_list", "display_name": "Admin List Candidate"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    session_id = create_resp.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "我会先定义约束，再逐步估算。"}},
    )
    assert turn_resp.status_code == 200

    end_resp = client.post(f"/api/v1/sessions/{session_id}/end", json={"reason": "completed"})
    assert end_resp.status_code == 200

    client.headers.clear()
    client.headers.update(_headers(AuthRole.ADMIN, subject="admin@company.com"))
    resp = client.get("/api/v1/admin/sessions")

    assert resp.status_code == 200
    payload = resp.json()["data"]["items"]
    item = next(entry for entry in payload if entry["session"]["session_id"] == session_id)
    assert item["session"]["candidate"]["candidate_id"] == "cand_admin_list"
    assert item["turn_count"] == 1
    assert item["report"] is not None


def test_admin_session_detail_returns_transcript_and_report() -> None:
    client = TestClient(app)
    client.headers.update(
        _headers(
            AuthRole.CANDIDATE,
            subject="real-flow-detail@example.com",
            candidate_id="cand_admin_detail",
        )
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "cand_admin_detail", "display_name": "Admin Detail Candidate"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    opening_prompt = create_resp.json()["data"]["next_action"]["text"]
    session_id = create_resp.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "我先拆问题，再做数量级估算。"}},
    )
    assert turn_resp.status_code == 200

    end_resp = client.post(f"/api/v1/sessions/{session_id}/end", json={"reason": "completed"})
    assert end_resp.status_code == 200

    client.headers.clear()
    client.headers.update(_headers(AuthRole.ADMIN, subject="admin@company.com"))
    resp = client.get(f"/api/v1/admin/sessions/{session_id}")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["session"]["session_id"] == session_id
    assert payload["opening_prompt"] == opening_prompt
    assert payload["turns"][0]["input"]["text"] == "我先拆问题，再做数量级估算。"
    assert payload["report"] is not None
