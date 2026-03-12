# AGENTS.md

本文件面向在本仓库内协作的编码代理。目标不是重复通用规范，而是提供这个项目特有的结构、约束和工作方式。

## 1. 项目概览

- 项目名称：`metacog-interview`
- 形态：前后端分离单仓库，`frontend/` + `backend/`
- 产品目标：实现一个自动化面试 Agent，围绕开放题评估候选人的 `planning / monitoring / evaluation / adaptability`
- 当前实现：MVP 已覆盖会话创建、回合提交、结束报告、事件导出、管理端只读查询、人工标注、健康检查、Prometheus 指标

关键事实：

- 后端是 FastAPI 单体服务，统一 API 前缀为 `/api/v1`
- 前端是 Next.js App Router 应用，浏览器请求通常先到前端，再由 `frontend/app/api/v1/[...path]/route.ts` 代理到后端
- 文档描述的是当前实现，但若文档、代码、测试冲突，以代码和测试为准

## 2. 仓库结构

### 根目录

- `frontend/`: Next.js 16 + React 19 前端
- `backend/`: Python 3.11 + FastAPI 后端
- `docs/`: 以当前代码实现为准的设计文档
- `infra/`: 本地基础设施，当前主要是 PostgreSQL 的 `docker-compose.yml`

### 后端

- `backend/apps/api/routers/`: HTTP 路由层，只做参数校验、鉴权、响应封装
- `backend/apps/api/core/`: 配置、鉴权、依赖注入、统一响应
- `backend/apps/api/middleware/`: 例如 `trace_id` 中间件
- `backend/services/`: 业务逻辑
- `backend/services/orchestrator/`: 主回合编排入口，核心文件是 `service.py`
- `backend/services/asr/`: 语音输入与 ASR
- `backend/services/nlp/`: 文本预处理
- `backend/services/safety/`: 安全检测与提示词注入检测
- `backend/services/trigger/`: 触发器检测，如 `OFFTRACK`、`LOOP`
- `backend/services/scaffold/`: 脚手架提示生成
- `backend/services/evaluation/`: 单回合和会话级评分
- `backend/libs/schemas/`: 对外契约模型单一来源
- `backend/libs/storage/`: PostgreSQL 持久化、文件存储、迁移辅助
- `backend/libs/llm_gateway/`: 大模型供应商适配
- `backend/data/`: 题库、量表、候选人注册表
- `backend/migrations/`: Alembic 迁移
- `backend/tests/`: pytest 测试，包含单元和集成测试

### 前端

- `frontend/app/page.tsx`: 单页入口，内部根据登录态切换 candidate/admin 视图
- `frontend/app/api/auth/*`: 登录/登出 route handlers
- `frontend/app/api/v1/[...path]/route.ts`: 后端 API 代理
- `frontend/components/`: 候选人面试页、管理页、录音控件等 UI
- `frontend/lib/api.ts`: 前端对后端的请求封装
- `frontend/lib/types.ts`: 前端使用的会话/报告类型

## 3. 必须理解的架构约束

### 3.1 PostgreSQL only

- 后端显式拒绝 SQLite，`DATABASE_URL` 必须是 PostgreSQL
- 本地开发前先准备 PostgreSQL，再执行 Alembic 迁移
- 后端不依赖运行时 `create_all()` 自动建表

### 3.2 主流程由 `OrchestratorService` 驱动

- 主流程入口在 `backend/apps/api/routers/sessions.py`
- 关键业务编排在 `backend/services/orchestrator/service.py`
- 单回合处理顺序是：
  1. 读取并锁定 session
  2. 解析文本或 `audio_ref`
  3. ASR
  4. preprocess
  5. safety
  6. trigger detection
  7. policy / scaffold
  8. evaluation
  9. 更新 theta、session 状态、next action
  10. 写入 turn / event / report

如果改会话、回合、状态机或 next action，请优先读这些文件：

- `docs/01_architecture.md`
- `docs/02_state_machine.md`
- `docs/05_turn_pipeline.md`
- `backend/services/orchestrator/service.py`
- `backend/services/orchestrator/state_machine.py`
- `backend/services/orchestrator/policy.py`

### 3.3 契约模型集中在 `backend/libs/schemas`

- 路由层对外请求/响应模型以 `backend/libs/schemas/` 为准
- 服务层允许内部模型，但对外输出前必须映射回 schemas
- 如果修改 API 契约，优先更新：
  1. `backend/libs/schemas/*`
  2. 对应 router / service
  3. `docs/openapi.yaml`
  4. 测试

### 3.4 角色与权限边界

- `candidate`: 只能访问自己的 session
- `admin`: 可查看题库、量表、会话与报告
- `annotator`: 可写标注，可调用 ASR/NLP/Safety/Scaffold/Evaluation 工具接口

相关文件：

- `backend/apps/api/routers/auth.py`
- `backend/apps/api/core/auth.py`
- `backend/apps/api/routers/sessions.py`
- `backend/apps/api/routers/admin.py`
- `backend/apps/api/routers/annotation.py`

