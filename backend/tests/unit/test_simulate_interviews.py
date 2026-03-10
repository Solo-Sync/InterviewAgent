import json

import pytest

from scripts import simulate_interviews


def test_extract_json_object_supports_embedded_payload() -> None:
    payload = simulate_interviews.extract_json_object(
        'prefix {"answer":"ok","should_stop":false} suffix'
    )

    assert payload["answer"] == "ok"
    assert payload["should_stop"] is False


def test_slugify_normalizes_mixed_input() -> None:
    assert simulate_interviews.slugify("LLM Sim Run #1") == "llm-sim-run-1"


def test_render_transcript_markdown_contains_session_and_messages() -> None:
    markdown = simulate_interviews.render_transcript_markdown(
        session_id="sess_123",
        persona=simulate_interviews.PERSONAS["structured"],
        candidate=simulate_interviews.CandidateAccount(
            email="alice@example.com",
            candidate_id="candidate_alice",
            display_name="Alice",
            invite_token="invite-alice-001",
        ),
        conversation=[
            {"speaker": "Interviewer", "text": "How would you estimate demand?"},
            {"speaker": "Candidate", "text": "I would start by defining the population."},
        ],
    )

    assert "# Session sess_123" in markdown
    assert "Structured Problem Solver" in markdown
    assert "How would you estimate demand?" in markdown
    assert "I would start by defining the population." in markdown


def test_candidate_simulator_uses_json_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeGateway:
        def __init__(self, **kwargs):  # noqa: ANN003
            captured["init_kwargs"] = kwargs

        def readiness(self):  # noqa: ANN201
            return type("Readiness", (), {"status": "ready", "detail": None})()

        def complete_sync(  # noqa: ANN201, ANN001
            self,
            model: str,
            prompt: str,
            timeout_s: float = 4.0,
            *,
            response_format: dict | None = None,
        ):
            captured["model"] = model
            captured["prompt"] = prompt
            captured["response_format"] = response_format
            return {
                "content": json.dumps(
                    {
                        "answer": "我会先定义问题范围，再拆分变量。",
                        "should_stop": False,
                        "rationale": "structured",
                    },
                    ensure_ascii=False,
                )
            }

    monkeypatch.setattr("scripts.simulate_interviews.LLMGateway", _FakeGateway)
    simulator = simulate_interviews.CandidateSimulator(
        model="qwen-plus",
        timeout_s=5.0,
        provider="aliyun",
        base_url=None,
        api_key="secret",
    )

    decision, trace = simulator.generate(
        persona=simulate_interviews.PERSONAS["structured"],
        conversation=[{"speaker": "Interviewer", "text": "你会怎么估算？"}],
        turn_index=1,
    )

    assert decision.answer == "我会先定义问题范围，再拆分变量。"
    assert decision.should_stop is False
    assert trace["parse_mode"] == "json"
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["name"] == "candidate_simulator_reply"
