from __future__ import annotations

from libs.schemas.base import NextActionType, ScaffoldLevel, ScaffoldResult, SessionState
from services.dialogue.generator import DialogueGenerator


class ScaffoldGenerator:
    def __init__(self, *, dialogue: DialogueGenerator | None = None) -> None:
        self.dialogue = dialogue or DialogueGenerator()

    def generate(self, level: ScaffoldLevel, context: dict) -> ScaffoldResult:
        state = self._resolve_state(context.get("state"))
        question_set_id = str(context.get("question_set_id") or "scaffold_runtime")
        turn_index = self._resolve_turn_index(context.get("turn_index"))
        candidate_answer = str(context.get("text") or context.get("candidate_last_answer") or "")
        trigger_types = self._resolve_trigger_types(context.get("trigger_types"))

        if level == ScaffoldLevel.L1:
            seed_prompt = "先明确目标，再列出两步可执行计划。"
            prompt = self.dialogue.generate(
                action_type=NextActionType.SCAFFOLD,
                seed_text=seed_prompt,
                question_set_id=question_set_id,
                state=state,
                turn_index=turn_index,
                candidate_answer=candidate_answer,
                scaffold_level=level,
                trigger_types=trigger_types,
            )
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt=prompt,
                rationale="轻量提示，帮助回到任务。",
            )
        if level == ScaffoldLevel.L2:
            seed_prompt = "请按‘目标-假设-验证’三段回答，每段一句。"
            prompt = self.dialogue.generate(
                action_type=NextActionType.SCAFFOLD,
                seed_text=seed_prompt,
                question_set_id=question_set_id,
                state=state,
                turn_index=turn_index,
                candidate_answer=candidate_answer,
                scaffold_level=level,
                trigger_types=trigger_types,
            )
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt=prompt,
                rationale="结构化脚手架，提升监控能力。",
            )
        if level == ScaffoldLevel.L3:
            seed_prompt = "我给你一个模板：1) 目标 2) 方法 3) 风险与修正。"
            prompt = self.dialogue.generate(
                action_type=NextActionType.SCAFFOLD,
                seed_text=seed_prompt,
                question_set_id=question_set_id,
                state=state,
                turn_index=turn_index,
                candidate_answer=candidate_answer,
                scaffold_level=level,
                trigger_types=trigger_types,
            )
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt=prompt,
                rationale="强引导，适用于持续卡住场景。",
            )
        return ScaffoldResult(fired=False, level=None, prompt=None, rationale=None)

    def _resolve_state(self, value: object) -> SessionState:
        if isinstance(value, SessionState):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                try:
                    return SessionState(normalized)
                except ValueError:
                    pass
        return SessionState.S_WAIT

    def _resolve_turn_index(self, value: object) -> int:
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str):
            try:
                parsed = int(value)
            except ValueError:
                return 0
            return parsed if parsed >= 0 else 0
        return 0

    def _resolve_trigger_types(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []
