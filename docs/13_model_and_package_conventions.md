# 13 模型与包结构约定（Model & Package Conventions）

## 13.1 契约模型单一来源

- 对外模型统一在 `backend/libs/schemas/`
- 路由层请求/响应以该目录模型为准

## 13.2 分层职责

- `apps/api/routers/*`：HTTP 入口、鉴权、响应封装
- `services/*`：业务逻辑与编排
- `libs/storage/*`：持久化
- `libs/llm_gateway/*`：LLM 供应商适配

## 13.3 adapter 约束

- 允许 `services/*` 内部模型
- 对外返回前必须映射到 `libs/schemas`
- ASR 已通过 `services/asr/adapter.py` 显式映射到 `AsrResult`

## 13.4 变更顺序建议

1. 先更新契约（`libs/schemas` 与 `docs/openapi.yaml`）
2. 再更新 router 和 service
3. 最后补充测试与文档
