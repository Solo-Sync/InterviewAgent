# 03 数据模型与存储（Data Model）

## 3.1 对外契约模型

定义位置：

- `backend/libs/schemas/base.py`
- `backend/libs/schemas/api.py`

最重要的对象如下。

### Session

关键字段：

- `session_id`
- `candidate`
- `mode`
- `state`
- `question_set_id`
- `scoring_policy_id`
- `scaffold_policy_id`
- `thresholds`
- `current_question_cursor`
- `theta`
- `created_at`

说明：

- `theta` 当前在线主流程不更新，但 schema 和数据库都保留。

### Turn

关键字段：

- `turn_id`
- `turn_index`
- `question`
- `input`
- `asr`
- `preprocess`
- `triggers`
- `scaffold`
- `evaluation`
- `next_action`
- `state_before`
- `state_after`
- `created_at`

说明：

- 在线主流程生成的 turn 通常 `evaluation=None`。

### Report

关键字段：

- `overall`
- `timeline`
- `conversation`
- `llm_scoring`
- `notes`

说明：

- `timeline` 当前若没有 turn 级评分，会对每个 turn 复用同一个 `overall` 分数。
- `llm_scoring.turns` 会保留每轮问答，但其中 `scores` 常常为 `None`。

## 3.2 PostgreSQL 表

定义位置：`backend/libs/storage/postgres.py`

### `sessions`

- 主键：`session_id`
- JSON 列：
  - `candidate`
  - `thresholds`
  - `current_question_cursor`
  - `theta`
  - `last_next_action`
- 时间列：
  - `created_at`
  - `ended_at`

### `turns`

- 主键：`turn_id`
- `turn_payload` 保存完整 `Turn` contract 快照
- 唯一约束：
  - `(session_id, turn_index)`
  - `(session_id, idempotency_key)`

### `events`

- 主键：`event_id`
- 每条 event 都包含：
  - `session_id`
  - `turn_id`
  - `event_type`
  - `payload`
  - `created_at`

### `reports`

- 一个 session 对应一条 report
- `report_payload` 保存完整 `Report`

### `annotations`

- 自增主键
- 记录 annotator 提交的人类分数、notes、evidence

## 3.3 Alembic 迁移来源

当前 schema 由两条迁移建立：

- `20260228_0001_baseline_schema.py`
- `20260303_0002_dynamic_question_state.py`

第二条迁移新增：

- `sessions.current_question_cursor`
- `sessions.theta`

## 3.4 事件类型

当前代码里实际会写入的事件包括：

- `session_created`
- `turn_received`
- `asr_completed`
- `preprocess_completed`
- `prompt_injection_detected`
- `prompt_injection_warned`
- `safety_blocked`
- `safety_sanitized`
- `trigger_detected`
- `scaffold_fired`
- `evaluation_completed`
- `next_action_decided`
- `report_generated`
- `session_ended`
- `session_invalidated`
- `annotation_created`

并不是每个 session 都会出现所有事件。

## 3.5 Review Status 的来源

管理端看到的 `review_status` 不是数据库列，而是派生值。

派生逻辑在 `OrchestratorService._derive_session_review_status()`：

1. 若存在 `session_invalidated` 事件，状态为 `invalid`
2. 否则若已有 report，或 session.state 已是 `S_END`，状态为 `completed`
3. 否则为 `in-progress`

同时会统计：

- `prompt_injection_count`
- `invalid_reason`

## 3.6 Cursor 与分页

`GET /sessions/{id}/turns` 的 cursor 是 base64 编码后的 `CursorEnvelope`：

- `offset`
- `ts`

这是 offset-based pagination，而不是稳定快照分页。文档和调用方都不应把它当作强一致游标。
