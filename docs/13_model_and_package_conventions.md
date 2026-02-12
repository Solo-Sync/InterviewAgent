# 13 模型与包结构统一约定（Model & Package Conventions）

目标：避免重复建模、循环依赖和接口漂移。

## 13.1 单一契约来源
- 对外数据结构统一定义在 `libs/schemas/`。
- `apps/api/routes/*` 只使用 `libs/schemas` 作为响应/请求契约参考。

## 13.2 分层职责
- `apps/api/routes/*`：HTTP 参数、鉴权、错误码、响应包装。
- `services/*`：业务逻辑和引擎编排。
- `libs/schemas/*`：契约模型。
- `libs/storage/*`：持久化。

## 13.3 允许内部模型，但必须显式适配
- `services/*` 可以定义内部 dataclass/model。
- 必须通过 `adapter` 转成 `libs/schemas` 契约对象后再返回。

## 13.4 ASR 约定
- ASR 代码统一放在 `services/asr/`。
- 路由层只调用 `ASRService`，不直接耦合底层引擎。
- 替换识别引擎时，不得修改 `AsrResult` 契约字段。

## 13.5 变更流程
1. 若涉及接口字段，先改 `docs/openapi.yaml`。
2. 同步更新 `libs/schemas`。
3. 最后更新 `services/*` 与 `apps/api/routes/*`。
