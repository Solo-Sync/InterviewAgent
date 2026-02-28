# Backend

FastAPI backend for metacog-interview.

## Run

```bash
uv sync
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

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
Set `AUTH_TOKEN_SECRET`, `ADMIN_LOGIN_*`, and `ANNOTATOR_LOGIN_*` in server-side env for non-demo deployments.
