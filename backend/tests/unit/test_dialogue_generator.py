import pytest

from libs.schemas.base import NextActionType, SessionState
from services.dialogue.generator import DialogueGenerationError, DialogueGenerator


class _FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_response_format = None

    def complete_sync(  # noqa: ANN001
        self,
        model: str,
        prompt: str,
        timeout_s: float = 4.0,
        *,
        response_format: dict | None = None,
    ):
        self.last_response_format = response_format
        return {"model": model, "content": self.content}


def _generate_with_content(content: str) -> str:
    generator = DialogueGenerator(gateway=_FakeGateway(content), model="test-dialogue-model")
    return generator.generate(
        action_type=NextActionType.ASK,
        seed_text="请先说说你的思路。",
        question_set_id="qs_fermi_v1",
        state=SessionState.S_WAIT,
        turn_index=1,
    )


def test_dialogue_generator_parses_json_text_field() -> None:
    gateway = _FakeGateway('{"text":"请先定义范围，再拆分变量。"}')
    generator = DialogueGenerator(gateway=gateway, model="test-dialogue-model")
    text = generator.generate(
        action_type=NextActionType.ASK,
        seed_text="请先说说你的思路。",
        question_set_id="qs_fermi_v1",
        state=SessionState.S_WAIT,
        turn_index=1,
    )

    assert text == "请先定义范围，再拆分变量。"
    assert gateway.last_response_format["type"] == "json_schema"
    assert gateway.last_response_format["json_schema"]["name"] == "dialogue_utterance"


def test_dialogue_generator_parses_embedded_json_payload() -> None:
    text = _generate_with_content('```json\n{"text":"你会如何验证数量级是否合理？"}\n```')
    assert text == "你会如何验证数量级是否合理？"


def test_dialogue_generator_falls_back_to_raw_string() -> None:
    text = _generate_with_content("继续，请说明你下一步会怎么做。")
    assert text == "继续，请说明你下一步会怎么做。"


def test_dialogue_generator_raises_on_empty_response() -> None:
    generator = DialogueGenerator(gateway=_FakeGateway("   "), model="test-dialogue-model")
    with pytest.raises(DialogueGenerationError):
        generator.generate(
            action_type=NextActionType.ASK,
            seed_text=None,
            question_set_id="qs_fermi_v1",
            state=SessionState.S_WAIT,
            turn_index=2,
        )
