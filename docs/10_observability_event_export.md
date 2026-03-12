# 10 可观测性与事件导出（Observability & Event Export）

## 10.1 Trace ID

实现位置：

- `backend/apps/api/middleware/trace.py`
- `backend/libs/observability.py`

行为：

- 若请求头已带 `x-trace-id`，则透传
- 否则生成 `trc_*`
- 响应 body 一定带 `trace_id`
- 响应 header 也会设置 `x-trace-id`

## 10.2 请求级日志与指标

`TraceIDMiddleware` 在每个请求结束时会：

- 写结构化日志 `request_completed`
- 记录 HTTP counter/histogram

指标包括：

- `http_requests_total{method,path,status_code}`
- `http_request_duration_seconds{method,path,status_code}`

注意：

- `path` 使用 route path，而不是原始 URL；这对 Prometheus 聚合很重要。

## 10.3 Turn 级阶段指标

在线回合中当前实际记录的阶段有：

- `asr`
- `prompt_injection`
- `preprocess`
- `safety`
- `trigger`
- `policy_llm`

对应指标：

- `turn_stage_latency_seconds{stage}`
- `turn_total_latency_seconds`

旧文档里提到的 `scaffold`、`evaluation` stage 当前并没有真正被 `observe_turn_stage()` 记录。

## 10.4 结构化日志

`libs/observability.py` 会输出 JSON 日志，常见字段包括：

- `ts`
- `level`
- `logger`
- `message`
- `event_type`
- `trace_id`
- `session_id`
- `turn_id`
- `candidate_id`
- `method`
- `path`
- `status_code`
- `latency_ms`
- `stage`

当前 LLM gateway 还会记录：

- `prompt`
- `prompt_chars`
- provider/model/timeout

这对排障有帮助，但也意味着日志中可能包含较多业务文本。

## 10.5 事件存储与导出

事件表是 `events`。

导出接口：

- `GET /api/v1/sessions/{session_id}/events/export`

导出格式：

- `text/plain`
- 每行一个 JSON

导出字段：

- `event_id`
- `session_id`
- `turn_id`
- `event_type`
- `payload`
- `ts`

排序规则：

- `created_at ASC`

## 10.6 管理端 review 状态的数据来源

虽然不是独立 observability 设施，但管理端的“是否 invalid / completed”实际上依赖 event history。

这意味着：

- 如果你新增终止原因
- 或新增 invalidation 机制

必须同步修改：

- `OrchestratorService._derive_session_review_status()`
- 管理端展示逻辑

否则 admin 页面状态会和真实会话结论不一致。
