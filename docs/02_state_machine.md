# 02 状态机与决策（State Machine）

## 2.1 会话状态

代码定义（`libs/schemas/base.py`）：
- `S_INIT`
- `S_WAIT`
- `S_PROBE`
- `S_SCAFFOLD`
- `S_EVAL_RT`
- `S_END`

## 2.2 状态迁移规则

`services/orchestrator/state_machine.py` 的规则：
- next_action=`END` -> `S_END`
- next_action=`SCAFFOLD` -> `S_SCAFFOLD`
- next_action=`PROBE` -> `S_PROBE`
- next_action=`WAIT` -> `S_WAIT`
- 其余情况：
  - 若当前是 `S_INIT` -> `S_WAIT`
  - 否则 -> `S_EVAL_RT`

## 2.3 trigger -> action 策略

`services/orchestrator/policy.py`：
- 含 `STRESS_SIGNAL` -> `SCAFFOLD` + `L1`
- 含 `HELP_KEYWORD` -> `SCAFFOLD` + `L2`
- 含 `OFFTRACK` 或 `LOOP` -> `SCAFFOLD` + `L1`
- 否则 -> `PROBE`

说明：`SILENCE` 当前只作为触发记录，不直接单独映射动作（除非同时命中其他规则）。

## 2.4 next_action 生成优先级

在 `handle_turn()` 中：
1. safety block：直接 `END`
2. policy 给出 scaffold/calm：优先输出对应提示
3. 若 LLM 决策失败则走 `QuestionSelector.select_next()` 兜底：
- 可输出 `ASK` / `PROBE`
- 题库耗尽时输出 `END`

## 2.5 session 结束

- 主动结束：`POST /sessions/{id}/end`
- 安全策略结束：safety block 时直接进入 `S_END`
- 自动结束：题库选择器 exhausted 时 next_action=`END`
