from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from libs.llm_gateway.client import LLMGateway, build_json_schema_response_format
from libs.schemas.base import NextActionType

_DECIDER_MODEL_ENV_KEYS = (
    "NEXT_ACTION_MODEL_NAME",
    "ORCHESTRATOR_MODEL_NAME",
    "LLM_MODEL_NAME",
    "ALIYUN_LLM_MODEL",
    "LLM_GATEWAY_MODEL",
)
_ALLOWED_ACTION_TYPES = {
    NextActionType.ASK,
    NextActionType.PROBE,
    NextActionType.SCAFFOLD,
    NextActionType.END,
}
_LAST_QUESTION_RUNTIME_INSTRUCTION = "这场面试时间已经过长，这次将是你的最后一次提问"
_NEXT_ACTION_RESPONSE_FORMAT = build_json_schema_response_format(
    name="next_action_decision",
    description="Interview next action decision for the orchestrator.",
    schema={
        "type": "object",
        "properties": {
            "next_action_type": {
                "type": "string",
                "enum": ["ASK", "PROBE", "SCAFFOLD", "END"],
            },
            "interviewer_reply": {"type": "string"},
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
        },
        "required": ["next_action_type", "interviewer_reply", "reasons"],
        "additionalProperties": False,
    },
)


class NextActionDecisionError(ValueError):
    pass


@dataclass(frozen=True)
class NextActionDecision:
    action_type: NextActionType
    interviewer_reply: str
    reasons: tuple[str, ...]


