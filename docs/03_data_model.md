# 03 数据模型与存储（Data Model）

## 3.1 领域模型（Pydantic）

定义位置：`backend/libs/schemas/base.py` 与 `backend/libs/schemas/api.py`

核心对象：
- `Session`：含 `current_question_cursor`、`theta`
- `Turn`：含 input/asr/preprocess/triggers/scaffold/evaluation/next_action
- `EvaluationResult`：含 `scores/evidence/judge_votes/final_confidence/discounts`
- `Report`：`overall + timeline + notes`

## 3.2 PostgreSQL 表（实际）

定义位置：`backend/libs/storage/postgres.py`

- `sessions`
  - `session_id` PK
  - `mode/state/question_set_id/scoring_policy_id/scaffold_policy_id`
  - `candidate` JSON
  - `thresholds` JSON
  - `current_question_cursor` JSON
  - `theta` JSON
  - `last_next_action` JSON
  - `created_at/ended_at`

- `turns`
  - `turn_id` PK
  - `session_id`, `turn_index`
  - `state_before/state_after`
  - `idempotency_key`
  - `turn_payload` JSON（完整 Turn 快照）
  - 唯一约束：`(session_id, turn_index)`、`(session_id, idempotency_key)`

- `events`
  - `event_id` PK
  - `session_id/turn_id/event_type/payload/created_at`

- `reports`
  - `session_id` PK
  - `report_payload` JSON

- `annotations`
  - 自增 `id`
  - `session_id/turn_id/human_scores/notes/evidence/created_at`

## 3.3 事件流（实际事件类型）

当前代码会写入：
- `session_created`
- `turn_received`
- `asr_completed`
- `preprocess_completed`
- `safety_blocked`
- `safety_sanitized`
- `trigger_detected`
- `scaffold_fired`
- `evaluation_completed`
- `next_action_decided`
- `session_ended`
- `annotation_created`

## 3.4 游标与分页

- turn 列表分页 cursor 为 base64 的 `CursorEnvelope(offset, ts)`
- 无效 cursor 返回 `INVALID_ARGUMENT`
