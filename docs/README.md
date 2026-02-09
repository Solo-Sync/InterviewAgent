# 元认知自动化面试 Agent — 工程级设计文档（基于 OpenAPI 契约）

- 契约来源：`openapi.yaml`（Metacognitive Interview API v0.1.0）
- 目标人群：大一新生（非 CS 题也可）
- 文档日期：2026-02-09

本设计文档**严格对齐**接口契约（OpenAPI 3.0.3），并在契约允许的 `additionalProperties` 扩展点上补全工程实现细节：状态机、事件流、脚手架策略、LLM 多评委评分、证据引用、折扣机制、安全防注入、可观测性与部署。

## 快速导航

1. [00_overview.md](00_overview.md) — 目标/范围、核心概念、MVP→扩展路线
2. [01_architecture.md](01_architecture.md) — 总体架构、模块职责、数据流
3. [02_state_machine.md](02_state_machine.md) — 状态机、触发器、跳转逻辑（含“重定义目标”异常）
4. [03_data_model.md](03_data_model.md) — 数据模型、存储表/索引、事件溯源
5. [04_api_contract_mapping.md](04_api_contract_mapping.md) — 逐接口映射到模块/流程（含示例请求/响应）
6. [05_turn_pipeline.md](05_turn_pipeline.md) — 单回合处理流水线（ASR→清洗→安全→触发→脚手架→评分→决策）
7. [06_scaffolding_engine.md](06_scaffolding_engine.md) — L1–L3 生成、触发策略、折扣与日志
8. [07_scoring_engine.md](07_scoring_engine.md) — 量表、证据、LLM 多评委集成、聚合与置信度
9. [08_safety.md](08_safety.md) — 防提示词注入/敏感内容/越权指令、Sanitize 策略
10. [09_question_bank_and_rubrics.md](09_question_bank_and_rubrics.md) — 题库树/扰动设计、rubric JSON 规范
11. [10_observability_event_export.md](10_observability_event_export.md) — trace_id、指标、事件导出（JSONL）
12. [11_deployment.md](11_deployment.md) — 部署拓扑、缓存、队列、成本与扩容
13. [12_testing.md](12_testing.md) — 回归集、离线批评分、人工标注闭环
14. [13_privacy_and_compliance.md](13_privacy_and_compliance.md) — 隐私、保留策略、审计与权限

15. [14_repo_structure.md](14_repo_structure.md) — 后端仓库结构与三人分工
16. [15_policies.md](15_policies.md) — scoring/scaffold 策略配置

## 附录

- `diagrams/`：Mermaid 图（状态机、时序、数据流）
- `prompts/`：核心提示词模板（评分 / 脚手架 / 安全）

> 说明：本文档以“工程落地”为目标，默认后端实现为 FastAPI（契约已体现），存储与队列选型给出可替换方案。
