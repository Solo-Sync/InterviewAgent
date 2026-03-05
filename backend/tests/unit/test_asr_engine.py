from services.asr.engine import FunASREngine


def test_readiness_reports_unavailable_when_funasr_dependency_missing(monkeypatch) -> None:
    monkeypatch.setattr("services.asr.engine.find_spec", lambda _: None)

    engine = FunASREngine()

    readiness = engine.readiness()

    assert readiness.status == "unavailable"
    assert readiness.ready is False
    assert readiness.detail == "funasr dependency is not installed"


def test_readiness_reports_degraded_after_model_load_failure() -> None:
    engine = FunASREngine()
    engine._load_error = RuntimeError("weights missing")

    readiness = engine.readiness()

    assert readiness.status == "degraded"
    assert readiness.ready is False
    assert readiness.detail == "weights missing"
