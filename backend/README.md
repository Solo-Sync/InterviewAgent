# Backend

FastAPI backend for metacog-interview.

## Run

```bash
uv sync
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

API prefix: `/api/v1`.

Protected endpoints require `Authorization: Bearer <token>`.
Set `API_BEARER_TOKEN` to enforce a specific token value. If left empty, any non-empty bearer token is accepted.
