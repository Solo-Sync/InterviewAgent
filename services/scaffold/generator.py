from libs.schemas.base import ScaffoldLevel, ScaffoldResult


class ScaffoldGenerator:
    def generate(self, level: ScaffoldLevel, context: dict) -> ScaffoldResult:
        if level == ScaffoldLevel.L1:
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt="先明确目标，再列出两步可执行计划。",
                rationale="轻量提示，帮助回到任务。",
            )
        if level == ScaffoldLevel.L2:
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt="请按‘目标-假设-验证’三段回答，每段一句。",
                rationale="结构化脚手架，提升监控能力。",
            )
        if level == ScaffoldLevel.L3:
            return ScaffoldResult(
                fired=True,
                level=level,
                prompt="我给你一个模板：1) 目标 2) 方法 3) 风险与修正。",
                rationale="强引导，适用于持续卡住场景。",
            )
        return ScaffoldResult(fired=False, level=None, prompt=None, rationale=None)
