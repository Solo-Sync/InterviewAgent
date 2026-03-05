from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers import health
from libs.readiness import ReadinessProbe


def test_health_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_get_llm_readiness",
        lambda: ReadinessProbe(status="not_configured"),
    )
    monkeypatch.setattr(
        health,
        "_get_asr_readiness",
        lambda: ReadinessProbe(status="unavailable"),
    )
    client = TestClient(app)
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["data"]["service"] == "metacog-interview"
    assert payload["data"]["status"] == "degraded"
    assert payload["data"]["llm_ready"] is False
    assert payload["data"]["asr_ready"] is False
    assert payload["data"]["llm_status"] == "not_configured"
    assert payload["data"]["asr_status"] == "unavailable"
    assert payload["trace_id"].startswith("trc_")


def test_health_reports_ready_when_dependencies_are_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_get_llm_readiness",
        lambda: ReadinessProbe(status="ready"),
    )
    monkeypatch.setattr(
        health,
        "_get_asr_readiness",
        lambda: ReadinessProbe(status="ready"),
    )

    client = TestClient(app)
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["status"] == "ready"
    assert payload["llm_ready"] is True
    assert payload["asr_ready"] is True
    assert payload["llm_status"] == "ready"
    assert payload["asr_status"] == "ready"


def test_health_reports_degraded_component_states(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_get_llm_readiness",
        lambda: ReadinessProbe(status="not_configured", detail="stub provider"),
    )
    monkeypatch.setattr(
        health,
        "_get_asr_readiness",
        lambda: ReadinessProbe(status="degraded", detail="model load failed"),
    )

    client = TestClient(app)
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["status"] == "degraded"
    assert payload["llm_ready"] is False
    assert payload["asr_ready"] is False
    assert payload["llm_status"] == "not_configured"
    assert payload["llm_detail"] == "stub provider"
    assert payload["asr_status"] == "degraded"
    assert payload["asr_detail"] == "model load failed"
