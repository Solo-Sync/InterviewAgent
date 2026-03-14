# 02 状态机与决策（State Machine）

## 2.1 状态枚举

定义位置：`backend/libs/schemas/base.py`

- `S_INIT`
- `S_WAIT`
- `S_PROBE`
- `S_SCAFFOLD`
- `S_EVAL_RT`
- `S_END`

## 2.2 状态迁移函数

定义位置：`backend/services/orchestrator/state_machine.py`

迁移逻辑非常简单，只取决于当前 `next_action.type`：

- `END -> S_END`
- `SCAFFOLD -> S_SCAFFOLD`
- `PROBE -> S_PROBE`
- `WAIT -> S_WAIT`
- 其他动作：
  - 若当前是 `S_INIT`，迁移到 `S_WAIT`
  - 否则迁移到 `S_EVAL_RT`

注意：

- `ASK` 不会单独映射到某个显式 `S_ASK` 状态。
- `S_EVAL_RT` 是历史上保留下来的命名；当前在线回合里并不会真的执行 real-time turn scoring。

## 2.3 在线 `next_action` 的真实来源

正常回合中，`next_action` 的优先级如下：

1. prompt injection 处置
2. safety block
3. LLM `next_action` 决策
4. 时间规则覆盖
5. 单题轮数上限覆盖

这里最关键的一点是：

- `OrchestratorPolicy.choose_action()` 当前没有接入主流程
- triggers 不再直接映射动作

## 2.4 Prompt Injection 分支

Prompt injection 检测发生在 preprocess 之前。

### 第一次命中

- 写 `prompt_injection_detected`
- `next_action = WAIT`
- `next_action.text` 是警告语
- `payload.interview_status = in-progress`
- session 不结束
- question cursor 保留

### 第二次命中

- 写第二次 `prompt_injection_detected`
- 写 `session_invalidated`
- `next_action = END`
- `payload.interview_status = invalid`
- session 结束
- 不生成 report

## 2.5 Safety 分支

当前 `SafetyClassifier` 只会返回两类结果：

- `ALLOW`
- `BLOCK`

命中 `BLOCK` 时：

- 立即返回 `END`
- 当前 turn 写入数据库
- session 进入 `S_END`
- 立即生成 report

## 2.6 正常回合的 LLM 决策

正常回合会把完整会话历史传给 `LLMNextActionDecider.decide()`。

LLM 只允许返回：

- `ASK`
- `PROBE`
- `SCAFFOLD`
- `END`

如果返回 `SCAFFOLD`：

- turn 中会记录一个 `ScaffoldResult`
- `level` 为 `None`
- `prompt` 直接使用 LLM 返回的 `interviewer_reply`
- 不会调用 `ScaffoldGenerator`

## 2.7 时间规则覆盖

时间规则在 LLM 决策后执行，优先级高于 LLM 输出。

### 25 分钟到 30 分钟之间

若 `25 <= elapsed_minutes < 30` 且尚未发出最后一问通知：

- 本轮不能直接结束
- 若 LLM 返回的不是 `ASK/PROBE`，会被强制改成 `PROBE`
- 返回文本前会拼上“最后一次提问”通知
- `QuestionCursor.asked_prompt_ids` 会插入内部 marker

### 已发出最后一问通知，或已到 30 分钟

- 本轮强制 `END`
- 文本固定为结束语

## 2.8 单题轮数上限

当前实现把一个 prompt 序列视为“同一道题的对话链”。

规则：

- 若 `QuestionCursor.asked_prompt_ids` 中的 prompt 数量达到 `12`
- 会强制 `END`

注意：

- 这里计数的是 prompt id 数量，而不是题库节点数量
- 当前后续 prompt 大多是 `llm:ask:*` 或 `llm:probe:*`

## 2.9 Question Cursor 的真实行为

`create_session()` 时：

- cursor 来自 `QuestionSelector.random_opening_selection()`
- opening prompt 会附加一句“不要着急作答，先说说你打算怎么做。”

后续正常回合：

- 若未结束，cursor 会改写成 `llm:{action}:{turn_index}`
- 不再沿用 `QuestionSelector.select_next()` 的题树推进逻辑

因此当前 question set 的 `probes / perturbations / children` 更像“可用结构”，而不是在线路径里的实际驱动器。
