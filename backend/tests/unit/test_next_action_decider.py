import pytest

from libs.schemas.base import NextActionType
from services.orchestrator.next_action_decider import LLMNextActionDecider, NextActionDecisionError


class _FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_prompt = ""
        self.last_response_format = None

    def complete_sync(  # noqa: ANN001
        self,
        model: str,
        prompt: str,
        timeout_s: float = 4.0,
        *,
        response_format: dict | None = None,
    ):
        self.last_prompt = prompt
        self.last_response_format = response_format
        return {"model": model, "content": self.content}


def test_decider_parses_valid_json_payload() -> None:
    gateway = _FakeGateway(
        '{"next_action_type":"PROBE","interviewer_reply":"先说说你的第一步。","reasons":["信息不足"]}'
    )
    decider = LLMNextActionDecider(gateway=gateway, model="test-next-action")
    decision = decider.decide([{"role": "system", "turn_index": 0, "text": "请开始。"}])

    assert decision.action_type == NextActionType.PROBE
    assert decision.interviewer_reply == "先说说你的第一步。"
    assert decision.reasons == ("信息不足",)
    assert "full_conversation_history" in gateway.last_prompt
    assert gateway.last_response_format["type"] == "json_schema"
    assert gateway.last_response_format["json_schema"]["name"] == "next_action_decision"


def test_decider_accepts_end_action_type() -> None:
    gateway = _FakeGateway(
        '{"next_action_type":"END","interviewer_reply":"本场面试到此结束，感谢你的作答。","reasons":["时间到"]}'
    )
    decider = LLMNextActionDecider(gateway=gateway, model="test-next-action")
    decision = decider.decide([{"role": "system", "turn_index": 0, "text": "请开始。"}])

    assert decision.action_type == NextActionType.END


def test_decider_prompt_includes_time_context() -> None:
    gateway = _FakeGateway(
        '{"next_action_type":"ASK","interviewer_reply":"请继续。","reasons":["继续考察"]}'
    )
    decider = LLMNextActionDecider(gateway=gateway, model="test-next-action")
    decider.decide(
        [{"role": "system", "turn_index": 0, "text": "请开始。"}],
        elapsed_minutes=26.5,
        last_question_notice_issued=True,
    )

    assert '"elapsed_minutes": 26.5' in gateway.last_prompt
    assert '"last_question_notice_issued": true' in gateway.last_prompt


def test_decider_rejects_calm_action_type() -> None:
    gateway = _FakeGateway(
        '{"next_action_type":"CALM","interviewer_reply":"慢慢来。","reasons":[]}'
    )
    decider = LLMNextActionDecider(gateway=gateway, model="test-next-action")

    with pytest.raises(NextActionDecisionError):
        decider.decide([{"role": "candidate", "turn_index": 0, "text": "我很紧张"}])
