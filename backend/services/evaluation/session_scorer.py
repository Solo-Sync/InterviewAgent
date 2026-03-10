from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import mean
from textwrap import dedent
from typing import Any

from libs.llm_gateway.client import LLMGateway, build_json_schema_response_format
from libs.observability import log_event
from libs.readiness import ReadinessProbe
from libs.schemas.base import DimScores, Turn

logger = logging.getLogger(__name__)

_DIMENSIONS = ("plan", "monitor", "evaluate", "adapt")
_DIMENSION_LABELS = {
    "plan": "planning",
    "monitor": "monitoring",
    "evaluate": "evaluating",
    "adapt": "adaptating",
}
_DIMENSION_CHINESE_LABELS = {
    "plan": "规划",
    "monitor": "监督",
    "evaluate": "评估",
    "adapt": "适应",
}
_DIMENSION_PROMPT_BODIES = {
    "plan": dedent(
        """
        “规划（plan）”的含义是：
        面试者在开始解决问题前，能否主动明确任务目标、界定范围、拆解子问题、识别关键变量或约束，并形成一个有顺序的解决路径。
        规划强调的是“先组织怎么做”，而不是想到什么就说什么。

        请按 0~3 分评分，标准如下：

        0分：
        没有可识别的规划行为。
        常见表现：
        - 直接给答案或直接开始展开，没有说明思路结构。
        - 回答零散、跳跃，没有任务拆解。
        - 没有界定目标、范围、步骤或关键因素。
        通用例子：
        - “我觉得答案应该是这样。”
        - “先试试看吧，后面再说。”
        - “大概就是这么做，没有特别步骤。”

        1分：
        有很弱的规划意识，但结构模糊、不足以支撑后续推理。
        常见表现：
        - 只给出非常笼统的框架，如“先分析再判断”。
        - 提到几个步骤或因素，但没有解释顺序或作用。
        - 有任务拆解的意图，但不清楚、不稳定。
        通用例子：
        - “我先看几个方面，再综合一下。”
        - “先分析背景，再往下做。”
        - “我会拆一下，但现在还没有特别清晰的步骤。”

        2分：
        有较清楚的规划，能形成基本可执行的解决路径，但完整性或稳健性一般。
        常见表现：
        - 能明确给出若干步骤，且顺序基本合理。
        - 能指出关键因素、关键约束或关键判断节点。
        - 能说明为什么这样拆解，但还不够深入。
        - 规划可执行，但没有充分说明优先级、边界或备用路径。
        通用例子：
        - “我会先定义问题范围，再拆成几个部分分别判断，最后汇总结果。”
        - “我先做一个主路径，再留一步检查结果是否合理。”
        - “我先处理最关键的变量，再看次要因素是否需要补充。”

        3分：
        规划能力很强，结构清晰、主动、完整，明显提升后续推理质量。
        常见表现：
        - 明确目标、范围、步骤、关键变量、优先级和求解顺序。
        - 能解释为什么采用这一路径，而不是其他路径。
        - 会提前指出哪些部分最关键、哪些部分需要后续验证。
        - 规划具有层次感，像一个真正可执行的方案，而不是临时拼凑。
        通用例子：
        - “我先明确要回答的核心问题，再界定口径，然后按主因子拆解，最后用独立路径做校验。”
        - “我会先给出主方案，再说明哪些假设最敏感，以及如果这些假设拿不到信息时该如何替代。”
        - “我先处理高影响部分，再处理次要细节，因为这样能更快得到一个可验证的中间结论。”

        评分时注意：
        - 不要因为回答很长就给高分。
        - 不要因为候选人使用了专业术语、行业框架或某道题常见套路就直接高分。
        - 只有当这些内容体现出“主动组织解题路径”的能力时，才能加分。
        - 以下标准是跨题通用的，不要把任何具体领域示例当成高分的必要条件。
        """
    ).strip(),
    "monitor": dedent(
        """
        “监督（monitor）”的含义是：
        面试者在思考和作答过程中，能否持续检查自己的推理是否跑偏、是否遗漏关键条件、是否存在矛盾、是否使用了不稳妥假设，并能意识到当前过程中的风险和漏洞。
        监督强调的是“我现在是不是在正确地推进”。

        请按 0~3 分评分，标准如下：

        0分：
        几乎没有监督意识。
        常见表现：
        - 一路往下说，不检查过程是否有问题。
        - 出现明显漏洞、矛盾、遗漏或口径混乱，但自己毫无察觉。
        - 被追问后仍不反思先前过程。
        通用例子：
        - “先这样继续说下去。”
        - “应该没问题吧。”
        - “我就按刚才那个说法继续。”

        1分：
        有一点监督意识，但很弱，通常只是模糊地表达不确定。
        常见表现：
        - 会说“可能不太对”“可能有问题”，但说不出问题在哪里。
        - 提到“需要检查”，但没有明确检查对象或检查方法。
        - 有不稳感，但无法定位具体风险点。
        通用例子：
        - “这里可能不太准确。”
        - “我感觉可能哪里有问题，但我还没想清楚。”
        - “这个之后可能还要再看看。”

        2分：
        具备较明确的监督行为，能发现主要风险点，但持续性或深度一般。
        常见表现：
        - 能指出当前推理中的关键风险、薄弱假设或潜在矛盾。
        - 能在关键节点主动停下来检查。
        - 能说明自己在检查什么，但不一定系统。
        - 监督行为存在，但不是始终稳定。
        通用例子：
        - “我先停一下，看这里是不是把两个不同口径混在一起了。”
        - “这一步我需要确认一下是否漏掉了关键约束。”
        - “这里的前提如果不成立，后面的结论可能都会偏掉。”

        3分：
        监督能力很强，能持续、主动、具体地监控自己的思路质量。
        常见表现：
        - 主动设定检查点，而不是等别人提醒。
        - 能准确定位错误来源，如定义不一致、逻辑跳步、重复计算、边界错误、假设不稳。
        - 能说明为什么这个地方值得检查，以及不检查会带来什么偏差。
        - 监督自然嵌入过程，是推理的一部分。
        通用例子：
        - “我先暂停一下，检查当前步骤是否和最初目标一致，否则后面会越走越偏。”
        - “这里最需要监控的是我是否把不同前提混在了一起，因为这会导致表面合理、实则不可比的结论。”
        - “我现在先不继续扩展，而是回头确认这一层推理是否自洽，再决定下一步。”

        评分时注意：
        - 不要把“给出最终验证结果”误算成监督，那更接近评估。
        - 不要把“改变方法”误算成监督，那更接近适应。
        - 监督看的是过程中的自我监控，而不是事后总结。
        - 以下标准是跨题通用的，不要把任何具体领域示例当成高分的必要条件。
        """
    ).strip(),
    "evaluate": dedent(
        """
        “评估（evaluate）”的含义是：
        面试者能否对自己的答案、判断或过程做质量判断，利用证据、对比、常识、交叉验证、边界判断、反向检验等方式，判断结果是否合理、是否可信、是否足以支撑结论。
        评估强调的是“这个结果到底靠不靠谱”。

        请按 0~3 分评分，标准如下：

        0分：
        没有评估行为。
        常见表现：
        - 给出结论后不检验、不比较、不说明依据。
        - 默认自己的结果成立。
        - 不对结论质量作任何判断。
        通用例子：
        - “我觉得就是这个结果。”
        - “应该对吧。”
        - “结论就先这样。”

        1分：
        有很弱的评估意识，但验证方式空泛或无效。
        常见表现：
        - 只说“需要验证”“需要查资料”，但没有说怎么验证。
        - 用模糊直觉评价结果，没有具体依据。
        - 提到证据来源，但没有解释它如何支持结论。
        通用例子：
        - “这个之后可以再验证一下。”
        - “我感觉还算合理。”
        - “大概是对的，后面再确认。”

        2分：
        有明确评估动作，能用至少一种有效方式检验结果合理性，但充分性一般。
        常见表现：
        - 使用常识检验、对照、反推、区间比较、独立路径检验等方法。
        - 能说明为什么当前结论大致合理或哪里还不稳。
        - 有评估行为，但证据链不够完整，或者只做了单一路径验证。
        通用例子：
        - “我会用另一条思路再算一遍，看结果是否还落在相近范围。”
        - “我会检查这个结论是否违反基本常识或边界条件。”
        - “如果从另一个角度看结果差异太大，那说明当前判断还不够稳。”

        3分：
        评估能力很强，能用多种证据或独立路径判断结果质量，并解释判断依据。
        常见表现：
        - 主动使用交叉验证、反向检验、区间对照、情景比较或证据比较。
        - 明确说明结果合理或不合理的依据。
        - 不仅会检验，还会说明“检验通过意味着什么，检验失败意味着什么”。
        - 评估是结论可信度的核心支撑，不是一句点缀。
        通用例子：
        - “我不会只看一个答案，而会看不同方法是否收敛到同一量级，这样结论才更可信。”
        - “如果这条路径和另一条独立路径得到的结果接近，我会提高对结论的信心；如果差异过大，就说明模型还需要修正。”
        - “我会先判断这个结果是否在常识边界内，再判断它是否和过程中的关键假设一致。”

        评分时注意：
        - 不要把“事先拆步骤”误算成评估，那更接近规划。
        - 不要把“发现过程风险”误算成评估，那可能只是监督。
        - 评估必须体现对结果质量的判断依据。
        - 以下标准是跨题通用的，不要把任何具体领域示例当成高分的必要条件。
        """
    ).strip(),
    "adapt": dedent(
        """
        “适应（adapt）”的含义是：
        面试者在发现原方案受限、信息不足、前提变化、方法失效、口径不一致或条件改变后，能否调整策略、替换路径、重构模型、改变优先级，并继续推进任务。
        适应强调的是“当原方法不够用时，我如何换一种可行办法”。

        请按 0~3 分评分，标准如下：

        0分：
        没有适应能力表现。
        常见表现：
        - 原方法不成立时直接卡住。
        - 被指出问题后仍重复原说法。
        - 没有替代路径，也不会调整。
        通用例子：
        - “如果这个不行，那我就不知道了。”
        - “那我还是照原来的说法继续。”
        - “没有这个前提我就做不了。”

        1分：
        有一点适应意愿，但调整很弱，通常停留在表态层面。
        常见表现：
        - 会说“换个思路”“改一下”，但没有形成实际新方案。
        - 承认原方法有问题，但不知道怎么调整。
        - 做了表面改动，本质路径没变。
        通用例子：
        - “那我换个角度试试。”
        - “如果这个不行，我再换一种方式。”
        - “我可能得重新想一下。”

        2分：
        能够做出有效调整，提出替代路径，但深度或解释一般。
        常见表现：
        - 信息不足时会改用替代方法、近似方法、区间方法、保守方法或另一条路径。
        - 能根据条件变化调整模型或重点。
        - 调整有效，但未充分解释为什么优先这样改。
        通用例子：
        - “如果原来的方法依赖的信息拿不到，我会改成一个更粗但更稳的估计方式。”
        - “如果这个前提不成立，我会先切换到另一条可验证的路径。”
        - “我会把原来的一步法改成分阶段处理，先解决最关键的部分。”

        3分：
        适应能力很强，调整及时、明确，而且解释得清楚。
        常见表现：
        - 不仅能换方案，还能说明为什么先换这一种。
        - 能根据限制条件变化主动重构模型，而不是只在原方案上打补丁。
        - 调整后仍能保持整体逻辑自洽。
        - 能说明新方案与旧方案相比，代价和收益分别是什么。
        通用例子：
        - “原方案太依赖一个不稳的前提，所以我先切到更可验证的路径，再用它反过来约束原模型。”
        - “如果条件变化导致原口径失效，我会先统一定义，再重建解题结构，而不是直接在旧结论上修补。”
        - “我会先保住可解释性和可验证性，再追求精细度，因为当前约束下这是更稳的选择。”

        评分时注意：
        - 不要把“指出问题”误算成适应，那可能只是监督。
        - 不要把“验证结果是否合理”误算成适应，那更接近评估。
        - 适应必须体现策略、模型、路径或优先级发生了实际调整。
        - 以下标准是跨题通用的，不要把任何具体领域示例当成高分的必要条件。
        """
    ).strip(),
}

