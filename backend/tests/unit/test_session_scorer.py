from libs.readiness import ReadinessProbe
from libs.schemas.base import DimScores, EvaluationResult, SessionState, Turn, TurnInput, TurnInputType
from services.evaluation.session_scorer import SessionScorer


class _ReadyGateway:
    def readiness(self) -> ReadinessProbe:
        return ReadinessProbe(status="ready")

    def complete_sync(self, model: str, prompt: str, timeout_s: float = 20.0) -> dict:
        return {
            "content": (
                '{"dimension_scores":{"plan":2.6,"monitor":2.1,"evaluate":2.2,"adapt":1.8},'
                '"confidence":0.84,"summary":"整体结构清晰但适应性一般"}'
            )
        }


class _BrokenGateway:
    def readiness(self) -> ReadinessProbe:
        return ReadinessProbe(status="ready")

    def complete_sync(self, model: str, prompt: str, timeout_s: float = 20.0) -> dict:
        raise RuntimeError("upstream error")


def _turn(*, text: str, score: float) -> Turn:
    return Turn(
        turn_id="turn_x",
        turn_index=0,
        state_before=SessionState.S_INIT,
        state_after=SessionState.S_WAIT,
        input=TurnInput(type=TurnInputType.TEXT, text=text),
        evaluation=EvaluationResult(
            scores=DimScores(plan=score, monitor=score, evaluate=score, adapt=score),
            final_confidence=0.5,
        ),
    )


def test_session_scorer_uses_llm_result_when_available() -> None:
    scorer = SessionScorer(
        gateway=_ReadyGateway(),
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
    )
    result = scorer.score_session([_turn(text="我先拆分再验证。", score=0.4)])

    assert result.source == "llm"
    assert result.scores.plan == 2.6
    assert result.scores.monitor == 2.1
    assert result.confidence == 0.84
    assert any(note.startswith("session_score_summary:") for note in result.notes)


def test_session_scorer_falls_back_to_turn_mean_when_llm_fails() -> None:
    scorer = SessionScorer(
        gateway=_BrokenGateway(),
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
    )
    result = scorer.score_session(
        [
            _turn(text="回答一", score=1.0),
            _turn(text="回答二", score=2.0),
        ]
    )

    assert result.source == "fallback_turn_mean"
    assert result.scores.plan == 1.5
    assert result.scores.monitor == 1.5
    assert result.confidence is None
    assert any(note.startswith("session_score_fallback_reason:llm_call_error") for note in result.notes)
