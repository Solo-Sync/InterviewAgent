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

## 生产部署

仓库现在包含一套生产用 Docker 部署文件：

- `backend/Dockerfile`: 构建后端生产镜像，容器启动前自动等待 PostgreSQL 并执行 `alembic upgrade head`
- `frontend/Dockerfile`: 执行 `next build`，以 `next start` 运行前端生产包
- `infra/compose.prod.yml`: 编排 PostgreSQL、API、Next.js、Caddy 反向代理和可选备份服务
- `infra/Caddyfile`: 统一 80/443 入口和自动 HTTPS

部署细节、环境变量与备份策略见 [docs/11_deployment.md](./docs/11_deployment.md)。

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
