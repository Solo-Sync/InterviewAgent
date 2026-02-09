from fastapi.testclient import TestClient

from apps.api.main import app


def test_session_turn_end_flow() -> None:
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_001", "display_name": "Alice"},
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
        json={"input": {"type": "text", "text": "我先定义范围再估算"}},
    )
    assert turn_resp.status_code == 200

    end_resp = client.post(f"/api/v1/sessions/{session_id}/end", json={"reason": "completed"})
    assert end_resp.status_code == 200
