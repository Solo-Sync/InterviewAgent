# metacog-interview

前后端分离单仓库：根目录采用 `frontend/` + `backend/` 结构。

## 目录结构

```text
.
├── frontend/                 # Next.js 16 + React 19 前端
├── backend/                  # Python 3.11 + FastAPI 后端
│   ├── apps/
│   │   └── api/
│   │       ├── core/
│   │       ├── routers/
│   │       ├── middleware/
│   │       └── main.py
│   ├── services/             # orchestrator/asr/nlp/safety/evaluation/...
│   ├── libs/                 # schemas/storage/llm_gateway
│   ├── data/                 # 题库、量表、候选人数据
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
├── docs/
└── infra/
```

## 启动方式概览

当前项目有两套启动方式：

1. 本地开发：PostgreSQL 用 Docker，后端和前端在宿主机进程里运行
2. 生产部署：前端、后端、PostgreSQL、反向代理都通过 `infra/compose.prod.yml` 启动

本地开发是当前默认路径。`infra/docker-compose.yml` 主要用于起 PostgreSQL；不是一套完整的本地全栈编排。

## 本地开发启动

### 前置条件

- Python 3.11
- `uv`
- Node.js 22
- `pnpm`
- Docker 或 Docker Desktop

如果你是在 Windows + WSL2 环境中开发，通常做法是：

- 在 Windows 打开 Docker Desktop
- 在 Docker Desktop 中启用当前 WSL 发行版的 integration
- 在 WSL2 终端里执行下面的命令

### 1. 启动 PostgreSQL

项目只支持 PostgreSQL，不支持 SQLite。

在仓库根目录执行：

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

这会启动一个本地 PostgreSQL 16：

- 地址：`127.0.0.1:5432`
- 数据库：`interview`
- 用户名：`postgres`
- 密码：`postgres`

### 2. 启动后端

在 `backend/` 下准备环境并启动：

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

说明：

- `cp .env.example .env` 不是可选步骤，当前 README 之前漏写了
- `DATABASE_URL` 默认就是本地 PostgreSQL：`postgresql+psycopg://postgres:postgres@127.0.0.1:5432/interview`
- 必须先执行 `alembic upgrade head`，后端不会在运行时自动建表
- 后端地址是 `http://127.0.0.1:8000`
- API 前缀固定为 `/api/v1`

常用校验：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 3. 启动前端

在 `frontend/` 下准备环境并启动：

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

说明：

- 前端开发地址是 `http://127.0.0.1:8080`
- `frontend/.env.example` 默认把 `BACKEND_ORIGIN` 指向 `http://127.0.0.1:8000`
- 浏览器不是直接访问后端，而是先访问前端的 `/api/v1/*`
- 前端 route handler 会把请求代理到后端，并用 `HttpOnly` cookie 保存登录 token

### 4. 本地访问顺序

启动完成后，访问：

- 前端页面：`http://127.0.0.1:8080`
- 后端健康检查：`http://127.0.0.1:8000/api/v1/health`

如果前端页面打开但接口报错，优先检查：

- PostgreSQL 是否真的启动
- 后端是否已经执行过迁移
- `frontend/.env.local` 里的 `BACKEND_ORIGIN` 是否仍然是 `http://127.0.0.1:8000`

### 5. 可选：把后端也放进 Docker 跑

`infra/docker-compose.yml` 里除了 `postgres` 还提供了一个 `api` 服务：

```bash
docker compose -f infra/docker-compose.yml up -d postgres api
```

这个模式会把仓库挂载进容器，用容器里的 `uvicorn` 启动后端。但它仍然不会启动前端，所以前端依然要在 `frontend/` 目录单独执行 `pnpm dev`。

## 生产部署启动

仓库提供了一套完整的生产 Docker 栈：

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `infra/compose.prod.yml`
- `infra/Caddyfile`
- `infra/scripts/backup-loop.sh`

### 1. 准备生产配置

在 `infra/` 目录下，从示例文件复制出真实配置：

```bash
cd infra
cp prod.env.example prod.env
cp env/postgres.prod.example.env env/postgres.prod.env
cp env/backend.prod.example.env env/backend.prod.env
cp env/frontend.prod.example.env env/frontend.prod.env
cp secrets/postgres_password.example secrets/postgres_password
cp secrets/auth_token_secret.example secrets/auth_token_secret
cp secrets/admin_login_password.example secrets/admin_login_password
cp secrets/annotator_login_password.example secrets/annotator_login_password
```

至少要修改这些内容：

- `prod.env` 里的 `SERVER_NAME`
- `secrets/*` 中所有示例密码和密钥
- `env/backend.prod.env` 中的 LLM / ASR / 音频相关配置

### 2. 启动生产栈

回到仓库根目录执行：

```bash
docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  up -d --build
```

可选备份 sidecar：

```bash
docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  --profile ops \
  up -d
```

### 3. 生产栈包含什么

- `postgres`: PostgreSQL 16，只在内部网络暴露
- `api`: FastAPI 容器，启动时自动等待数据库并执行 `alembic upgrade head`
- `frontend`: Next.js 生产服务
- `proxy`: Caddy，对外暴露 `80/443`
- `db-backup`: 可选定时备份

### 4. 生产部署前提

- `SERVER_NAME` 必须是已解析到服务器公网 IP 的域名
- 服务器必须放通 `80/tcp` 和 `443/tcp`
- 不要把真实 secrets 直接写进 `env/*.env`

完整细节见 [docs/11_deployment.md](./docs/11_deployment.md)。

## Testing

后端测试：

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
