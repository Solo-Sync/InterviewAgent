# 13 模型与包结构约定（Model & Package Conventions）

## 13.1 契约模型单一来源

对外 contract 统一放在：

- `backend/libs/schemas/base.py`
- `backend/libs/schemas/api.py`

路由层的请求体、响应体都应优先复用这些模型。

## 13.2 分层职责

### `apps/api/routers/*`

只做：

- HTTP 参数解析
- 角色校验
- 调 service
- 返回统一 envelope

不应在 router 里写复杂业务状态机。

### `services/*`

负责：

- 业务逻辑
- LLM / ASR / 安全 / 评分等域逻辑
- 主流程编排

### `libs/storage/*`

负责：

- PostgreSQL 表定义
- 事务与 CRUD 封装

### `libs/llm_gateway/*`

负责：

- provider 适配
- 请求格式统一
- readiness

## 13.3 存储层约定

当前系统大量使用“contract snapshot 存 JSON”模式：

- `sessions.last_next_action`
- `turns.turn_payload`
- `reports.report_payload`

优点：

- 容易回放
- schema 演进成本低

代价：

- 查询粒度粗
- 某些派生字段只能在应用层计算

如果要把某个字段做成高频查询条件，再考虑拆成独立列。

## 13.4 事件优先于派生状态

当前很多管理端状态不是存成列，而是由 event 推导。

例如：

- `review_status`
- `prompt_injection_count`
- `invalid_reason`

因此新增流程分支时，优先考虑：

1. 应该追加什么 event
2. 哪些派生逻辑需要同步更新

## 13.5 对外返回前优先映射回 schema

允许 service 内部有辅助 dataclass 或临时 dict，但对外返回前应尽量转回 `libs/schemas`。

已有示例：

- `services/asr/adapter.py`

## 13.6 变更建议顺序

### 改 API 契约

1. 先改 `libs/schemas/*`
2. 再改 router / service
3. 再改 `docs/openapi.yaml`
4. 再改前端类型和请求封装

### 改主流程行为

1. 先改 `OrchestratorService`
2. 同步更新事件、review status、报告影响
3. 再更新文档与测试

### 改前端调用

1. 先确认是否经过 `/api/v1/*` 代理
2. 再改 `frontend/lib/api.ts`
3. 再改组件

## 13.7 当前开发中的一个重要习惯

不要只看类名判断是否“已经上线”。

本仓库存在多处“设计上存在、代码上实现了、但在线链路尚未接通”的模块。修改前务必先从入口函数反查调用链。
