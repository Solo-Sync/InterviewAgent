# 11 部署与扩展（Deployment & Scaling）— Postgres-only 版本

> 目标：**低运维、低复杂度**。不引入 Redis / MQ，仅使用 PostgreSQL 作为唯一外部依赖（对象存储/本地磁盘可选）。

---

## 11.1 推荐运行形态

### 11.1.1 单体（MVP & 推荐）
- 1 个 FastAPI 服务
- 1 个 PostgreSQL
- 内部模块化（asr/nlp/safety/scaffold/eval/orchestrator）
- 优点：最省心、部署简单、调试最容易
- 代价：吞吐有限；但你明确“性能要求不高”，可接受

### 11.1.2 “轻异步”而不引入队列（可选）
不使用 Redis/MQ 的前提下，如果某些任务明显更慢（如 report 生成、batch_score），建议：
- API 热路径仍同步返回 next_action
- 慢任务使用 FastAPI `BackgroundTasks` 或独立的 `asyncio` 任务执行
- 结果写回 Postgres（report 表 / export 表），前端通过轮询 `/sessions/{id}/report` 获取

> 这不是“强一致的分布式队列”，但对低并发场景足够；进程重启会中断后台任务——若未来需要可靠异步，再引入队列/MQ。

---

## 11.2 存储（Postgres 作为唯一状态源）

- Postgres：`sessions/turns/events/annotations`
- 音频与导出文件：
  - 低规模：本地磁盘 + 文件路径入库（最简单）
  - 想更稳：对象存储（S3/OSS）+ URL 入库（仍不改变契约）

### 11.2.1 不用 Redis 时的状态管理要点
- `sessions.state/theta/cursor/thresholds` **必须持久化**：每回合由 orchestrator 读写（同一事务）。
- 并发控制（推荐）：
  - `SELECT ... FOR UPDATE` 锁住 session 行
  - turn/events 同事务提交
- 连接池：
  - Python 端用 asyncpg / psycopg3 + pool
  - 或加 pgbouncer（可选）

---

## 11.3 LLM Gateway（成本与稳定性）

### 11.3.1 并发与限流
- 按 judge_id 设置并发上限
- 为每回合设总超时（例如 3s），超时就降级（减少对交互的破坏）

### 11.3.2（可选）无 Redis 的缓存策略
你说性能不敏感 → **默认不做缓存**也 OK。若想节省 LLM 成本：
- 进程内 LRU/TTL（例如 5–30 分钟）：
  - key：`hash(question_id, rubric_id, clean_text, context_digest)`
  - 优点：实现最简单
  - 缺点：多实例不共享、重启丢失
- 如果未来需要跨实例共享缓存：再考虑“DB 表缓存”或引入 Redis（不在本版本范围内）

---

## 11.4 安全与权限
- 签名 access token + 角色声明（`candidate` / `admin` / `annotator`）
- 浏览器端不要持有后台通用 bearer token；Web 前端通过 Next.js 服务端登录和 `HttpOnly` cookie 转发到后端
- candidate 身份来源建议使用预置候选人表或邀请凭证；当前实现为 `CANDIDATE_REGISTRY_PATH` 中的 `email + invite_token` 校验
- 角色建议：
  - `candidate_client`：仅 sessions/turns/report
  - `admin`：admin/question_sets, admin/rubrics
  - `annotator`：annotations 写入
- 服务端强制鉴权与审计日志（尤其是 admin/annotation）

---

## 11.5 配置管理
- 题库/量表：可先用本地 JSON 文件（只读），后续迁移到 DB 或配置中心
- 阈值 thresholds：可在 session 创建时写入（便于 A/B）
- 建议引入 `APP_ENV` 区分 dev 与非 dev；非 dev 环境下默认密钥和默认管理密码应禁止启动
- 数据库 schema 变更统一走 Alembic；部署和启动前执行 `cd backend && uv run alembic upgrade head`

---

## 11.6 扩展路线（与契约兼容）
- 流式 ASR：客户端边录边传，服务端持续更新 SILENCE trigger
- “面试官语音合成”：next_action.text 交给 TTS（不需要改契约）
- 更丰富的 audio_features：不改 schema（AudioFeatures additionalProperties=true）
