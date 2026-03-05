import asyncio
import json
import re
from collections import Counter

from libs.readiness import ReadinessProbe
from libs.schemas.base import DimScores, EvaluationResult, SessionState, Turn, TurnInput, TurnInputType
from services.evaluation.session_scorer import SessionScorer

_DIM_RE = re.compile(r"Dimension key:\s*(plan|monitor|evaluate|adapt)")
_ATTEMPT_RE = re.compile(r"Attempt:\s*([0-9]+)")


class _EnsembleGateway:
    TABLE = {
        "plan": [2.0, 2.4, 2.8],
        "monitor": [1.0, 1.4, 1.8],
        "evaluate": [1.5, 1.7, 1.9],
        "adapt": [0.8, 1.0, 1.2],
    }

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    def readiness(self) -> ReadinessProbe:
        return ReadinessProbe(status="ready")

    async def complete(self, model: str, prompt: str, timeout_s: float = 20.0) -> dict:
        dim_match = _DIM_RE.search(prompt)
        attempt_match = _ATTEMPT_RE.search(prompt)
        assert dim_match is not None
        assert attempt_match is not None
        dim = dim_match.group(1)
        attempt = int(attempt_match.group(1))
        self.calls.append((dim, attempt))

        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1

        score = self.TABLE[dim][attempt - 1]
        return {
            "content": json.dumps(
                {
                    "dimension": dim,
                    "score": score,
                    "confidence": 0.9,
                    "reason": "ok",
                },
                ensure_ascii=False,
            )
        }


class _BrokenGateway:
    def readiness(self) -> ReadinessProbe:
        return ReadinessProbe(status="ready")

    async def complete(self, model: str, prompt: str, timeout_s: float = 20.0) -> dict:
        raise RuntimeError("upstream error")


class _HighScoreGateway:
    def readiness(self) -> ReadinessProbe:
        return ReadinessProbe(status="ready")

    async def complete(self, model: str, prompt: str, timeout_s: float = 20.0) -> dict:
        dim_match = _DIM_RE.search(prompt)
        assert dim_match is not None
        dim = dim_match.group(1)
        return {
            "content": json.dumps(
                {
                    "dimension": dim,
                    "score": 2.9,
                    "confidence": 0.9,
                    "reason": "high",
                },
                ensure_ascii=False,
            )
        }


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


def test_session_scorer_runs_12_parallel_dimension_calls_and_averages() -> None:
    gateway = _EnsembleGateway()
    scorer = SessionScorer(
        gateway=gateway,
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
        runs_per_dimension=3,
    )
    result = scorer.score_session(
        [
            _turn(text="我会先拆分变量，再做验证和调整。", score=0.6),
            _turn(text="如果条件变化，我会修改假设并复核。", score=0.7),
        ]
    )

    assert result.source == "llm_dimension_ensemble"
    assert result.scores.plan == 2.4
    assert result.scores.monitor == 1.4
    assert result.scores.evaluate == 1.7
    assert result.scores.adapt == 1.0

    assert len(gateway.calls) == 12
    counts = Counter(dim for dim, _ in gateway.calls)
    assert counts["plan"] == 3
    assert counts["monitor"] == 3
    assert counts["evaluate"] == 3
    assert counts["adapt"] == 3

    assert gateway.max_in_flight > 1
    assert any(note == "session_score_votes:plan:3" for note in result.notes)


def test_session_scorer_falls_back_to_turn_mean_when_ensemble_incomplete() -> None:
    scorer = SessionScorer(
        gateway=_BrokenGateway(),
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
        runs_per_dimension=3,
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
    assert any(note.startswith("session_score_fallback_reason:llm_ensemble_incomplete") for note in result.notes)


def test_session_scorer_applies_keyword_stuffing_cap_even_with_high_llm_scores() -> None:
    scorer = SessionScorer(
        gateway=_HighScoreGateway(),
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
        runs_per_dimension=3,
    )
    turns = [
        _turn(text="目标 计划 步骤 假设 范围 检查 验证 对比 证据 如果 变化 迁移", score=1.0),
        _turn(text="plan monitor evaluate adapt step check validate compare fallback", score=1.0),
        _turn(text="目标 计划 计划 检查 验证 对比 适应 适应", score=1.0),
    ]
    result = scorer.score_session(turns)

    assert result.scores.plan <= 0.8
    assert result.scores.monitor <= 0.8
    assert any(note == "session_score_guard:keyword_stuffing_cap" for note in result.notes)


def test_session_scorer_applies_refusal_cap_even_with_high_llm_scores() -> None:
    scorer = SessionScorer(
        gateway=_HighScoreGateway(),
        model="judge-model",
        timeout_s=5.0,
        allow_test_mode_llm=True,
        runs_per_dimension=3,
    )
    turns = [
        _turn(text="抱歉我答不出来。", score=0.2),
        _turn(text="我不太会，先跳过。", score=0.2),
        _turn(text="谢谢，我想结束。", score=0.2),
        _turn(text="不知道。", score=0.2),
    ]
    result = scorer.score_session(turns)

    assert result.scores.plan <= 0.2
    assert result.scores.evaluate <= 0.2
    assert any(note == "session_score_guard:refusal_dominant_cap" for note in result.notes)
