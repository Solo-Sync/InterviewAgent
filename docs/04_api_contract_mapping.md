# 04 接口契约映射（API Contract Mapping）

## 4.1 认证与角色

### POST /auth/token（公开）
- 输入：`role + email + password`
- `candidate` 使用 `CANDIDATE_REGISTRY_PATH` 中 `email + invite_token` 校验
- 输出：签名 bearer token（含 role/candidate_id）

## 4.2 system

### GET /health（公开）
- 返回 `status/llm_status/asr_status` 与 detail

### GET /metrics（公开）
- Prometheus 文本格式

## 4.3 sessions（candidate）

- `POST /sessions`
- `GET /sessions/{session_id}`
- `POST /sessions/{session_id}/turns`
- `GET /sessions/{session_id}/turns`
- `POST /sessions/{session_id}/end`
- `GET /sessions/{session_id}/report`
- `GET /sessions/{session_id}/events/export`

说明：会话归属强校验，candidate 只能访问自己的 session。

## 4.4 工具接口（admin / annotator）

- `POST /asr/transcribe`
- `POST /nlp/preprocess`
- `POST /safety/check`
- `POST /scaffold/generate`
- `POST /evaluation/score`
- `POST /evaluation/batch_score`

## 4.5 admin（admin）

- `GET /admin/question_sets`
- `GET /admin/question_sets/{question_set_id}`
- `GET /admin/rubrics`
- `GET /admin/rubrics/{rubric_id}`
- `GET /admin/sessions`
- `GET /admin/sessions/{session_id}`

## 4.6 annotation（annotator）

- `POST /sessions/{session_id}/annotations`

## 4.7 响应与错误约定

- 成功：`{ok:true,data,error:null,trace_id}`
- 失败：`{ok:false,data:null,error,trace_id}`
- 常见错误码：
  - `INVALID_ARGUMENT`
  - `NOT_FOUND`
  - `UNAUTHORIZED`
  - `FORBIDDEN`
  - `CONFLICT`
  - `INTERNAL`
