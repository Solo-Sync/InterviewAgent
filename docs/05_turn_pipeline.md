# 05 单回合处理流水线（Turn Pipeline）

目标接口：`POST /sessions/{session_id}/turns`

## 5.1 事务与并发

- 使用数据库事务包裹整个回合
- 先 `SELECT ... FOR UPDATE` 锁 session 行
- `turn_index` 在事务内按最大值+1生成
- 依赖唯一约束处理并发冲突并重试

## 5.2 幂等键

当 `client_meta.client_timestamp` 存在时生成：
- `sha256(session_id|utc_timestamp|input.type|text_or_audio_ref)`

冲突恢复：若命中 `(session_id, idempotency_key)` 唯一约束，直接返回已存在 turn。

## 5.3 实际处理顺序

1. load + lock session
2. 解析输入文本
- text：直接使用
- audio_ref：读取 `audio_id` 或 `audio_url`
3. ASR（仅 audio_ref）
4. preprocess
5. safety
- block：直接 END，跳过 trigger/scaffold/eval
- sanitize：替换 clean_text 并记录事件
6. trigger detection（含 recent turns）
7. policy + scaffold
8. evaluation
9. update theta（EMA, alpha=0.7）
10. selector 选下一提示（非 scaffold/calm 场景）
11. 持久化 turn/session/events

## 5.4 audio_ref 处理边界

支持：
- `audio_id`（本地文件键）
- `audio_url=data:*;base64,...`
- `audio_url=http(s)`（仅当 `ALLOW_REMOTE_AUDIO_FETCH=true`）

远程 URL 限制：
- 可选 host allowlist（`REMOTE_AUDIO_ALLOWED_HOSTS`）
- 主机必须解析为公网 IP
- 大小限制 `REMOTE_AUDIO_MAX_BYTES`

## 5.5 关键事件

每回合至少会有：
- `turn_received`
- `preprocess_completed`
- `evaluation_completed`（若未被 safety block）
- `next_action_decided`
