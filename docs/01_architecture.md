# 01 总体架构（Architecture）

## 1.1 运行时形态

当前仓库是前后端分离单仓库：

- `frontend/`：Next.js App Router 应用
- `backend/`：FastAPI 单体服务
- `infra/`：本地 PostgreSQL `docker-compose`

浏览器的典型访问路径是：

1. 浏览器请求前端页面
2. 浏览器调用前端 route handler，例如 `/api/auth/login`、`/api/v1/*`
3. 前端服务端读取 `HttpOnly` cookie
4. 前端服务端把 bearer token 代理到后端

因此，前端并不要求浏览器直接知道后端地址。

## 1.2 后端核心模块

- `apps/api/main.py`
  FastAPI 应用入口、异常处理、router 装配。
- `apps/api/middleware/trace.py`
  trace id、请求日志、HTTP 指标。
- `apps/api/core/auth.py`
  HMAC 签名 token、角色鉴权。
- `apps/api/routers/sessions.py`
  候选人会话主入口。
- `services/orchestrator/service.py`
  主事务边界与回合编排入口。
- `libs/storage/postgres.py`
  PostgreSQL 持久化。
- `libs/schemas/*`
  对外 contract 单一来源。
- `libs/llm_gateway/client.py`
  LLM provider 适配层。

## 1.3 `OrchestratorService` 的依赖关系

`OrchestratorService` 在初始化时持有以下依赖：

- `SessionStateMachine`
- `LLMNextActionDecider`
- `QuestionSelector`
- `Preprocessor`
- `SafetyClassifier`
- `PromptInjectionDetector`
- `TriggerDetector`
- `ScaffoldGenerator`
- `DialogueGenerator`
- `SessionScorer`
- `ASRService`
- `FileStore`
- `SqlStore`

这些依赖并不都在在线路径里同等生效。

## 1.4 当前真正在线的控制链

`POST /sessions/{session_id}/turns` 的真实控制链是：

1. 事务内锁定 session
2. 解析文本或音频并执行 ASR
3. 使用 LLM 做 prompt injection 检测
4. preprocess
5. rules-based safety
6. trigger detection
7. 构造完整会话历史
8. 使用 LLM 决定 `next_action`
9. 时间规则/问题轮数规则覆盖 LLM 结果
10. 持久化 turn、session、events
11. 必要时生成 report

## 1.5 已存在但当前未真正接到在线主链的能力

下面这些代码存在，但不能按“已在主流程生效”理解：

- `services/orchestrator/policy.py`
  当前未在 `handle_turn()` 中调用。
- `QuestionSelector.select_next()`
  当前在线回合不使用它推进题目树；`create_session()` 只会从题库根节点里随机抽一题作为 opening。
- `ScoreAggregator`
  当前不用于主流程 turn 评分。
- `theta`
  字段存在，但在线回合不会更新。
- `ScaffoldGenerator`
  当前主要用于工具接口 `/scaffold/generate`；在线主流程只有当 LLM 直接返回 `SCAFFOLD` 时才会在 turn 中记录一个 `ScaffoldResult`，但不会调用 `ScaffoldGenerator.generate()`。

## 1.6 前端当前结构

前端并不是复杂多页系统，而是单页视图切换：

- `app/page.tsx`
  依据登录态切换 login / candidate / admin / review 视图。
- `app/api/auth/login/route.ts`
  调后端 `/api/v1/auth/token`，把 access token 写入 `interview_agent_session` cookie。
- `app/api/v1/[...path]/route.ts`
  将 cookie 中的 token 转成 `Authorization` 请求头再代理给后端。
- `components/candidate-interview.tsx`
  文本面试主界面。
- `components/admin-dashboard.tsx`
  只读会话列表与健康状态面板。
- `components/admin-review.tsx`
  会话详情与只读 transcript。

## 1.7 外部依赖

必需依赖：

- PostgreSQL

可选依赖：

- LLM provider
- FunASR 依赖与模型

当可选依赖缺失时，系统部分功能会降级：

- `/health` 会返回 `degraded / not_configured / unavailable`
- `SessionScorer` 可能回落到零分 fallback
- prompt injection detector / next action decider 如果上游不可用，会在在线 turn 中直接导致 502