class LLMNextActionDecider:
    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        model: str | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.model = model or self._resolve_model()
        self.timeout_s = timeout_s

    def decide(
        self,
        full_conversation_history: list[dict[str, Any]],
        *,
        elapsed_minutes: float | None = None,
        last_question_notice_issued: bool = False,
    ) -> NextActionDecision:
        prompt = self._build_prompt(
            full_conversation_history,
            elapsed_minutes=elapsed_minutes,
            last_question_notice_issued=last_question_notice_issued,
        )
        try:
            response = self.gateway.complete_sync(
                self.model,
                prompt,
                timeout_s=self.timeout_s,
                response_format=_NEXT_ACTION_RESPONSE_FORMAT,
            )
        except Exception as exc:  # noqa: BLE001
            raise NextActionDecisionError(f"failed to decide next action: {exc}") from exc

        payload = response.get("parsed") if isinstance(response, dict) else None
        if not isinstance(payload, dict):
            content = response.get("content")
            if not isinstance(content, str) or not content.strip():
                raise NextActionDecisionError("next-action decision response missing content")
            payload = self._parse_json_payload(content)
        if not isinstance(payload, dict):
            raise NextActionDecisionError("next-action decision response is not valid JSON")

        action_type = self._parse_action_type(payload.get("next_action_type"))
        interviewer_reply = self._parse_reply(payload.get("interviewer_reply"))
        reasons = self._parse_reasons(payload.get("reasons"))

        return NextActionDecision(
            action_type=action_type,
            interviewer_reply=interviewer_reply,
            reasons=reasons,
        )

    def _resolve_model(self) -> str:
        for key in _DECIDER_MODEL_ENV_KEYS:
            value = os.getenv(key)
            if value and value.strip():
                return value.strip()
        return "next-action-decider"

    def _build_prompt(
        self,
        full_conversation_history: list[dict[str, Any]],
        *,
        elapsed_minutes: float | None,
        last_question_notice_issued: bool,
    ) -> str:
        system_prompt = (
            "你是一名“元认知面试”面试官助手。\n"
            "这场面试的目标是评估候选人的四项能力：规划（plan）、监控（monitor）、评估（evaluate）、调整（adapt）。\n\n"
            "你的任务：\n"
            "1) 在 ASK / PROBE / SCAFFOLD / END 中选择 next_action_type\n"
            "2) 生成可直接发送给候选人的 interviewer_reply\n"
            "3) 给出简短 reasons（最多3条）\n\n"
            "你必须基于“完整会话历史（system + candidate 全量文本）”做判断，不能只看最后一轮。\n\n"
            "动作定义：\n"
            "- ASK：推进到下一问、子问题或变式问题。\n"
            "- PROBE：当前回答相关但不完整，用追问补齐关键缺口（步骤、假设、验证、取舍）。\n"
            "- SCAFFOLD：候选人明显卡住、反复打转、偏题、无法自行推进时，给结构化引导。\n"
            "- END：结束面试，不再提问。\n\n"
            "时间控制规则（强约束）：\n"
            "- 输入会提供 elapsed_minutes（已进行分钟数）和 last_question_notice_issued（是否已发过“最后一次提问”通知）。\n"
            "- 若 elapsed_minutes >= 30：本轮必须输出 END。\n"
            "- 若 elapsed_minutes >= 25 且 last_question_notice_issued = false：\n"
            "  1) 本轮不能输出 END，必须输出 ASK 或 PROBE；\n"
            "  2) interviewer_reply 必须以这句话开头（逐字一致）：\n"
            "     “这场面试时间已经过长，这次将是你的最后一次提问”\n"
            "  3) 之后只允许提出 1 个高价值问题（不要多问）。\n"
            "- 若 last_question_notice_issued = true：\n"
            "  - 说明候选人已经回答过最后一问，本轮必须输出 END；\n"
            "  - interviewer_reply 仅做简短收尾与感谢，不得再提问。\n\n"
            "一般结束规则（在不违反时间强约束前提下）：\n"
            "- 满足以下任一条件可输出 END：\n"
            "  1) 面试目标已基本完成：四维能力证据已较充分，继续追问增益很低；\n"
            "  2) 连续低进展：最近多轮重复、偏题或无法推进，且已尝试有效追问/引导仍无明显改善；\n"
            "  3) 候选人明确表示希望结束、放弃或拒绝继续作答。\n"
            "- 禁止过早结束：\n"
            "  - 不能因为单次回答简短就 END；\n"
            "  - 如果一次具体追问仍可能显著增益，应优先 PROBE/ASK。\n\n"
            "语言与风格要求：\n"
            "- interviewer_reply 必须自然、具体、简洁、可直接发送；\n"
            "- 不要模板化重复，不要空泛评价；\n"
            "- 如果 next_action_type = END，回复应简短收束（感谢+结束通知），不要再出现问号式提问。\n\n"
            "输出要求：\n"
            "- 只输出 JSON，不要输出任何额外文本。\n"
            "- 严格使用以下格式：\n"
            "{\n"
            '  "next_action_type": "ASK|PROBE|SCAFFOLD|END",\n'
            '  "interviewer_reply": "面试官下一次要说的话",\n'
            '  "reasons": ["最多3条，每条不超过18字"]\n'
            "}"
        )
        user_payload = {
            "elapsed_minutes": 0.0 if elapsed_minutes is None else round(float(elapsed_minutes), 2),
            "last_question_notice_issued": bool(last_question_notice_issued),
            "full_conversation_history": full_conversation_history,
        }
        if elapsed_minutes is not None and elapsed_minutes >= 25.0 and not last_question_notice_issued:
            user_payload["runtime_instruction"] = _LAST_QUESTION_RUNTIME_INSTRUCTION
        elif last_question_notice_issued:
            user_payload["runtime_instruction"] = "候选人已经回答过最后一问，本轮必须结束面试。"
        user_prompt = json.dumps(user_payload, ensure_ascii=False)
        return (
            f"[System Prompt]\n{system_prompt}\n\n"
            "[User Prompt]\n"
            f"{user_prompt}\n\n"
            "请基于以上完整历史进行判断，并按约定格式只返回 JSON。"
        )

    def _parse_action_type(self, value: Any) -> NextActionType:
        if not isinstance(value, str):
            raise NextActionDecisionError("next_action_type must be a string")
        normalized = value.strip().upper()
        try:
            action_type = NextActionType(normalized)
        except ValueError as exc:
            raise NextActionDecisionError(f"invalid next_action_type: {value}") from exc
        if action_type not in _ALLOWED_ACTION_TYPES:
            raise NextActionDecisionError(f"unsupported next_action_type: {value}")
        return action_type

    def _parse_reply(self, value: Any) -> str:
        if not isinstance(value, str):
            raise NextActionDecisionError("interviewer_reply must be a string")
        reply = " ".join(value.split()).strip()
        if not reply:
            raise NextActionDecisionError("interviewer_reply is empty")
        if len(reply) > 240:
            reply = f"{reply[:240].rstrip(' ,，。.!?')}。"
        return reply

    def _parse_reasons(self, value: Any) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        items: list[str] = []
        for raw in value:
            text = " ".join(str(raw).split()).strip()
            if not text:
                continue
            if len(text) > 18:
                text = text[:18]
            items.append(text)
            if len(items) >= 3:
                break
        return tuple(items)

    def _parse_json_payload(self, content: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            payload = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
