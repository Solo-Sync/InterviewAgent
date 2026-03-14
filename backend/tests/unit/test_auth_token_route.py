from fastapi.testclient import TestClient

from apps.api.main import app


def test_candidate_can_register_and_receive_token() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["data"]["role"] == "candidate"
    assert payload["data"]["candidate_id"] == "Sarah2026"
    assert payload["data"]["display_name"] == "Sarah2026"


def test_candidate_token_uses_registered_identity() -> None:
    client = TestClient(app)
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data"]["role"] == "candidate"
    assert payload["data"]["candidate_id"] == "Sarah2026"
    assert payload["data"]["display_name"] == "Sarah2026"


def test_candidate_token_rejects_invalid_credentials() -> None:
    client = TestClient(app)
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "username": "Sarah2026",
            "password": "wrong_token1@",
        },
    )

    assert resp.status_code == 401
    payload = resp.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"


def test_candidate_token_rejects_candidate_id_override() -> None:
    client = TestClient(app)
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    resp = client.post(
        "/api/v1/auth/token",
        json={
            "role": "candidate",
            "username": "Sarah2026",
            "password": "Sarah_2026",
            "candidate_id": "cand_attacker_override",
        },
    )

    assert resp.status_code == 403
    payload = resp.json()
    assert payload["error"]["code"] == "FORBIDDEN"


def test_candidate_register_rejects_invalid_username() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bad-user",
            "password": "Valid_2026",
        },
    )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_candidate_register_rejects_invalid_password() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "passwordonly",
        },
    )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_candidate_register_rejects_duplicate_username() -> None:
    client = TestClient(app)
    first = client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/register",
        json={
            "username": "Sarah2026",
            "password": "Sarah_2026",
        },
    )

    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "CONFLICT"
