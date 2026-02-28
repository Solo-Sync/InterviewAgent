import base64

from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.dependencies import orchestrator
from apps.api.main import app
from libs.schemas.base import AsrResult

CANDIDATE_HEADERS = {
    "Authorization": (
        f"Bearer {issue_access_token(subject='sarah.chen@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_001')[0]}"
    )
}
ANNOTATOR_HEADERS = {
    "Authorization": f"Bearer {issue_access_token(subject='annotator@company.com', role=AuthRole.ANNOTATOR)[0]}"
}


def test_session_turn_end_flow() -> None:
    client = TestClient(app)
    client.headers.update(CANDIDATE_HEADERS)

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
    assert "估算你所在城市" in create_resp.json()["data"]["next_action"]["text"]
    session_id = create_resp.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "我先定义范围再估算"}},
    )
    assert turn_resp.status_code == 200

    end_resp = client.post(f"/api/v1/sessions/{session_id}/end", json={"reason": "completed"})
    assert end_resp.status_code == 200


def test_session_turn_help_trigger_applies_l2_discount() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='cara@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_003')[0]}"
            )
        }
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_003", "display_name": "Cara"},
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
        json={"input": {"type": "text", "text": "help，我不知道该怎么开始，帮帮我"}},
    )
    assert turn_resp.status_code == 200
    payload = turn_resp.json()["data"]
    assert payload["next_action"]["type"] == "SCAFFOLD"
    assert payload["next_action"]["level"] == "L2"
    assert payload["evaluation"]["discounts"] is not None
    assert len(payload["evaluation"]["discounts"]) >= 1


def test_session_create_rejects_invalid_rubric_id() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='cara@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_003x')[0]}"
            )
        }
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_003x", "display_name": "Cara"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_not_exists",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_resp.status_code == 400
    payload = create_resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "rubric not found" in payload["error"]["message"]


def test_session_create_rejects_invalid_question_set_id() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='cara@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_003y')[0]}"
            )
        }
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_003y", "display_name": "Cara"},
            "mode": "text",
            "question_set_id": "qs_not_exists",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_resp.status_code == 400
    payload = create_resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "question_set not found" in payload["error"]["message"]


def test_session_turn_audio_ref_flow(monkeypatch) -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='bob@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_002')[0]}"
            )
        }
    )

    monkeypatch.setattr(
        orchestrator.asr_service,
        "transcribe",
        lambda **_: AsrResult(
            raw_text="这是语音转写",
            tokens=[],
            silence_segments=[],
            audio_features={"backend": "mock"},
        ),
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_002", "display_name": "Bob"},
            "mode": "audio",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["session"]["session_id"]

    data_url = "data:audio/wav;base64," + base64.b64encode(b"fake-audio-bytes").decode("ascii")
    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "audio_ref", "audio_url": data_url}},
    )
    assert turn_resp.status_code == 200
    turn = turn_resp.json()["data"]["turn"]
    assert turn["asr"]["raw_text"] == "这是语音转写"


def test_session_turn_audio_ref_rejects_remote_url_by_default() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='dora@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_004')[0]}"
            )
        }
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_004", "display_name": "Dora"},
            "mode": "audio",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "audio_ref", "audio_url": "https://example.com/sample.wav"}},
    )
    assert turn_resp.status_code == 400
    payload = turn_resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "disabled" in payload["error"]["message"]


def test_session_turn_blocked_by_safety_skips_evaluation() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='evan@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_005')[0]}"
            )
        }
    )

    create_resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_005", "display_name": "Evan"},
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
        json={"input": {"type": "text", "text": "我想聊炸弹"}},
    )
    assert turn_resp.status_code == 200
    payload = turn_resp.json()["data"]
    assert payload["next_action"]["type"] == "END"
    assert payload["evaluation"] is None


def test_annotation_rejects_turn_from_other_session() -> None:
    client = TestClient(app)
    client.headers.update(
        {
            "Authorization": (
                f"Bearer {issue_access_token(subject='fay@email.com', role=AuthRole.CANDIDATE, candidate_id='stu_006')[0]}"
            )
        }
    )

    create_a = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_006", "display_name": "Fay"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    create_b = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "stu_006", "display_name": "Gina"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )
    assert create_a.status_code == 200
    assert create_b.status_code == 200
    session_a = create_a.json()["data"]["session"]["session_id"]
    session_b = create_b.json()["data"]["session"]["session_id"]

    turn_resp = client.post(
        f"/api/v1/sessions/{session_b}/turns",
        json={"input": {"type": "text", "text": "我先定义范围再估算"}},
    )
    assert turn_resp.status_code == 200
    turn_id = turn_resp.json()["data"]["turn"]["turn_id"]

    client.headers.clear()
    client.headers.update(ANNOTATOR_HEADERS)
    annotation_resp = client.post(
        f"/api/v1/sessions/{session_a}/annotations",
        json={
            "turn_id": turn_id,
            "human_scores": {"plan": 1, "monitor": 1, "evaluate": 1, "adapt": 1},
            "notes": "cross-session should fail",
        },
    )
    assert annotation_resp.status_code == 400
    payload = annotation_resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "turn_id not found in session" in payload["error"]["message"]
