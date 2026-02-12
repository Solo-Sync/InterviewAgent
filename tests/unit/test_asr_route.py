from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routes import asr as asr_route
from libs.schemas.base import AsrResult
from services.asr import ASRErrorCode, ASRServiceError


def test_asr_transcribe_returns_contract_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        asr_route.asr_service,
        "transcribe",
        lambda **_: AsrResult(
            raw_text="hello",
            tokens=[],
            silence_segments=[],
            audio_features={"backend": "mock"},
        ),
    )
    client = TestClient(app)
    resp = client.post(
        "/api/v1/asr/transcribe?language=zh&need_word_timestamps=true",
        content=b"fake-audio-bytes",
        headers={"x-audio-filename": "sample.wav"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    asr = payload["data"]["asr"]
    assert set(asr.keys()) == {"raw_text", "tokens", "silence_segments", "audio_features"}
    assert isinstance(asr["silence_segments"], list)
    assert isinstance(asr["audio_features"], dict)


def test_asr_transcribe_can_disable_word_timestamps(monkeypatch) -> None:
    monkeypatch.setattr(
        asr_route.asr_service,
        "transcribe",
        lambda **_: AsrResult(
            raw_text="hello",
            tokens=None,
            silence_segments=[],
            audio_features={"backend": "mock"},
        ),
    )
    client = TestClient(app)
    resp = client.post(
        "/api/v1/asr/transcribe?language=zh&need_word_timestamps=false",
        content=b"fake-audio-bytes",
        headers={"x-audio-filename": "sample.wav"},
    )

    assert resp.status_code == 200
    asr = resp.json()["data"]["asr"]
    assert asr["tokens"] is None


def test_asr_transcribe_rejects_empty_payload() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/asr/transcribe", content=b"")
    assert resp.status_code == 400


def test_asr_transcribe_returns_503_when_model_not_ready(monkeypatch) -> None:
    def _raise(**_):
        raise ASRServiceError(ASRErrorCode.MODEL_NOT_READY, "model missing")

    monkeypatch.setattr(asr_route.asr_service, "transcribe", _raise)
    client = TestClient(app)
    resp = client.post("/api/v1/asr/transcribe", content=b"fake-audio-bytes")
    assert resp.status_code == 503
