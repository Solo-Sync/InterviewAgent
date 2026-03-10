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

### 1) 启动 PostgreSQL

项目仅支持 PostgreSQL，不支持 SQLite。本地没有数据库时，可直接使用仓库内 compose：

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

### 2) 启动后端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`，API 前缀：`/api/v1`。

默认数据库连接参考 `backend/.env.example`。

### 3) 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端开发服务器通过 `frontend/app/api/v1/[...path]/route.ts` 将 `/api/v1/*` 代理到后端（默认 `http://127.0.0.1:8000`，可通过 `BACKEND_ORIGIN` 覆盖）。

## Testing

后端全量测试：

```bash
cd backend
uv run pytest -q
```

前端类型检查：

```bash
cd frontend
pnpm -s lint
```

仓库已包含 GitHub Actions 工作流 [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)，会执行后端测试和前端类型检查。

## Interview Simulation

可用脚本通过真实 API 调用后端，并用 LLM 模拟候选人完成多轮面试，导出完整审阅数据：

```bash
cd backend
uv run python scripts/simulate_interviews.py \
  --api-base-url http://127.0.0.1:8000/api/v1 \
  --persona structured \
  --persona adversarial \
  --runs-per-persona 2
```

输出目录默认在 `artifacts/sim_runs/<timestamp>_llm-sim/`，每个 session 会保存：

- `session_create.json`
- `turns.json`
- `report.json`
- `admin_detail.json`
- `events.jsonl`
- `simulator_trace.jsonl`
- `transcript.md`
- `review_template.md`