_SIGNAL_TERMS = (
    "目标",
    "计划",
    "步骤",
    "拆分",
    "假设",
    "检查",
    "验证",
    "对比",
    "证据",
    "如果",
    "调整",
    "适应",
    "plan",
    "monitor",
    "evaluate",
    "adapt",
    "step",
    "check",
    "validate",
    "compare",
    "fallback",
)
_SIGNAL_TERMS_SORTED = sorted(_SIGNAL_TERMS, key=len, reverse=True)
_REFUSAL_PATTERNS = (
    "不知道",
    "不太会",
    "答不出来",
    "不想答",
    "拒绝回答",
    "跳过",
    "结束",
    "抱歉",
)
_TOKEN_RE = re.compile(r"[0-9A-Za-z_]{2,}|[\u4e00-\u9fff]+")
_NON_SEMANTIC_RE = re.compile(r"[\s,.;:!?，。；：！？、*\\-_/]+")
_SESSION_SCORE_RESPONSE_FORMAT = build_json_schema_response_format(
    name="session_dimension_score",
    description="A single dimension score for a session transcript.",
    schema={
        "type": "object",
        "properties": {
            "dimension": {
                "type": "string",
                "enum": ["plan", "monitor", "evaluate", "adapt"],
            },
            "score": {"type": "number", "minimum": 0, "maximum": 3},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
            "evidence": {"type": "string"},
        },
        "required": ["dimension", "score", "confidence", "reason", "evidence"],
        "additionalProperties": False,
    },
)


