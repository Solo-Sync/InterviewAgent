# metacog-interview

前后端分离单仓库：根目录采用 `frontend/` + `backend/` 结构。

## 目录结构

```text
.
├── frontend/                 # Next.js 前端
├── backend/                  # Python/FastAPI 后端
│   ├── apps/
│   │   └── api/
│   │       ├── core/
│   │       ├── routers/
│   │       ├── middleware/
│   │       └── main.py
│   ├── services/             # 业务引擎（orchestrator/asr/nlp/safety/...）
│   ├── libs/                 # 契约模型、存储适配、LLM 网关
│   ├── data/                 # 题库与量表
│   ├── tests/
│   └── pyproject.toml
├── docs/
└── infra/
```

## 快速开始

### 1) 启动后端

```bash
cd backend
uv sync
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`，API 前缀：`/api/v1`。

### 2) 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端开发服务器会通过 `next.config.mjs` 将 `/api/*` 代理到后端（默认 `http://127.0.0.1:8000`，可通过 `BACKEND_ORIGIN` 覆盖）。
