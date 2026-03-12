# 06 脚手架引擎（Scaffolding Engine）

## 6.1 当前有两条“脚手架”路径

### 路径 A：工具接口显式生成

入口：

- `POST /api/v1/scaffold/generate`

实现：

- `services/scaffold/generator.py`
- `services/dialogue/generator.py`

这条路径会真正根据 `ScaffoldLevel` 调用 `DialogueGenerator` 生成中文引导语。

### 路径 B：在线主流程中由 LLM 直接决定 `SCAFFOLD`

入口：

- `OrchestratorService.handle_turn()`

这条路径不会调用 `ScaffoldGenerator.generate()`，而是直接把 LLM 返回的话术包装成：

- `ScaffoldResult(fired=True, level=None, prompt=next_action.text, rationale="llm_selected_scaffold")`

## 6.2 `ScaffoldGenerator` 的真实行为

当前内置模板种子如下：

- `L1`
  - `先明确目标，再列出两步可执行计划。`
- `L2`
  - `请按‘目标-假设-验证’三段回答，每段一句。`
- `L3`
  - `我给你一个模板：1) 目标 2) 方法 3) 风险与修正。`

随后会把上下文交给 `DialogueGenerator` 进行润色生成。

额外约束：

- `create_session()` 传入的 `scaffold_policy_id` 当前不是读某个 JSON 资源
- 后端只会校验它是否存在于 `settings.scaffold_policy_ids`
- 这组 id 来自环境变量 `SCAFFOLD_POLICY_IDS`

返回结构包括：

- `fired`
- `level`
- `prompt`
- `rationale`

## 6.3 当前未接线的自动触发策略

`services/orchestrator/policy.py` 定义了：

- `HELP_KEYWORD -> SCAFFOLD + L2`
- `OFFTRACK / LOOP / STRESS_SIGNAL -> SCAFFOLD + L1`
- 其他 -> `PROBE`

但这套规则当前没有在 `handle_turn()` 中使用。

结论：

- trigger 会被检测
- policy 类会存在
- 但在线回合不会自动按这套规则调用 `ScaffoldGenerator`

## 6.4 与评分折扣的关系

折扣逻辑在 `services/evaluation/discount.py`，只对 `ScoreAggregator.score()` 生效。

当前规则：

- `L1`
  - 不折扣
- `L2`
  - `monitor * 0.9`
  - `evaluate * 0.9`
- `L3`
  - `plan * 0.8`
  - `monitor * 0.75`
  - `evaluate * 0.75`

重要限制：

- 主流程在线回合当前不做 turn 级评分，因此在线会话里即使出现 `next_action=SCAFFOLD`，也不会自动触发这些折扣。
- 这些折扣目前主要服务于 `/evaluation/*` 工具接口。

## 6.5 事件记录

只有当在线主流程中最终 `next_action.type == SCAFFOLD` 时，才会写：

- `scaffold_fired`

而工具接口 `/scaffold/generate` 本身不会写 session event。

## 6.6 开发建议

若后续要恢复“trigger 驱动脚手架”的原设计，应至少同时修改：

- `services/orchestrator/service.py`
- `services/orchestrator/policy.py`
- `services/scaffold/generator.py`
- `apps/api/core/config.py`
- `services/evaluation/discount.py`
- `docs/02_state_machine.md`
- `docs/05_turn_pipeline.md`
