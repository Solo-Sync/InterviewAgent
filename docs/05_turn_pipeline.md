# 05 单回合处理流水线（Turn Pipeline）

目标接口：`POST /api/v1/sessions/{session_id}/turns`

实现入口：`backend/services/orchestrator/service.py`

## 5.1 事务与并发控制

每个 turn 都在单个数据库事务中处理。

关键步骤：

1. `SELECT ... FOR UPDATE` 锁住 session
2. 读取当前最大 `turn_index`
3. 插入 turn
4. 更新 session
5. 追加 events

并发保护依赖：

- 行锁
- `(session_id, turn_index)` 唯一约束
- `(session_id, idempotency_key)` 唯一约束

若命中唯一约束冲突，`handle_turn()` 最多会尝试恢复/重试 3 次。

## 5.2 幂等键

当 `client_meta.client_timestamp` 存在时，会计算：

`sha256(session_id | utc_ts | input.type | text_or_audio_material)`

音频 material 的选择顺序：

- `audio_id`
- `audio_url`

命中相同幂等键时，会返回数据库里已存在的 turn，而不是重复创建。

## 5.3 输入解析

### 文本输入

- 直接使用 `input.text`

### 音频输入

支持三种来源：

- `audio_id`
- `audio_url=data:...;base64,...`
- `audio_url=http(s)://...`

其中远程 URL 必须满足：

- `ALLOW_REMOTE_AUDIO_FETCH=true`
- scheme 为 `http/https`
- host 在 allowlist 内，或 allowlist 为空
- host 必须解析到公网 IP
- 下载大小不超过 `REMOTE_AUDIO_MAX_BYTES`

## 5.4 正常回合的实际执行顺序

1. 锁定 session
2. 解析文本或音频
3. ASR（若是音频）
4. Prompt Injection 检测
5. preprocess
6. safety
7. trigger detection
8. 构造完整会话历史
9. LLM 决策 `next_action`
10. 时间规则/轮数规则覆盖
11. 组装 `Turn`
12. 持久化 turn、session、events
13. 若本轮结束，生成 report

## 5.5 Prompt Injection 分支

这是第一个分叉点，发生在 preprocess 之前。

处理细节：

- 仍会执行 preprocess
- 但会把 `clean_text` 强制替换成 `[prompt injection removed]`
- 不会执行 safety、trigger、评分

### 第一次命中

- `next_action=WAIT`
- 记录警告
- session 保持可继续

### 第二次命中

- `next_action=END`
- 会话被标记 `invalid`
- 不会生成 report

## 5.6 Safety 分支

当前 safety 非常轻量：

- 仅对固定敏感词做 `BLOCK`
- 不存在独立的 prompt injection sanitize 逻辑

命中 block 时：

- 当前 turn 仍会落库
- session 立即结束
- 立即生成 report

## 5.7 Trigger 检测

当前会识别：

- `SILENCE`
- `OFFTRACK`
- `LOOP`
- `HELP_KEYWORD`
- `STRESS_SIGNAL`

输入上下文包括：

- 当前 clean text
- 当前问题文本
- 最近 2 轮文本
- ASR 导出的最大静默时长
- session thresholds 里的 silence / loop 阈值

注意：

- `offtrack_threshold` 虽然在 `Thresholds` 里存在，但当前 `TriggerDetector` 并不使用它。

## 5.8 LLM 决策与覆盖规则

正常回合会调用 `LLMNextActionDecider`，拿到：

- `next_action_type`
- `interviewer_reply`
- `reasons`

然后再执行覆盖规则：

1. 单题 prompt 数达到 12，强制结束
2. 已到 30 分钟或已发过最后一问通知，强制结束
3. 25 到 30 分钟之间且未发通知，强制保留最后一问语义

## 5.9 当前不会执行的旧链路

在线主流程里当前不会做：

- `OrchestratorPolicy.choose_action()`
- `QuestionSelector.select_next()`
- turn 级 `ScoreAggregator.score()`
- `theta` 更新

如果后续要恢复这些能力，应该从 `handle_turn()` 而不是从文档假设出发。

## 5.10 关键事件序列

### 正常回合

通常包括：

- `turn_received`
- `asr_completed`（若有）
- `preprocess_completed`
- `trigger_detected`（0 到多条）
- `evaluation_completed`（但通常标记 skipped）
- `next_action_decided`

### safety block

额外包括：

- `safety_blocked`
- `report_generated`

### prompt injection 首次命中

额外包括：

- `prompt_injection_detected`
- `prompt_injection_warned`

### prompt injection 二次命中

额外包括：

- `prompt_injection_detected`
- `session_invalidated`
