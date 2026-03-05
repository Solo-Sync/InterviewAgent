# Backend

FastAPI backend for metacog-interview.

## Run

Backend is PostgreSQL-only. SQLite is not supported.

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

应用启动前必须先执行数据库迁移；后端不再通过运行时 `create_all()` 自动建表。
本地若未运行 PostgreSQL，可在仓库根目录执行 `docker compose -f infra/docker-compose.yml up -d postgres`。

使用 `.env` 指定阿里云 DashScope：

```bash
LLM_GATEWAY_PROVIDER=aliyun
DASHSCOPE_API_KEY=<your-key>
LLM_MODEL_NAME=qwen-plus
```

多评委模型可用 `EVAL_JUDGE_MODELS`（逗号分隔）覆盖，例如：

```bash
EVAL_JUDGE_MODELS=qwen-plus,qwen-max,qwen-turbo
```

API prefix: `/api/v1`.

Protected endpoints require a signed `Authorization: Bearer <token>`.
Use `POST /api/v1/auth/token` to mint role-scoped tokens for `candidate`, `admin`, or `annotator`.
Candidate login is validated against `CANDIDATE_REGISTRY_PATH` using `email + invite_token`.
Set `APP_ENV`, `AUTH_TOKEN_SECRET`, `ADMIN_LOGIN_*`, `ANNOTATOR_LOGIN_*`, and `CANDIDATE_REGISTRY_PATH` in server-side env for non-demo deployments.
When `APP_ENV` is not `dev`, default secrets and default admin/annotator passwords will fail startup.
