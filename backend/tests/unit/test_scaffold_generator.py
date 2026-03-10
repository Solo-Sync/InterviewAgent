from libs.schemas.base import NextActionType, ScaffoldLevel, SessionState
from services.scaffold.generator import ScaffoldGenerator


class _FakeDialogue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        seed_text = kwargs.get("seed_text")
        return f"LLM:{seed_text}" if seed_text else "LLM:generated"


def test_scaffold_generator_uses_dialogue_llm_for_prompt() -> None:
    fake = _FakeDialogue()
    generator = ScaffoldGenerator(dialogue=fake)  # type: ignore[arg-type]

    result = generator.generate(
        ScaffoldLevel.L2,
        {
            "text": "我现在没有思路。",
            "question_set_id": "qs_fermi_v1",
            "state": SessionState.S_WAIT.value,
            "turn_index": 3,
            "trigger_types": ["HELP_KEYWORD"],
        },
    )

    assert result.fired is True
    assert result.level == ScaffoldLevel.L2
    assert result.prompt is not None
    assert result.prompt.startswith("LLM:")
    assert fake.calls
    call = fake.calls[-1]
    assert call["action_type"] == NextActionType.SCAFFOLD
    assert call["scaffold_level"] == ScaffoldLevel.L2
    assert call["question_set_id"] == "qs_fermi_v1"
    assert call["turn_index"] == 3
    assert call["trigger_types"] == ["HELP_KEYWORD"]
