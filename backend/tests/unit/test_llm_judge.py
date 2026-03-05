from services.evaluation.judges.llm import LLMJudge, build_default_judges


class _GatewayOK:
    def complete_sync(self, model: str, prompt: str, timeout_s: float = 3.0) -> dict:
        assert model == "judge-model"
        assert timeout_s == 2.5
        return {
            "content": (
                '{"dimension_scores":{"planning":2.4,"monitor":2,"evaluation":1.8,"transfer":1.2},'
                '"confidence":{"overall":0.83},"deductions":["missing_counter_example"],'
                '"evidence":{"plan":"先定义范围","monitor":"再检查假设"}}'
            )
        }


class _GatewayBroken:
    def complete_sync(self, model: str, prompt: str, timeout_s: float = 3.0) -> dict:
        return {"content": "not json"}


def test_llm_judge_parses_scores_and_aliases() -> None:
    judge = LLMJudge("judge_llm_1", "judge-model", gateway=_GatewayOK(), timeout_s=2.5)
    result = judge.invoke("我先定义范围，再检查假设并调整。", question="估算问题")

    assert result.judge_id == "judge_llm_1"
    assert result.dimensions["plan"] == 2.4
    assert result.dimensions["monitor"] == 2.0
    assert result.dimensions["evaluate"] == 1.8
    assert result.dimensions["adapt"] == 1.2
    assert result.confidence == 0.83
    assert result.evidence["plan"] == "先定义范围"
    assert result.evidence["monitor"] == "再检查假设"


def test_llm_judge_falls_back_when_response_invalid() -> None:
    judge = LLMJudge("judge_llm_2", "judge-model", gateway=_GatewayBroken())
    result = judge.invoke("help 我不知道怎么做")

    assert result.judge_id == "judge_llm_2"
    assert any(item.startswith("llm_parse_error") for item in result.deductions)


def test_build_default_judges_uses_single_model_env(monkeypatch) -> None:
    monkeypatch.delenv("EVAL_JUDGE_MODELS", raising=False)
    monkeypatch.delenv("ALIYUN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_GATEWAY_MODEL", raising=False)
    monkeypatch.setenv("LLM_MODEL_NAME", "qwen-plus")

    judges = build_default_judges()

    assert len(judges) == 3
    assert judges[0].model == "qwen-plus"
    assert judges[1].judge_id == "judge_heuristic_structure"
    assert judges[2].judge_id == "judge_heuristic_adapt"
