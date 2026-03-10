# 10 可观测性与事件导出（Observability & Event Export）

## 10.1 trace_id

- 中间件 `TraceIDMiddleware` 负责生成/透传 `x-trace-id`
- 所有响应 body 含 `trace_id`
- 响应 header 也包含 `x-trace-id`

## 10.2 日志

- `libs/observability.py` 输出 JSON 结构化日志
- 核心字段：`event_type/trace_id/session_id/turn_id/path/status_code/latency_ms`

## 10.3 指标（/metrics）

当前内置指标：
- `http_requests_total{method,path,status_code}`
- `http_request_duration_seconds{method,path,status_code}`
- `turn_stage_latency_seconds{stage}`
- `turn_total_latency_seconds`

turn stage 观测点：`asr/preprocess/safety/trigger/scaffold/evaluation`。

## 10.4 事件导出

接口：`GET /sessions/{session_id}/events/export`

- 输出：JSONL 文本（每行一个 event JSON）
- 数据源：`events` 表按 `created_at ASC`
- 字段：`event_id/session_id/turn_id/event_type/payload/ts`
