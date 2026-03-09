from __future__ import annotations

import base64
import hashlib
import hmac
import json
from time import time

import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.config import settings
from apps.api.core.dependencies import orchestrator
from apps.api.main import app
from libs.schemas.base import NextActionType
from services.orchestrator.next_action_decider import NextActionDecision


def _headers(role: AuthRole, *, subject: str, candidate_id: str | None = None) -> dict[str, str]:
    token, _ = issue_access_token(subject=subject, role=role, candidate_id=candidate_id)
    return {"Authorization": f"Bearer {token}"}


def _encode(payload: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    def _b64(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")).rstrip(
            b"="
        ).decode("ascii")

    header_part = _b64(header)
    payload_part = _b64(payload)
    signed = f"{header_part}.{payload_part}".encode("ascii")
    signature = base64.urlsafe_b64encode(
        hmac.new(settings.auth_token_secret.encode("utf-8"), signed, hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
    return f"{header_part}.{payload_part}.{signature}"


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


def test_candidate_cannot_access_admin_route() -> None:
    client = TestClient(app)
    client.headers.update(_headers(AuthRole.CANDIDATE, subject="candidate@example.com", candidate_id="cand_001"))

    resp = client.get("/api/v1/admin/question_sets")

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_admin_cannot_operate_candidate_session() -> None:
    client = TestClient(app)
    client.headers.update(_headers(AuthRole.CANDIDATE, subject="candidate@example.com", candidate_id="cand_001"))
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

    client.headers.clear()
    client.headers.update(_headers(AuthRole.ADMIN, subject="admin@company.com"))
    resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "admin should be blocked"}},
    )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_candidate_cannot_create_session_for_another_candidate() -> None:
    client = TestClient(app)
    client.headers.update(_headers(AuthRole.CANDIDATE, subject="candidate@example.com", candidate_id="cand_001"))

    resp = client.post(
        "/api/v1/sessions",
        json={
            "candidate": {"candidate_id": "cand_999", "display_name": "Other Candidate"},
            "mode": "text",
            "question_set_id": "qs_fermi_v1",
            "scoring_policy_id": "rubric_v1",
            "scaffold_policy_id": "scaffold_v1",
        },
    )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_annotator_can_write_annotation_but_cannot_access_admin() -> None:
    client = TestClient(app)
    client.headers.update(_headers(AuthRole.CANDIDATE, subject="candidate@example.com", candidate_id="cand_001"))
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
    session_id = create_resp.json()["data"]["session"]["session_id"]
    turn_resp = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        json={"input": {"type": "text", "text": "我先定义范围再估算"}},
    )
    turn_id = turn_resp.json()["data"]["turn"]["turn_id"]

    client.headers.clear()
    client.headers.update(_headers(AuthRole.ANNOTATOR, subject="annotator@company.com"))
    annotation_resp = client.post(
        f"/api/v1/sessions/{session_id}/annotations",
        json={
            "turn_id": turn_id,
            "human_scores": {"plan": 1, "monitor": 1, "evaluate": 1, "adapt": 1},
            "notes": "ok",
        },
    )
    admin_resp = client.get("/api/v1/admin/question_sets")

    assert annotation_resp.status_code == 200
    assert annotation_resp.json()["data"]["stored"] is True
    assert admin_resp.status_code == 403
    assert admin_resp.json()["error"]["code"] == "FORBIDDEN"


def test_missing_role_claim_is_rejected() -> None:
    client = TestClient(app)
    token = _encode({"sub": "candidate@example.com", "candidate_id": "cand_001", "iat": int(time()), "exp": int(time()) + 60})
    client.headers.update({"Authorization": f"Bearer {token}"})

    resp = client.get("/api/v1/admin/question_sets")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_invalid_signature_is_rejected() -> None:
    client = TestClient(app)
    token, _ = issue_access_token(subject="admin@company.com", role=AuthRole.ADMIN)
    broken = token.rsplit(".", 1)[0] + ".broken"
    client.headers.update({"Authorization": f"Bearer {broken}"})

    resp = client.get("/api/v1/admin/question_sets")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_expired_token_is_rejected() -> None:
    client = TestClient(app)
    token = _encode(
        {
            "sub": "admin@company.com",
            "role": "admin",
            "iat": int(time()) - 120,
            "exp": int(time()) - 60,
        }
    )
    client.headers.update({"Authorization": f"Bearer {token}"})

    resp = client.get("/api/v1/admin/question_sets")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