@dataclass(slots=True)
class SessionScoreResult:
    scores: DimScores
    confidence: float | None
    source: str
    notes: list[str]


class SessionScorer:
    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        allow_test_mode_llm: bool = False,
        runs_per_dimension: int = 3,
        max_attempts_per_dimension: int = 5,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.model = (
            model
            or os.getenv("SESSION_EVAL_MODEL")
            or os.getenv("LLM_MODEL_NAME")
            or os.getenv("LLM_GATEWAY_MODEL")
            or "qwen-plus"
        )
        self.timeout_s = timeout_s if timeout_s is not None else float(os.getenv("SESSION_EVAL_TIMEOUT_S", "20"))
        self.allow_test_mode_llm = allow_test_mode_llm
        self.runs_per_dimension = max(1, runs_per_dimension)
        self.max_attempts_per_dimension = max(self.runs_per_dimension, max_attempts_per_dimension)

    def score_session(self, turns: list[Turn]) -> SessionScoreResult:
        if not turns:
            return self._fallback(turns, reason="empty_session")

        if "PYTEST_CURRENT_TEST" in os.environ and not self.allow_test_mode_llm:
            return self._fallback(turns, reason="pytest_mode")

        readiness = self.gateway.readiness()
        if readiness.status != "ready":
            return self._fallback(
                turns,
                reason=f"gateway_not_ready:{readiness.status}",
                readiness=readiness,
            )

        try:
            ensemble = self._run_dimension_ensemble(turns)
        except Exception as exc:  # noqa: BLE001
            return self._fallback(turns, reason=f"llm_call_error:{exc.__class__.__name__}")

        scores = DimScores(
            plan=ensemble["scores"]["plan"],
            monitor=ensemble["scores"]["monitor"],
            evaluate=ensemble["scores"]["evaluate"],
            adapt=ensemble["scores"]["adapt"],
        )
        notes = [
            f"session_score_source:{ensemble['source']}",
            f"session_score_call_success:{ensemble['success_calls']}/{ensemble['total_calls']}",
            *ensemble["dimension_notes"],
        ]
        if ensemble["confidence"] is not None:
            notes.append(f"session_score_confidence:{ensemble['confidence']:.2f}")

        scores, guard_notes = self._apply_post_guards(scores, turns)
        notes.extend(guard_notes)
        return SessionScoreResult(
            scores=scores,
            confidence=ensemble["confidence"],
            source=ensemble["source"],
            notes=notes,
        )

    def _run_dimension_ensemble(self, turns: list[Turn]) -> dict[str, Any]:
        coro = self._run_dimension_ensemble_async(turns)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    async def _run_dimension_ensemble_async(self, turns: list[Turn]) -> dict[str, Any]:
        transcript = self._build_transcript(turns)
        max_total_calls = len(_DIMENSIONS) * self.max_attempts_per_dimension
        log_event(
            logger,
            logging.INFO,
            "session_scorer_started",
            model=self.model,
            timeout_s=self.timeout_s,
            turns=len(turns),
            mode="dimension_ensemble",
            runs_per_dimension=self.runs_per_dimension,
            total_calls=max_total_calls,
        )

        raw_dimensions = await asyncio.gather(
            *(self._score_dimension_with_retries(transcript, dimension=dimension) for dimension in _DIMENSIONS)
        )
        complete = all(item["complete"] for item in raw_dimensions)
        scores = {}
        confidences: list[float] = []
        success_calls = 0
        failed_calls = 0
        total_calls = 0
        dimension_notes: list[str] = []

        for item in raw_dimensions:
            dimension = str(item["dimension"])
            votes = list(item["scores"])
            confidence_votes = list(item["confidences"])
            scores[dimension] = round(mean(votes), 2) if votes else 0.0
            if confidence_votes:
                confidences.extend(confidence_votes)
            success_calls += int(item["success_calls"])
            failed_calls += int(item["failed_calls"])
            total_calls += int(item["attempts_used"])
            dimension_notes.append(f"session_score_votes:{dimension}:{len(votes)}")
            dimension_notes.append(f"session_score_attempts:{dimension}:{item['attempts_used']}")
            if not item["complete"]:
                dimension_notes.append(f"session_score_partial:{dimension}")
            if not votes:
                dimension_notes.append(f"session_score_zero_success:{dimension}")

        confidence = round(mean(confidences), 2) if confidences else None
        return {
            "complete": complete,
            "scores": scores,
            "confidence": confidence,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "total_calls": total_calls,
            "dimension_notes": dimension_notes,
            "source": "llm_dimension_ensemble" if complete else "llm_dimension_partial_ensemble",
        }

    async def _score_dimension_with_retries(self, transcript: str, *, dimension: str) -> dict[str, Any]:
        scores: list[float] = []
        confidences: list[float] = []
        attempts_used = 0
        failed_calls = 0

        while len(scores) < self.runs_per_dimension and attempts_used < self.max_attempts_per_dimension:
            attempts_left = self.max_attempts_per_dimension - attempts_used
            missing_scores = self.runs_per_dimension - len(scores)
            batch_size = min(missing_scores, attempts_left)
            start_attempt = attempts_used + 1
            tasks = [
                self._score_one_call(
                    dimension=dimension,
                    attempt=attempt,
                    prompt=self._build_dimension_prompt(transcript, dimension=dimension, attempt=attempt),
                )
                for attempt in range(start_attempt, start_attempt + batch_size)
            ]
            raw = await asyncio.gather(*tasks, return_exceptions=True)
            attempts_used += batch_size

            for item in raw:
                if isinstance(item, Exception):
                    failed_calls += 1
                    continue
                _, score, confidence = item
                if score is None:
                    failed_calls += 1
                    continue
                scores.append(score)
                if confidence is not None:
                    confidences.append(confidence)

        return {
            "dimension": dimension,
            "scores": scores,
            "confidences": confidences,
            "attempts_used": attempts_used,
            "success_calls": len(scores),
            "failed_calls": failed_calls,
            "complete": len(scores) >= self.runs_per_dimension,
        }

    async def _score_one_call(
        self,
        *,
        dimension: str,
        attempt: int,
        prompt: str,
    ) -> tuple[str, float | None, float | None]:
        if hasattr(self.gateway, "complete"):
            raw = await self.gateway.complete(
                self.model,
                prompt,
                timeout_s=self.timeout_s,
                response_format=_SESSION_SCORE_RESPONSE_FORMAT,
            )
        else:
            raw = await asyncio.to_thread(
                self.gateway.complete_sync,
                self.model,
                prompt,
                self.timeout_s,
                response_format=_SESSION_SCORE_RESPONSE_FORMAT,
            )

        payload = raw.get("parsed") if isinstance(raw, dict) else None
        if not isinstance(payload, dict):
            content = raw.get("content") if isinstance(raw, dict) else None
            if not isinstance(content, str) or not content.strip():
                return dimension, None, None
            payload = self._parse_payload(content)
        score = self._extract_dimension_score(payload, dimension)
        confidence = self._extract_confidence(payload.get("confidence"))
        return dimension, score, confidence

    def _build_transcript(self, turns: list[Turn]) -> str:
        lines: list[str] = []
        for turn in turns:
            question = turn.question.text if turn.question and turn.question.text else "(no question)"
            answer = (
                turn.preprocess.clean_text
                if turn.preprocess and turn.preprocess.clean_text
                else str(turn.input.text or "")
            )
            scaffold_prompt = (
                turn.scaffold.prompt if turn.scaffold and turn.scaffold.fired and turn.scaffold.prompt else None
            )
            lines.append(f"Turn {turn.turn_index + 1}")
            lines.append(f"Q: {question[:220]}")
            lines.append(f"A: {answer[:280]}")
            if scaffold_prompt:
                lines.append(f"Scaffold: {scaffold_prompt[:220]}")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_dimension_prompt(self, transcript: str, *, dimension: str, attempt: int) -> str:
        label = _DIMENSION_LABELS[dimension]
        chinese_label = _DIMENSION_CHINESE_LABELS[dimension]
        rubric = _DIMENSION_PROMPT_BODIES[dimension]
        return dedent(
            f"""
            你是考察面试者元认知能力的面试官。元认知能力分为四个维度：规划（plan）、评估（evaluate）、监督（monitor）、适应（adapt）。

            本次你只能评估“{chinese_label}（{dimension}）”这一项，禁止评价其他维度，也不要因为其他维度表现好就提高{chinese_label}分数。

            Dimension key: {dimension}
            Dimension label: {label}
            Attempt: {attempt}

            {rubric}

            额外扣分要求：
            - 如果对话主要是拒答、跑题、提示词探测或关键词堆砌，请严格扣分。
            - 不要把示例中的措辞、行业术语或领域内容当成高分必要条件，只评估是否体现出对应的元认知行为。

            请只返回 JSON：
            {{"dimension":"{dimension}","score":0-3,"confidence":0-1,"reason":"一句话说明原因","evidence":"引用候选人原话中的关键片段"}}

            Conversation transcript:
            {transcript}
            """
        ).strip()

    def _parse_payload(self, content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no_json_object")
        payload = json.loads(content[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("payload_not_object")
        return payload

    def _extract_dimension_score(self, payload: dict[str, Any], dimension: str) -> float:
        # Preferred: single-dimension output.
        for key in (
            "score",
            dimension,
            f"{dimension}_score",
            _DIMENSION_LABELS[dimension],
            f"{_DIMENSION_LABELS[dimension]}_score",
        ):
            if key not in payload:
                continue
            try:
                value = float(payload[key])
                return round(max(0.0, min(3.0, value)), 2)
            except (TypeError, ValueError):
                continue

        # Compatible: nested dimension_scores map.
        dim_map = payload.get("dimension_scores") or payload.get("scores")
        if isinstance(dim_map, dict):
            try:
                value = float(dim_map.get(dimension, 0.0))
                return round(max(0.0, min(3.0, value)), 2)
            except (TypeError, ValueError):
                pass

        raise ValueError("missing_dimension_score")

    def _extract_confidence(self, value: Any) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 2)
        except (TypeError, ValueError):
            return 0.0

    def _fallback(
        self,
        turns: list[Turn],
        *,
        reason: str,
        readiness: ReadinessProbe | None = None,
    ) -> SessionScoreResult:
        scores = DimScores(plan=0.0, monitor=0.0, evaluate=0.0, adapt=0.0)
        notes = [
            "session_score_source:llm_zero_fallback",
            f"session_score_fallback_reason:{reason}",
        ]
        if readiness and readiness.detail:
            notes.append(f"session_score_gateway_detail:{readiness.detail[:180]}")
        scores, guard_notes = self._apply_post_guards(scores, turns)
        notes.extend(guard_notes)
        return SessionScoreResult(
            scores=scores,
            confidence=None,
            source="llm_zero_fallback",
            notes=notes,
        )

    def _apply_post_guards(self, scores: DimScores, turns: list[Turn]) -> tuple[DimScores, list[str]]:
        guarded = scores
        notes: list[str] = []
        if self._is_refusal_dominant(turns):
            guarded = self._cap_all(guarded, 0.2)
            notes.append("session_score_guard:refusal_dominant_cap")
        if self._is_keyword_stuffing_dominant(turns):
            guarded = self._cap_all(guarded, 0.8)
            notes.append("session_score_guard:keyword_stuffing_cap")
        guarded, alignment_notes = self._cap_by_turn_history(guarded, turns)
        notes.extend(alignment_notes)
        return guarded, notes

    def _cap_all(self, scores: DimScores, cap: float) -> DimScores:
        return DimScores(
            plan=round(min(scores.plan, cap), 2),
            monitor=round(min(scores.monitor, cap), 2),
            evaluate=round(min(scores.evaluate, cap), 2),
            adapt=round(min(scores.adapt, cap), 2),
        )

    def _cap_by_turn_history(self, scores: DimScores, turns: list[Turn]) -> tuple[DimScores, list[str]]:
        votes = [turn.evaluation.scores for turn in turns if turn.evaluation is not None]
        if len(votes) < 3:
            return scores, []

        capped_values: dict[str, float] = {}
        notes: list[str] = []
        for dimension in _DIMENSIONS:
            current_score = float(getattr(scores, dimension))
            max_turn_score = max(float(getattr(vote, dimension)) for vote in votes)
            upper_bound = round(min(3.0, max_turn_score + 0.5), 2)
            if current_score > upper_bound:
                capped_values[dimension] = upper_bound
                notes.append(f"session_score_guard:turn_alignment_cap:{dimension}:{upper_bound:.2f}")
            else:
                capped_values[dimension] = round(current_score, 2)

        return (
            DimScores(
                plan=capped_values["plan"],
                monitor=capped_values["monitor"],
                evaluate=capped_values["evaluate"],
                adapt=capped_values["adapt"],
            ),
            notes,
        )

    def _is_refusal_dominant(self, turns: list[Turn]) -> bool:
        if not turns:
            return False
        refusal_hits = 0
        for turn in turns:
            answer = self._turn_answer(turn)
            if any(pattern in answer for pattern in _REFUSAL_PATTERNS):
                refusal_hits += 1
        return refusal_hits / len(turns) >= 0.5

    def _is_keyword_stuffing_dominant(self, turns: list[Turn]) -> bool:
        if not turns:
            return False
        stuffing_hits = 0
        for turn in turns:
            answer = self._turn_answer(turn)
            if len(answer) < 12:
                continue
            token_count = len(_TOKEN_RE.findall(answer))
            if token_count <= 0:
                continue
            signal_hits = sum(1 for term in _SIGNAL_TERMS if term in answer)
            residual = answer
            for term in _SIGNAL_TERMS_SORTED:
                residual = residual.replace(term, " ")
            residual = _NON_SEMANTIC_RE.sub("", residual)
            if signal_hits >= 6 and len(residual) <= 4:
                stuffing_hits += 1
        return stuffing_hits / len(turns) >= 0.34

    def _turn_answer(self, turn: Turn) -> str:
        if turn.preprocess and turn.preprocess.clean_text:
            return turn.preprocess.clean_text.lower()
        return str(turn.input.text or "").lower()
