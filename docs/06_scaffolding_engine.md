# 06 脚手架引擎（Scaffolding Engine）

## 6.1 当前实现

生成器：`services/scaffold/generator.py`

- L1：`先明确目标，再列出两步可执行计划。`
- L2：`请按‘目标-假设-验证’三段回答，每段一句。`
- L3：保留能力，但主流程策略当前不会自动触发

## 6.2 触发策略（当前）

来自 `OrchestratorPolicy`：
- `HELP_KEYWORD` -> `SCAFFOLD L2`
- `OFFTRACK` 或 `LOOP` -> `SCAFFOLD L1`
- `STRESS_SIGNAL` -> `SCAFFOLD L1`

## 6.3 与评分折扣联动

折扣定义在 `services/evaluation/discount.py`：
- L1：不折扣
- L2：`monitor/evaluate * 0.9`
- L3：`plan * 0.8`, `monitor/evaluate * 0.75`

## 6.4 事件记录

脚手架触发会写：
- `scaffold_fired`（包含 level/prompt/rationale）
