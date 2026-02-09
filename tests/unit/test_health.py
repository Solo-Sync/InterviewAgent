from fastapi.testclient import TestClient

from apps.api.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["data"]["service"] == "metacog-interview"
    assert payload["trace_id"].startswith("trc_")
