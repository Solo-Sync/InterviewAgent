# 04 接口契约映射（API Contract Mapping）

## 4.1 统一响应封装

后端统一返回：

- 成功：`{ ok: true, data, error: null, trace_id }`
- 失败：`{ ok: false, data: null, error, trace_id }`

实现位置：`backend/apps/api/core/response.py`

常见错误码：

- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `CONFLICT`
- `INTERNAL`

## 4.2 认证与角色

### `POST /api/v1/auth/token`

公开接口。

支持角色：

- `candidate`
- `admin`
- `annotator`

认证方式：

- `candidate`
  - 使用 `email + invite_token`
  - 数据源是 `CANDIDATE_REGISTRY_PATH`
- `admin`
  - 使用 `ADMIN_LOGIN_EMAIL / PASSWORD`
- `annotator`
  - 使用 `ANNOTATOR_LOGIN_EMAIL / PASSWORD`

签发结果是后端自定义 HMAC 签名 token，不依赖外部 JWT 库。

## 4.3 Session 相关接口

这些接口都要求 `candidate` 角色，并且做 session 归属校验。

- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/turns`
- `GET /api/v1/sessions/{session_id}/turns`
- `POST /api/v1/sessions/{session_id}/end`
- `GET /api/v1/sessions/{session_id}/report`
- `GET /api/v1/sessions/{session_id}/events/export`

特殊行为：

- `create_session`
  - `body.candidate.candidate_id` 必须等于 token 里的 `candidate_id`
  - `question_set_id` 必须对应 `backend/data/question_sets/{id}.json`
  - `scoring_policy_id` 必须对应 `backend/data/rubrics/{id}.json`
  - `scaffold_policy_id` 必须存在于环境变量 `SCAFFOLD_POLICY_IDS`
- `create_turn`
  - 可能返回 502：
    - `next action llm decision failed`
    - `prompt injection detection failed`
- `list_turns`
  - 非法 cursor 返回 400
- `events/export`
  - 返回 `text/plain`
  - 内容是 JSONL，不再包 `ApiResponse`

## 4.4 工具接口

这些接口在 `app.include_router()` 时被挂上了统一依赖：

- 允许 `admin`
- 允许 `annotator`

接口包括：

- `POST /api/v1/asr/transcribe`
- `POST /api/v1/nlp/preprocess`
- `POST /api/v1/safety/check`
- `POST /api/v1/scaffold/generate`
- `POST /api/v1/evaluation/score`
- `POST /api/v1/evaluation/batch_score`

说明：

- 这些接口本质上是调试/离线工具接口，不是候选人主流程必经路径。

## 4.5 管理接口

这些接口要求 `admin`：

- `GET /api/v1/admin/question_sets`
- `GET /api/v1/admin/question_sets/{question_set_id}`
- `GET /api/v1/admin/rubrics`
- `GET /api/v1/admin/rubrics/{rubric_id}`
- `GET /api/v1/admin/sessions`
- `GET /api/v1/admin/sessions/{session_id}`

数据来源：

- 题库与量表直接读 `backend/data/*.json`
- 会话详情来自 `OrchestratorService`

## 4.6 标注接口

### `POST /api/v1/sessions/{session_id}/annotations`

要求 `annotator`。

行为：

- 校验 session 存在
- 校验 `turn_id` 属于该 session
- 写入 `annotations` 表
- 追加 `annotation_created` event

## 4.7 健康与指标

公开接口：

- `GET /api/v1/health`
- `GET /api/v1/metrics`

`health` 会聚合：

- LLM readiness
- ASR readiness

## 4.8 前端代理层的对应关系

浏览器常见入口不是直接调后端，而是：

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `/api/v1/*`

其中：

- `frontend/app/api/auth/login/route.ts`
  调后端 `/api/v1/auth/token`
- `frontend/app/api/v1/[...path]/route.ts`
  把 cookie 中的 access token 转成 `Authorization: Bearer ...`

所以当你修改后端接口权限或 header 语义时，必须同时检查前端 route handler。
