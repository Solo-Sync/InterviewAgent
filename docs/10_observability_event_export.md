# 10 可观测性与事件导出（Observability & Event Export）

---

## 10.1 trace_id 贯穿全链路
契约的所有 ApiResponse 都带 `trace_id`。工程实现建议：
- 入口中间件生成 trace_id（若客户端未提供）
- 注入到：
  - 日志（structured logs）
  - OpenTelemetry trace/span
  - 事件表 events
- 返回给客户端，前端报错时可直接带 trace_id

---

## 10.2 关键指标（Metrics）

### 10.2.1 交互体验
- `turn_latency_ms{stage=preprocess|safety|eval|scaffold}`
- `turn_total_latency_ms`
- `llm_timeout_rate{judge_id=...}`

### 10.2.2 策略有效性
- `trigger_rate{type=...}`
- `scaffold_rate{level=...}`
- `scaffold_effect_delta{dimension=...}`：脚手架后分数变化
- `offtrack_recovery_turns`：跑题后恢复平均回合数

### 10.2.3 评分稳定性
- `judge_disagreement{dimension=...}`：评委分歧度
- `final_confidence_histogram`

---

## 10.3 日志（Logs）
建议按事件写结构化日志（JSON）：
- session_id, turn_id, trace_id
- state_before/state_after
- trigger 列表（含 score）
- scaffold level（含 prompt_hash）
- evaluation scores（不写原文可写 hash，按隐私策略）

---

## 10.4 事件导出（/sessions/{id}/events/export）

### 10.4.1 输出格式
- Content-Type: text/plain
- 每行一个 JSON（JSONL）
- 便于：
  - 直接 `jq` 分析
  - 导入到 Spark/BigQuery
  - 训练数据集构建

### 10.4.2 导出内容建议
至少包含：
- session_created / session_ended
- 每回合：turn_received, preprocess_completed, triggers, scaffold, evaluation, next_action
- safety 命中：safety_blocked/sanitized

### 10.4.3 脱敏策略
- 默认导出 **不包含原始音频**  
- 对回答文本：
  - 可导出 clean_text（脱敏后）或导出 hash + 引用片段（EvidenceSpan.quote）
  - 具体见 13_privacy_and_compliance.md

---

## 10.5 调试模式与生产模式
建议通过 `mode` 或配置开关控制：
- Debug：返回更完整的 turn（含 triggers/scaffold/evaluation）
- Prod：仅返回 next_action + 必要的评分摘要（降低信息泄露风险）

