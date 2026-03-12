# 11 部署与运行（Deployment）

## 11.1 本地最小运行拓扑

当前本地开发最小需要：

- 1 个 PostgreSQL
- 1 个 FastAPI 后端
- 1 个 Next.js 前端

## 11.2 启动 PostgreSQL

仓库根目录：

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

## 11.3 启动后端

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

关键点：

- 必须先迁移数据库
- SQLite 会被显式拒绝

## 11.4 启动前端

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

默认前端地址：

- `http://127.0.0.1:8080`

默认后端地址：

- `http://127.0.0.1:8000`

## 11.5 PostgreSQL-only 约束

下面两层都会拒绝非 PostgreSQL：

- `apps/api/core/config.py`
- `libs/storage/postgres.py`

因此不要尝试用 SQLite 跑本地 demo。

## 11.6 关键环境变量

### 基础运行

- `DATABASE_URL`
- `API_PREFIX`
- `APP_ENV`
- `AUTH_TOKEN_SECRET`

### 账号体系

- `ADMIN_LOGIN_EMAIL`
- `ADMIN_LOGIN_PASSWORD`
- `ANNOTATOR_LOGIN_EMAIL`
- `ANNOTATOR_LOGIN_PASSWORD`
- `CANDIDATE_REGISTRY_PATH`
- `SCAFFOLD_POLICY_IDS`

### 音频远程拉取

- `ALLOW_REMOTE_AUDIO_FETCH`
- `REMOTE_AUDIO_MAX_BYTES`
- `REMOTE_AUDIO_ALLOWED_HOSTS`

### LLM

- `LLM_GATEWAY_PROVIDER`
- `LLM_GATEWAY_BASE_URL`
- `LLM_GATEWAY_API_KEY`
- `OPENAI_API_KEY`
- `DASHSCOPE_API_KEY`
- `LLM_MODEL_NAME`
- `NEXT_ACTION_MODEL_NAME`
- `PROMPT_INJECTION_MODEL_NAME`
- `SESSION_EVAL_MODEL`
- `DIALOGUE_MODEL_NAME`

### ASR

- `ASR_MODEL_NAME`
- `ASR_VAD_MODEL`
- `ASR_PUNC_MODEL`
- `ASR_DEVICE`
- `ASR_ENABLE_VAD`
- `ASR_ENABLE_PUNC`

## 11.7 非 dev 环境的启动保护

当 `APP_ENV != dev` 时，后端会拒绝以下默认值：

- `AUTH_TOKEN_SECRET=dev-auth-secret`
- `ADMIN_LOGIN_PASSWORD=password123`
- `ANNOTATOR_LOGIN_PASSWORD=password123`

这是当前唯一的基础防误启动保护。

## 11.8 前端鉴权与代理部署含义

前端当前采用：

- `HttpOnly` cookie 保存 access token
- Next.js route handler 代理到后端

因此生产部署时至少要保证：

- 前端服务端能够访问后端 `BACKEND_ORIGIN`
- cookie 域与路径配置正确
- 反向代理不要吞掉 `Authorization` 与 `x-trace-id`

## 11.9 健康检查的解释

`GET /api/v1/health` 聚合：

- `LLMGateway.readiness()`
- `FunASREngine.readiness()`

返回值可能是：

- `ready`
- `degraded`
- `not_configured`
- `unavailable`

这更适合“开发态/集成态可用性提示”，而不是完整生产探针。
