# 16 生产化差距与修复任务单（Production Readiness Gap）

> 审阅日期：2026-02-28
> 审阅范围：`backend/`、`frontend/`、`docs/`、`infra/`
> 目标：把当前仓库从“可演示原型”推进到“可分批生产化改造”的状态。

---

## 16.1 结论摘要

当前项目已经具备以下基础：
- 后端有清晰的分层结构，接口契约和基础测试存在。
- 前后端都能在本地启动，后端测试通过，前端能完成生产构建。
- 评分、ASR、状态机、事件导出等模块已经有初始实现。

但距离“生产级”还有明显差距，主要集中在 5 个方面：
- 安全边界不成立：前端暴露通用令牌，后端没有角色隔离。
- 文件访问存在目录逃逸风险。
- 并发一致性依赖单进程内锁，多实例部署会失效。
- 健康检查与真实依赖状态不一致，容易误报“可用”。
- 前端核心流程仍是 demo/mock，不是真实业务链路。

其中 G1、G3、G6、G7 已完成修复，本文保留问题描述、证据和修复记录，剩余项继续作为待办跟踪。

建议按 `P0 -> P1 -> P2` 分 6 到 8 个小批次修复，每个批次只处理一类问题，必须带测试和验收命令。

---

## 16.2 评分标准

本文件中的优先级定义如下：

- `P0`：上线前必须修，存在安全事故、数据错误、权限失控或多实例错误风险。
- `P1`：尽快修，属于“不能当真实产品使用”的缺口。
- `P2`：生产化基础设施，短期不修不一定立刻出事故，但会严重影响运维、扩展和回滚。

---

## 16.3 问题总览

| 编号 | 优先级 | 问题 | 当前状态 | 影响 |
|---|---|---|---|---|
| G1 | P0 | 浏览器暴露通用 Bearer Token，后端无角色隔离 | 已修复 | 通过服务端 cookie + 签名角色 token 收敛权限边界 |
| G2 | P0 | `audio_id` 存在目录逃逸，可读工作区文件 | 存在 | 本地敏感文件泄露 |
| G3 | P0 | 回合一致性依赖进程内锁，多 worker/多实例不安全 | 已修复 | turn 顺序与幂等收敛到数据库事务，冲突不再直接抛 500 |
| G4 | P0 | `/health` 误报依赖就绪 | 存在 | 运维和前端误判系统可用性 |
| G5 | P1 | 前端主流程仍是 demo/mock | 存在 | 不能作为真实候选人和管理端使用 |
| G6 | P1 | 前端构建忽略 TypeScript 错误 | 已修复 | 前端生产构建恢复 TypeScript 门禁 |
| G7 | P2 | 数据库 schema 生命周期仍依赖 `create_all()` | 已修复 | schema 生命周期改为 Alembic 迁移管理，可初始化、回滚和审计 |
| G8 | P2 | 缺少结构化日志、指标、告警和真实链路观测 | 已修复 | 已补齐结构化日志、Prometheus 指标和 turn 阶段耗时观测 |
| G9 | P2 | 配置默认值过于宽松，生产环境容易误启动 | 存在 | dev 配置泄露到 prod |

---

## 16.4 P0 问题

### G1. 浏览器暴露通用令牌，后端无角色隔离

**修复状态（2026-02-28）**
- 已移除前端 `NEXT_PUBLIC_API_BEARER_TOKEN` 方案，浏览器不再直接持有后台通用 bearer token。
- Web 登录改为 Next.js 服务端登录，并通过 `HttpOnly` cookie + `/api/v1/*` 服务端代理转发鉴权头。
- 后端改为签名 access token，并按 `candidate` / `admin` / `annotator` 做 RBAC。
- `sessions` 路由增加 candidate 归属校验，admin 不能操作 candidate session。
- 权限矩阵和异常 token 的回归测试已补齐。

**现象**
- 前端请求默认读取 `NEXT_PUBLIC_API_BEARER_TOKEN`，并在浏览器侧自动带上 `Authorization`。
- 默认令牌值还是 `dev-token`。
- 后端所有受保护路由都复用同一个 `require_bearer_auth`。
- `sessions`、`admin`、`annotation`、`evaluation` 等接口没有角色边界。