### 3.5 前端并不直接暴露后端地址

- 浏览器通常请求前端的 `/api/v1/*`
- 前端 route handler 从 cookie 中取 token，再代理到后端
- 登录接口在 `frontend/app/api/auth/login/route.ts`，会把后端签发的 bearer token 写入 `interview_agent_session` cookie

如果改前端 API 行为，请同时检查：

- `frontend/app/api/v1/[...path]/route.ts`
- `frontend/app/api/auth/login/route.ts`
- `frontend/lib/server-auth.ts`
- `frontend/lib/api.ts`

## 4. 运行方式

### 本地启动 PostgreSQL

在仓库根目录：

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

### 启动后端

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

默认后端地址：`http://127.0.0.1:8000`

### 启动前端

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

默认前端地址：`http://127.0.0.1:8080`

`BACKEND_ORIGIN` 默认指向 `http://127.0.0.1:8000`

## 5. 测试与验证

### 后端

```bash
cd backend
uv run pytest -q
```

注意：

- 后端测试依赖 PostgreSQL
- 默认测试库是 `postgresql+psycopg://postgres:postgres@127.0.0.1:5432/interview_test`
- 测试通过独立 schema 隔离，并在每个测试前清空数据

如果只改了某个服务，优先跑对应测试文件，再决定是否跑全量

### 前端

```bash
cd frontend
pnpm -s lint
```

这里的 `lint` 实际是 `tsc --noEmit` 类型检查，不是 ESLint

## 6. 配置与数据

### 后端环境变量

关键配置在：

- `backend/.env.example`
- `backend/apps/api/core/config.py`

重点变量：

- `DATABASE_URL`
- `AUTH_TOKEN_SECRET`
- `ADMIN_LOGIN_*`
- `ANNOTATOR_LOGIN_*`
- `CANDIDATE_REGISTRY_PATH`
- `SCAFFOLD_POLICY_IDS`
- `ALLOW_REMOTE_AUDIO_FETCH`
- `REMOTE_AUDIO_MAX_BYTES`
- `REMOTE_AUDIO_ALLOWED_HOSTS`
- `LLM_GATEWAY_PROVIDER`
- `DASHSCOPE_API_KEY`
- `LLM_MODEL_NAME`

### 项目数据

- 题库：`backend/data/question_sets/*.json`
- 评分量表：`backend/data/rubrics/*.json`
- 候选人注册表：`backend/data/candidates/dev_candidates.json`

管理端题库/量表接口直接读取这些 JSON 文件。修改数据文件时，通常不需要动数据库迁移，但要确认 admin 接口与前端展示仍然兼容。

## 7. 修改代码时的项目内约定

### 后端

- 保持 router 薄，业务逻辑放在 `services/*`
- 涉及持久化时，优先沿用 `backend/libs/storage/postgres.py` 现有模式
- 涉及回合并发、幂等或状态迁移时，不要绕开 `OrchestratorService`
- 涉及 API 结构时，不要直接在 router 内手拼非标准响应；统一走现有响应封装，确保带 `trace_id`

### 前端

- 现有前端是单页视图切换，不是复杂多路由应用；先理解 `frontend/app/page.tsx` 再改结构
- 调后端优先复用 `frontend/lib/api.ts`
- 认证状态与 token 由前端 route handlers + cookie 维护，不要把 bearer token 散落到客户端组件里

### 文档与测试

- 如果修改了系统行为，优先同步相关测试
- 如果修改了 API、状态机、数据模型或运行约束，补充或修正 `docs/` 下对应文档
- 本仓库文档覆盖面较全，遇到复杂改动先搜索 `docs/` 再动代码

## 8. 常见落点

### 改面试主流程

先看：

- `backend/services/orchestrator/service.py`
- `backend/services/orchestrator/next_action_decider.py`
- `backend/services/orchestrator/selector.py`
- `backend/services/evaluation/*`
- `backend/services/trigger/*`
- `backend/services/safety/*`

### 改会话/报告/管理端展示

先看：

- `backend/apps/api/routers/admin.py`
- `backend/apps/api/routers/sessions.py`
- `frontend/components/admin-dashboard.tsx`
- `frontend/components/admin-review.tsx`
- `frontend/lib/types.ts`

### 改音频输入或 ASR

先看：

- `backend/services/asr/*`
- `backend/apps/api/routers/asr.py`
- `backend/libs/storage/files.py`

## 9. 工作建议

- 搜索优先用 `rg`
- 大改前先确认脏工作区，避免覆盖用户未提交的修改
- 涉及接口变更时，优先检查是否会影响前端代理层和 `frontend/lib/types.ts`
- 涉及数据库变更时，必须补 Alembic 迁移和相关测试
- 不要假设外部 LLM / ASR 一定可用；健康接口允许返回 `degraded` 或 `not_configured`
