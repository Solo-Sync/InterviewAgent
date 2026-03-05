from fastapi.testclient import TestClient

from apps.api.main import app


def test_candidate_token_uses_preloaded_identity() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "email": "sarah.chen@email.com",
            "password": "invite-sarah-001",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data"]["role"] == "candidate"
    assert payload["data"]["candidate_id"] == "candidate_sarah_chen"
    assert payload["data"]["display_name"] == "Sarah Chen"


def test_candidate_token_rejects_invalid_credentials() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "email": "sarah.chen@email.com",
            "password": "wrong-token",
        },
    )

    assert resp.status_code == 401
    payload = resp.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"


def test_candidate_token_rejects_candidate_id_override() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "email": "sarah.chen@email.com",
            "password": "invite-sarah-001",
            "candidate_id": "cand_attacker_override",
        },
    )

    assert resp.status_code == 403
    payload = resp.json()
    assert payload["error"]["code"] == "FORBIDDEN"