**证据**
- [frontend/lib/api.ts](/home/leo/InterviewAgent/frontend/lib/api.ts#L70)
- [backend/apps/api/core/config.py](/home/leo/InterviewAgent/backend/apps/api/core/config.py#L52)
- [backend/apps/api/core/auth.py](/home/leo/InterviewAgent/backend/apps/api/core/auth.py#L9)
- [backend/apps/api/main.py](/home/leo/InterviewAgent/backend/apps/api/main.py#L61)
- [docs/11_deployment.md](/home/leo/InterviewAgent/docs/11_deployment.md#L60)

**风险**
- 浏览器包、前端环境变量、网络抓包都能暴露这个 token。
- 一旦 token 泄露，攻击者可直接访问管理接口和标注接口。
- 当前“登录”只是前端切换视图，不构成任何后端权限控制。

**根因**
- 鉴权设计仍停留在“单一静态 bearer token”阶段。
- 前端直接调用后端接口，没有服务端 session/JWT/RBAC。
- 文档已经提出角色设计，但实现未落地。

**修复目标**
- 浏览器不再持有后台通用口令。
- 后端基于身份和角色做权限控制，最少区分：
  - `candidate`
  - `admin`
  - `annotator`
- 管理接口、标注接口、候选人接口的访问边界清晰。

**建议方案**
- 第一阶段最小可行修复：
  - 移除 `NEXT_PUBLIC_API_BEARER_TOKEN` 的使用。
  - 改为 Next.js 服务端转发或服务端 session 管理。
  - 后端引入带角色声明的 JWT，或至少实现签名 token + 角色 claim。
- 第二阶段标准化：
  - 统一认证中间件。
  - 按路由声明需要的角色。
  - 审计关键管理操作。

**验收标准**
- 浏览器产物、前端请求头里看不到后台通用 bearer token。
- candidate 身份不能访问 `/admin/*` 和标注接口。
- admin 身份不能冒充 candidate 操作其他人的 session。
- 单元测试覆盖权限矩阵。

**建议测试**
- 未登录访问受保护接口应返回 `401`。
- candidate 访问 admin 路由应返回 `403`。
- annotator 可写 annotation，但不能访问 admin 配置接口。
- token 缺 role、签名错误、过期都应失败。

**给 AI 的任务模板**

```text
只修复认证与权限问题，不处理别的缺陷。

目标：
1. 前端不再通过 NEXT_PUBLIC_API_BEARER_TOKEN 在浏览器侧发送通用 Bearer Token。
2. 后端实现基于角色的鉴权，至少区分 candidate/admin/annotator。
3. admin、annotation、sessions 等路由按角色做权限隔离。

约束：
- 尽量最小改动现有 API 结构。
- 先补失败测试，再实现功能。
- 不要顺手修改 UI 文案或重构无关模块。

完成标准：
- 新增权限相关测试并通过。
- `uv run pytest -q` 通过。
- `pnpm -s build` 通过。
```

---

### G2. `audio_id` 目录逃逸与任意文件读取

**现象**
- `FileStore.path_for()` 直接返回 `self.root / key`。
- `audio_id` 未校验格式，也没有校验规范化后的路径是否仍位于根目录下。
- 业务层会直接读取该路径的字节。

**证据**
- [backend/libs/storage/files.py](/home/leo/InterviewAgent/backend/libs/storage/files.py#L4)
- [backend/services/orchestrator/service.py](/home/leo/InterviewAgent/backend/services/orchestrator/service.py#L358)

**风险**
- 可通过 `../../...` 读取工作目录内敏感文件。
- 在默认仓库结构下，潜在可读取 `.env`、源码、配置文件、测试数据。
- 这类问题属于直接安全漏洞。

**根因**
- 把 `audio_id` 当作“文件路径片段”使用，而不是“受控对象 ID”。
- 缺少路径规范化和根目录约束。

**修复目标**
- `audio_id` 只能映射到安全的受控文件。
- 所有文件读取必须确认路径仍位于存储根目录。
- 拒绝路径分隔符、绝对路径、相对逃逸、软链接逃逸。

**建议方案**
- 将 `audio_id` 收敛为受限格式，例如 `[a-zA-Z0-9._-]+`。
- 在 `path_for()` 中使用 `resolve()` 校验目标路径前缀仍属于 root。
- 如需长期演进，改成“对象 ID -> 元数据表 -> 实际文件路径”的模式。

**验收标准**
- `audio_id` 为 `../../backend/.env` 必须失败。
- `audio_id` 为绝对路径必须失败。
- 合法 ID 仍可正常读取。
- 测试能覆盖目录逃逸和软链接场景。

**建议测试**
- 非法相对路径。
- 绝对路径。
- 包含路径分隔符的 ID。
- 合法 ID 正常读取。

**给 AI 的任务模板**

```text
只修复 audio_id 的路径安全问题。

目标：
1. 阻止 audio_id 通过 ../、绝对路径或其他方式逃逸文件存储根目录。
2. 保留现有对合法 audio_id 的读取能力。
3. 增加回归测试覆盖目录逃逸场景。

约束：
- 不改动 API 契约字段名。
- 不重写整个文件存储模块。
- 先补失败测试，再最小改动实现。

完成标准：
- 新增路径安全测试并通过。
- `uv run pytest -q` 通过。
```

---

### G3. 回合一致性依赖单进程锁，多实例部署不安全

**修复状态（2026-02-28）**
- `handle_turn` / `end_session` 已移除对进程内 `SessionLockPool` 的正确性依赖。
- turn 写入改为数据库事务内分配 `turn_index`，并在唯一约束冲突时执行恢复/重试。
- 并发回归测试已切换到 PostgreSQL，验证路径与生产保持一致。
- 已补“双 service 实例共享同一数据库”的并发回归测试，覆盖相同幂等键和不同请求并发两种场景。

**现象**
- `SessionLockPool` 只在 Python 进程内生效。
- 服务是模块级单例。
- turn 序号由 `count()` 计算。
- 数据库有唯一约束，但业务层没有显式处理冲突和重试。

**修复证据**
- [backend/services/orchestrator/service.py](/home/leo/InterviewAgent/backend/services/orchestrator/service.py#L105)
- [backend/services/orchestrator/service.py](/home/leo/InterviewAgent/backend/services/orchestrator/service.py#L122)
- [backend/libs/storage/postgres.py](/home/leo/InterviewAgent/backend/libs/storage/postgres.py#L92)
- [backend/libs/storage/postgres.py](/home/leo/InterviewAgent/backend/libs/storage/postgres.py#L171)
- [backend/tests/integration/test_turn_idempotency.py](/home/leo/InterviewAgent/backend/tests/integration/test_turn_idempotency.py#L31)

**风险**
- 多 worker/multi-instance 下，同一 session 并发提交可能得到相同 `turn_index`。
- 幂等 key 冲突时可能不是返回历史结果，而是抛数据库异常。
- 如果未来用 Gunicorn/Uvicorn 多 worker，这类问题会非常快暴露。

**根因**
- 把并发控制的核心放在进程内，而不是数据库事务和约束层。
- turn 编号分配不是数据库原子操作。
- 唯一约束冲突没有转成业务可恢复逻辑。

**修复目标**
- 多进程、多实例下仍能保证：
  - turn 顺序正确
  - 幂等 key 生效
  - 冲突不转成随机 500

**建议方案**
- 优先把一致性收敛到数据库：
  - `SELECT ... FOR UPDATE` 锁 session 行。
  - turn index 用事务内可靠分配策略，而不是 `count()`。
  - 捕获唯一约束冲突并执行读取重试。
- 如继续保留进程内锁，只能作为优化，不能作为正确性依赖。

**验收标准**
- 并发提交同一 idempotency key 时，只生成一个 turn。
- 并发提交不同 turn 时，不会出现重复 `turn_index`。
- 多线程测试稳定通过。

**建议测试**
- 同一 session 并发相同请求。
- 同一 session 并发不同请求。
- 唯一约束冲突后应返回业务结果而非 500。

**给 AI 的任务模板**

```text
只修复会话 turn 的并发一致性和幂等问题。

目标：
1. 不再依赖进程内锁保证正确性。
2. turn_index 分配在数据库事务层可靠完成。
3. 唯一约束冲突应转成可恢复逻辑，而不是 500。

约束：
- 不大改 API 契约。
- 尽量保留现有 service/store 分层。
- 先补并发测试，再实现修复。

完成标准：
- 新增并发/幂等回归测试并通过。
- `uv run pytest -q` 通过。
```

---

### G4. `/health` 误报依赖就绪

**现象**
- 健康检查固定返回 `llm_ready=True` 和 `asr_ready=True`。
- LLM 默认 provider 是 `stub`。
- LLM judge 在失败时会静默降级到启发式评分。
- ASR 依赖 `funasr`，但依赖清单没有显式安装它。

**证据**
- [backend/apps/api/routers/health.py](/home/leo/InterviewAgent/backend/apps/api/routers/health.py#L10)
- [backend/libs/llm_gateway/client.py](/home/leo/InterviewAgent/backend/libs/llm_gateway/client.py#L51)
- [backend/services/evaluation/judges/llm.py](/home/leo/InterviewAgent/backend/services/evaluation/judges/llm.py#L44)
- [backend/services/asr/engine.py](/home/leo/InterviewAgent/backend/services/asr/engine.py#L24)
- [backend/pyproject.toml](/home/leo/InterviewAgent/backend/pyproject.toml#L1)

**风险**
- 运维认为服务已就绪，实际 LLM/ASR 根本不可用。
- 前端管理页把系统显示为在线，会误导业务和测试。
- 故障发生时很难判断是“降级中”还是“真的正常”。

**根因**
- `/health` 实现只反映静态值，不反映依赖状态。
- 降级路径过于静默，没有向上暴露 readiness 状态。

**修复目标**
- 健康检查反映真实能力状态，而不是固定绿灯。
- 区分：
  - `ready`
  - `degraded`
  - `not_configured`
  - `unavailable`

**建议方案**
- 为 LLMGateway 增加轻量 readiness 检查。
- 为 ASR 增加依赖加载检查，不做昂贵推理。
- 如果 provider 是 `stub`，应明确标记为未就绪或降级。
- 前端状态展示也要区分“在线但降级”和“完全不可用”。

**验收标准**
- 未配置真实 LLM key 时，health 不能显示 fully ready。
- 未安装 ASR 依赖时，health 明确返回 asr not ready。
- 单元测试覆盖 ready/degraded/not_configured 场景。

**给 AI 的任务模板**

```text
只修复 health/readiness 的真实性问题。

目标：
1. /health 反映真实的 LLM 和 ASR 就绪状态。
2. stub provider 不能再被标记为 ready。
3. ASR 缺依赖时必须明确标记为 not ready 或 degraded。

约束：
- 不做重型健康探测，不触发实际大模型推理。
- 先补测试，再最小改动实现。

完成标准：
- 新增 health 相关测试并通过。
- `uv run pytest -q` 通过。
```

---

## 16.5 P1 问题

### G5. 前端主流程仍是 demo/mock，不是实际业务流

**现象**
- 候选人“录音”结束后，提交的是本地 `scriptedAnswers`。
- 登录页不验证账号密码，只做视图切换。
- 管理端候选人列表来自本地 mock 数据，不是后端返回。

**证据**
- [frontend/components/candidate-interview.tsx](/home/leo/InterviewAgent/frontend/components/candidate-interview.tsx#L22)
- [frontend/components/login-screen.tsx](/home/leo/InterviewAgent/frontend/components/login-screen.tsx#L60)
- [frontend/components/admin-dashboard.tsx](/home/leo/InterviewAgent/frontend/components/admin-dashboard.tsx#L67)
- [frontend/lib/mock-data.ts](/home/leo/InterviewAgent/frontend/lib/mock-data.ts#L3)

**风险**
- 用户路径无法代表真实产品行为。
- 现在的前端看起来像产品，但实际上不能用于真实候选人面试。
- 后端数据模型和前端展示脱节，联调时会暴露大量缺口。

**修复目标**
- 候选人输入来自真实文本输入或真实录音结果，而不是脚本。
- 管理端展示真实后端数据。
- 登录至少接入真实身份来源，或明确切换成开发态假登录模式。

**建议方案**
- 第一阶段：
  - 候选人流先支持真实文本输入。
  - 管理端先接通真实 question set、rubric、session 列表接口。
- 第二阶段：
  - 再接语音录音、上传、转写和回放。

**验收标准**
- 删掉 `scriptedAnswers` 依赖。
- 管理页不再读取 `mock-data.ts` 中的候选人列表。
- 前端主要路径能对接真实 API。

**给 AI 的任务模板**

```text
只处理前端去 demo/mock 化，不改后端核心逻辑。

目标：
1. 候选人回答不再来自 scriptedAnswers，而来自真实用户输入。
2. 管理端不再依赖 mock candidate 数据。
3. 登录流程要么接真实身份，要么明确区分 dev 假登录和真实登录入口。

约束：
- 不顺手重做整套 UI。
- 先保证真实业务链路打通。

完成标准：
- 前端可完成真实 session -> turn -> end 流程。
- `pnpm -s lint` 和 `pnpm -s build` 通过。
```

---

### G6. 前端生产构建忽略 TypeScript 错误

**修复状态（2026-03-01）**
- 已删除 `next.config.mjs` 中的 `ignoreBuildErrors: true`，Next.js 生产构建不再跳过类型校验。
- 已重新执行 `pnpm -s lint` 与 `pnpm -s build`，当前前端可在开启 TypeScript 门禁的前提下通过构建。

**现象**
- `next.config.mjs` 中配置了 `ignoreBuildErrors: true`。
- 当前生产构建日志会跳过类型校验。

**修复证据**
- [frontend/next.config.mjs](/home/leo/InterviewAgent/frontend/next.config.mjs#L1)
- [frontend/package.json](/home/leo/InterviewAgent/frontend/package.json#L5)

**风险**
- 类型不一致会直接进入生产构建产物。
- 当接口契约变化时，前端更容易在运行时才暴露错误。

**修复目标**
- 生产构建必须被类型错误阻断。
- `pnpm -s lint` 和 `pnpm -s build` 的门禁语义恢复正常。

**建议方案**
- 去掉 `ignoreBuildErrors: true`。
- 修掉当前真实存在的 TS 问题。
- 如有必要，单独拆一个“类型债清理”小批次。

**验收标准**
- 生产构建过程中不再显示跳过类型校验。
- 有意引入类型错误时，构建应失败。

**给 AI 的任务模板**

```text
只修复前端构建忽略 TypeScript 错误的问题。

目标：
1. 删除 ignoreBuildErrors 配置。
2. 修复因此暴露出来的真实类型问题。

约束：
- 不重构无关前端模块。
- 以恢复构建门禁为目标。

完成标准：
- `pnpm -s lint` 通过。
- `pnpm -s build` 通过，且不再跳过类型校验。
```

---

## 16.6 P2 问题

### G7. 数据库 schema 生命周期仍是原型模式

**修复状态（2026-03-01）**
- 已初始化 Alembic，并提交首个基线迁移，覆盖当前 `sessions`、`turns`、`events`、`reports`、`annotations` schema。
- `SqlStore` 已移除运行时 `metadata.create_all()`，应用启动不再隐式修改数据库 schema。
- 测试改为先迁移再启动应用，开发、测试与生产的 schema 生命周期模型保持一致。
- 已补迁移回归测试，验证“仅实例化 `SqlStore` 不会建表”以及“`upgrade head` 可完整初始化新库”。

**修复证据**
- [backend/libs/storage/postgres.py](/home/leo/InterviewAgent/backend/libs/storage/postgres.py#L79)
- [backend/libs/storage/migrations.py](/home/leo/InterviewAgent/backend/libs/storage/migrations.py#L1)
- [backend/alembic.ini](/home/leo/InterviewAgent/backend/alembic.ini)
- [backend/migrations/env.py](/home/leo/InterviewAgent/backend/migrations/env.py#L1)
- [backend/migrations/versions/20260228_0001_baseline_schema.py](/home/leo/InterviewAgent/backend/migrations/versions/20260228_0001_baseline_schema.py#L1)
- [backend/tests/unit/test_migrations.py](/home/leo/InterviewAgent/backend/tests/unit/test_migrations.py#L1)

**当前运行方式**
- 新环境初始化数据库：`cd backend && uv run alembic upgrade head`
- 启动应用前先执行迁移，不再依赖应用导入或请求路径自动建表。

**验收结果**
- 新 PostgreSQL schema 可通过迁移命令完整初始化。
- 应用实例化本身不再创建任何业务表。
- 后端回归测试与迁移相关新增测试均已切换为依赖 PostgreSQL 运行。

---

### G8. 缺少结构化日志、指标、告警和真实链路观测

**修复状态（2026-03-01）**
- 已补齐后端 JSON 结构化日志，统一输出 `trace_id`、`event_type`、请求路径、状态码和关键业务字段。
- 请求入口现在会记录请求完成日志，并为失败请求输出带 `trace_id` 的错误日志。
- 已新增 `/api/v1/metrics`，暴露 Prometheus 文本指标。
- `handle_turn` 关键阶段已补 `turn_stage_latency_seconds` 与 `turn_total_latency_seconds` 指标，并在日志中关联 `session_id` / `turn_id`。
- 已补回归测试，覆盖异常日志 trace_id 关联和 metrics 导出。

**现象**
- 中间件只生成 `trace_id`，但没有形成完整日志链路。
- 全局异常处理器不会记录异常日志。
- 代码中几乎没有指标、OTel、结构化日志落地。

**证据**
- [backend/apps/api/middleware/trace.py](/home/leo/InterviewAgent/backend/apps/api/middleware/trace.py#L1)
- [backend/apps/api/main.py](/home/leo/InterviewAgent/backend/apps/api/main.py#L48)
- [backend/libs/observability.py](/home/leo/InterviewAgent/backend/libs/observability.py#L1)
- [backend/apps/api/routers/health.py](/home/leo/InterviewAgent/backend/apps/api/routers/health.py#L54)
- [backend/services/orchestrator/service.py](/home/leo/InterviewAgent/backend/services/orchestrator/service.py#L149)
- [backend/tests/unit/test_observability.py](/home/leo/InterviewAgent/backend/tests/unit/test_observability.py#L1)
- [docs/10_observability_event_export.md](/home/leo/InterviewAgent/docs/10_observability_event_export.md#L10)

**风险**
- 故障时只能看接口报错，无法快速定位到 session/turn 粒度。
- 无法做延迟、错误率、降级率和 judge 超时监控。

**修复目标**
- 至少补齐：
  - 结构化日志
  - 请求级 trace_id
  - session_id/turn_id 关联
  - 基础 metrics

**建议方案**
- 第一阶段：
  - 用标准 logging 输出 JSON 日志。
  - 在关键路径记录 session_id、turn_id、trace_id、event_type、latency。
- 第二阶段：
  - 暴露 Prometheus metrics。
  - 再考虑 OTel tracing。

**验收标准**
- 请求失败时能查到对应 trace_id 的错误日志。
- 每个 turn 的关键阶段耗时可观测。

**验收结果（2026-03-01）**
- 失败请求会输出 `unhandled_exception` 结构化错误日志，并保留同一 `trace_id`。
- `/api/v1/metrics` 可导出请求计数、请求延迟、turn 阶段延迟和 turn 总延迟指标。
- turn 主链路日志已包含 `session_id`、`turn_id`、`stage`、`latency_ms`。

---

### G9. 配置默认值过宽松，生产环境容易误启动

**现象**
- 默认 `DATABASE_URL` 指向本地 PostgreSQL 开发实例，且运行时会拒绝非 PostgreSQL DSN。
- 默认 auth secret 仍是 dev 值，生产环境必须覆盖。
- 默认 LLM provider 是 `stub`。
- 环境加载器会自动尝试读取多个 `.env` 路径。

**证据**
- [backend/apps/api/core/config.py](/home/leo/InterviewAgent/backend/apps/api/core/config.py#L52)
- [backend/libs/env_loader.py](/home/leo/InterviewAgent/backend/libs/env_loader.py#L11)
- [backend/libs/llm_gateway/client.py](/home/leo/InterviewAgent/backend/libs/llm_gateway/client.py#L27)

**风险**
- 生产环境配置不完整时，服务可能仍然“成功启动”，但处于错误降级状态。
- dev 环境配置可能意外污染 staging/prod。

**修复目标**
- 生产模式下关键配置缺失应启动失败。
- dev/staging/prod 的默认值和校验策略分离。

**建议方案**
- 引入 `APP_ENV` 或 `ENVIRONMENT`。
- 对 prod 环境强制校验：
  - `DATABASE_URL`
  - JWT 密钥
  - 真实 LLM provider/key
- 把危险默认值限定在 dev。

**验收标准**
- prod 模式缺失关键配置时应用启动失败。
- dev 模式仍保留快速启动体验。

---

## 16.7 推荐修复顺序

推荐按以下批次执行，不要混做：

1. 批次 1：G1 认证与 RBAC
2. 批次 2：G2 文件路径安全
3. 批次 3：G3 并发一致性与幂等
4. 批次 4：G4 健康检查真实化
5. 批次 5：G5 前端去 demo/mock 化
6. 批次 6：G6 前端构建门禁恢复
7. 批次 7：G7 数据库迁移体系
8. 批次 8：G8/G9 可观测性与配置治理

原因：
- 前 4 个批次决定“能不能安全上线”。
- 中间 2 个批次决定“是不是一个真实产品”。
- 最后 2 个批次决定“能不能稳定运维和持续迭代”。

---

## 16.8 每个批次统一流程

建议固定使用下面的工作流：

1. 明确只修一个问题。
2. 先补失败测试或回归测试。
3. 再做最小实现。
4. 本地跑完整验证。
5. 只在通过后进入下一个批次。

推荐固定验证命令：

```bash
cd /home/leo/InterviewAgent/backend
uv run pytest -q
```

```bash
cd /home/leo/InterviewAgent/frontend
pnpm -s lint
pnpm -s build
```

如果某个批次只改后端，也建议至少再跑一次前端构建，确认契约没被破坏。

---

## 16.9 给 AI 下任务的统一模板

```text
你现在只处理一个问题，不要顺手修别的。

问题：
<填入本次任务标题，例如：修复 audio_id 路径穿越>

目标：
<填入本次任务的 2-4 个明确目标>

约束：
- 先补失败测试，再实现修复。
- 只做最小改动，不重构无关代码。
- 不修改 UI 文案和无关模块，除非完成修复必须涉及。

完成标准：
- 指定测试新增并通过。
- `uv run pytest -q` 通过。
- 如涉及前端，`pnpm -s lint` 和 `pnpm -s build` 通过。

输出要求：
- 先给出你要修改的文件列表和测试计划。
- 再开始实现。
```

---

## 16.10 当前审阅的验证结果

本次审阅时的本地验证结果如下：

- 后端测试：`31 passed`
- 前端类型检查：`pnpm -s lint` 通过
- 前端生产构建：`pnpm -s build` 通过

注意：
- 前端构建现已恢复 TypeScript 门禁；构建日志会执行 `Running TypeScript ...`。
- 这些结果只能说明“当前仓库可运行”，不能说明“当前仓库可安全上线”。

---

## 16.11 最终判断

如果以“真实用户可用、权限可控、数据一致、故障可定位、可多实例部署”为生产级标准，当前仓库更接近：

- 可演示原型
- 可内测工程骨架
- 还不是可正式上线系统

建议先完成全部 `P0`，再决定是否进入真实试点。
