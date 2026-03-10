# 11 部署与扩展（Deployment）

## 11.1 基础部署

当前推荐：
- 1 个 FastAPI 服务
- 1 个 PostgreSQL
- 前端 Next.js 通过 `/api/v1/[...path]` 服务端代理后端

后端启动前必须执行 Alembic 迁移：
- `uv run alembic upgrade head`

## 11.2 PostgreSQL-only

- `Settings` 和 `SqlStore` 都会拒绝非 PostgreSQL URL
- 不依赖 Redis/MQ
- turn 顺序一致性依赖数据库事务 + 唯一约束

## 11.3 鉴权配置

关键环境变量：
- `AUTH_TOKEN_SECRET`
- `ADMIN_LOGIN_EMAIL` / `ADMIN_LOGIN_PASSWORD`
- `ANNOTATOR_LOGIN_EMAIL` / `ANNOTATOR_LOGIN_PASSWORD`
- `CANDIDATE_REGISTRY_PATH`

非 dev 环境会强制拒绝默认密钥与默认密码启动。

## 11.4 音频远程拉取配置

- `ALLOW_REMOTE_AUDIO_FETCH`
- `REMOTE_AUDIO_MAX_BYTES`
- `REMOTE_AUDIO_ALLOWED_HOSTS`

默认关闭远程拉取。

## 11.5 LLM/ASR 可用性

- `/health` 汇总 `LLMGateway` 与 `FunASREngine` readiness
- LLM provider 支持 `stub/openai/openai_compatible/aliyun(dashscope)`
