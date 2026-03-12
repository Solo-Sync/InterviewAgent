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

## 11.10 Docker 生产部署栈

仓库提供了一套生产编排：

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `infra/compose.prod.yml`
- `infra/Caddyfile`
- `infra/scripts/backup-loop.sh`

生产拓扑为：

- `postgres`: PostgreSQL 16，仅加入内部网络，不对宿主机暴露端口
- `api`: FastAPI 后端，容器启动时自动等待数据库并执行 `alembic upgrade head`
- `frontend`: Next.js 生产服务，使用 `next build` / `next start`
- `proxy`: Caddy 反向代理，对外暴露 `80/443` 并自动申请 TLS 证书
- `db-backup`: 可选备份 sidecar，按固定周期生成 `pg_dump` 备份

## 11.11 生产部署前准备

在 `infra/` 目录下准备以下文件：

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

必须修改：

- `prod.env` 中的 `SERVER_NAME`
- `secrets/*` 中的所有示例值
- `env/backend.prod.env` 中与 LLM / ASR / 远程音频相关的生产配置

推荐额外修改：

- `env/postgres.prod.env` 中的 `POSTGRES_DB`、`POSTGRES_USER`
- `env/backend.prod.env` 中的 `ACCESS_TOKEN_TTL_SECONDS`
- `prod.env` 中的备份周期与保留天数

## 11.12 生产启动方式

仓库根目录：

```bash
docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  up -d --build
```

启用定时备份 sidecar：

```bash
docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  --profile ops \
  up -d
```

查看服务状态：

```bash
docker compose --env-file infra/prod.env -f infra/compose.prod.yml ps
```

查看日志：

```bash
docker compose --env-file infra/prod.env -f infra/compose.prod.yml logs -f proxy frontend api postgres
```

## 11.13 生产配置约束

### 反向代理与 TLS

- Caddy 使用 `infra/Caddyfile`
- `SERVER_NAME` 必须是已经解析到服务器公网 IP 的域名
- 服务器必须允许入站 `80/tcp` 与 `443/tcp`
- TLS 证书与状态存放在 `caddy_data` 卷中

### Secret 管理

- 数据库密码、JWT 密钥、后台密码通过 Docker secrets 文件注入
- 后端容器入口脚本会优先读取 `*_FILE` 环境变量，再导出为运行时环境变量
- 不要把真实 secret 写进 `env/*.env`

### 数据持久化

命名卷：

- `postgres_data`: PostgreSQL 数据目录
- `postgres_backups`: `pg_dump` 备份文件
- `caddy_data`: TLS 证书与 ACME 状态
- `caddy_config`: Caddy 运行时配置缓存

## 11.14 健康检查与自恢复

`compose.prod.yml` 为以下服务提供了健康检查，并统一配置 `restart: unless-stopped`：

- `postgres`: `pg_isready`
- `api`: `GET http://127.0.0.1:8000/api/v1/health`
- `frontend`: `GET http://127.0.0.1:8080/`

注意：

- 后端健康检查仍然是“应用活着且 HTTP 可响应”的探针
- 它不会单独验证数据库 schema 是否正确，也不会把外部 LLM/ASR 不可用视为容器故障

## 11.15 备份与恢复建议

启用 `db-backup` profile 后，sidecar 会执行：

- 周期性 `pg_dump --format=custom`
- 将备份写入 `postgres_backups` 卷
- 删除超过 `BACKUP_RETENTION_DAYS` 的旧备份

建议同时做两件事：

- 定期把 `postgres_backups` 卷同步到对象存储或另一台机器
- 对恢复流程做演练，而不是只保留备份文件

手动导出一次备份：

```bash
docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  exec -T postgres \
  sh -c 'pg_dump --format=custom -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.dump
```

恢复示例：

```bash
cat backup.dump | docker compose \
  --env-file infra/prod.env \
  -f infra/compose.prod.yml \
  exec -T postgres \
  sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## 11.16 已知边界

- 当前 `proxy` 直接代理到 `frontend`，浏览器流量统一从 Next.js 进入，再由 route handler 访问后端
- 如果后续要把后端 API 直接暴露给第三方客户端，建议再单独补充 API 域名、限流和更细的反向代理规则
- 由于当前环境没有 Docker CLI，本仓库内仅完成了静态配置落地，未在本机执行容器级联调
