# 03 数据模型与存储（Data Model）

本节描述**服务端内部存储**（不改变 OpenAPI 契约），并确保所有契约对象可被无损持久化与回放。

---

## 3.1 核心实体（与 OpenAPI schema 对齐）

### 3.1.1 Session（契约：`Session`）
关键字段：
- `session_id`：全局唯一
- `candidate`：Candidate（candidate_id, display_name）
- `mode`：例如 `mvp_text` / `voice` / `debug`
- `state`：SessionState
- `question_set_id` / `scoring_policy_id` / `scaffold_policy_id`
- `thresholds`：silence_s / offtrack_threshold / loop_threshold
- `created_at`

**内部扩展（建议）**
- `ended_at`
- `current_question_cursor`：题库树位置（方便挑选下一个 probe/扰动）
- `theta`：θ={plan, monitor, evaluate, adapt} 的运行估计（可写入报告或缓存）

### 3.1.2 Turn（契约：`Turn`）
Turn 是一次完整处理的快照：
- 输入：TurnInput（text 或 audio_ref）
- ASR：AsrResult（raw_text, tokens, silence_segments, audio_features）
- preprocess：PreprocessResult（clean_text, filler_stats, hesitation_rate）
- triggers：Trigger[]
- scaffold：ScaffoldResult（fired, level, prompt, rationale）
- evaluation：EvaluationResult（scores, evidence, votes, discounts, confidence）
- next_action：NextAction（type, text, level, payload）
- state_before / state_after（用于回放状态机）
- created_at

---

## 3.2 事件溯源（Event Stream）

### 3.2.1 为什么要 Event Stream
- 回放：逐步还原决策过程（包含 safety、trigger、LLM 评分与提示）
- 离线评估：对同一份数据运行新策略（A/B）而不污染原始记录
- 审计：安全拦截、敏感处理的可追踪性

### 3.2.2 Event 结构（建议）
不新增契约 schema，作为内部表与 `/events/export` 输出格式：

```json
{
  "event_id": "evt_...",
  "session_id": "sess_...",
  "turn_id": "turn_...",
  "ts": "2026-02-09T10:00:00Z",
  "event_type": "trigger_detected",
  "payload": { "type": "OFFTRACK", "score": 0.82, "detail": "..." }
}
```

常见 event_type：
- session_created / session_ended
- turn_received / asr_completed / preprocess_completed
- safety_blocked / safety_sanitized
- trigger_detected (SILENCE/OFFTRACK/LOOP/HELP/ STRESS)
- scaffold_fired (level, prompt_hash)
- evaluation_completed (scores, confidence, judge_ids)
- next_action_decided (type, payload)
- goal_reset_detected（适应能力异常跳转）

---

## 3.3 推荐数据库表设计（Postgres 示例）

### 3.3.1 sessions
- `session_id` TEXT PK
- `candidate_id` TEXT
- `candidate_display_name` TEXT NULL
- `mode` TEXT
- `state` TEXT
- `question_set_id` TEXT
- `scoring_policy_id` TEXT
- `scaffold_policy_id` TEXT
- `thresholds` JSONB
- `theta` JSONB NULL
- `created_at` TIMESTAMPTZ
- `ended_at` TIMESTAMPTZ NULL

索引：
- (candidate_id, created_at desc)
- (state)

### 3.3.2 turns
- `turn_id` TEXT PK
- `session_id` TEXT FK
- `turn_index` INT
- `state_before` TEXT
- `state_after` TEXT
- `question` JSONB
- `input` JSONB
- `asr` JSONB NULL
- `preprocess` JSONB NULL
- `triggers` JSONB NULL
- `scaffold` JSONB NULL
- `evaluation` JSONB NULL
- `next_action` JSONB
- `created_at` TIMESTAMPTZ

索引：
- UNIQUE(session_id, turn_index)
- (session_id, created_at)
- GIN(triggers), GIN(evaluation)（便于分析）

### 3.3.3 events
- `event_id` TEXT PK
- `session_id` TEXT
- `turn_id` TEXT NULL
- `event_type` TEXT
- `payload` JSONB
- `created_at` TIMESTAMPTZ

索引：
- (session_id, created_at)
- (event_type, created_at)

### 3.3.4 human_annotations
- `id` BIGSERIAL PK
- `session_id` TEXT
- `turn_id` TEXT
- `human_scores` JSONB
- `evidence` JSONB NULL
- `notes` TEXT NULL
- `created_at` TIMESTAMPTZ

索引：
- (turn_id)
- (created_at desc)

---

## 3.4 音频与文件存储（Object Storage）

- 原始音频：按 `audio_id` 存储
- 派生文件：
  - 事件导出 JSONL（`/sessions/{id}/events/export`）
  - 可选：评分回归集切片（抽样后的 turns）

建议：
- 用 **内容哈希** 做去重（同音频重复上传）
- 音频默认短期保留（见 13_privacy_and_compliance.md）

---

## 3.5 模型分层与单一来源（新增约定）

- `libs/schemas/*.py` 是 API 契约模型唯一来源（与 `openapi.yaml` 对齐）。
- `services/*` 可以有内部领域模型，但必须通过 adapter 显式映射到契约模型。
- 禁止在不同目录并行维护“同名不同义”模型（例如重复定义 `AsrResult`/`Turn`）。
- 评审标准：对外接口字段变更必须先更新 `openapi.yaml` 与 `libs/schemas`，再改 service 实现。
