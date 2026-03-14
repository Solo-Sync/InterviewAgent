from __future__ import annotations

from services.orchestrator.selector import QuestionSelector


def test_random_opening_selection_chooses_one_root_question(monkeypatch) -> None:
    selector = QuestionSelector()
    monkeypatch.setattr(selector._random, "choice", lambda items: items[-1])

    selection = selector.random_opening_selection("qs_fermi_v1")

    assert selection.question is not None
    assert selection.question.qid == "6"
    assert "新能源汽车充电" in selection.question.text
    assert selection.cursor is not None
    assert selection.cursor.node_id == "6"


def test_question_text_returns_selected_root_question() -> None:
    selector = QuestionSelector()

    text = selector.question_text("qs_fermi_v1", "3")

    assert text is not None
    assert "图书馆" in text
