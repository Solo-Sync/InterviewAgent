# 元认知自动化面试 Agent — 设计文档（以当前代码实现为准）

- 代码基线：`backend/` + `frontend/`
- API 前缀：`/api/v1`
- 更新时间：2026-03-06

本目录描述的是**当前仓库已经实现的行为**。若与文档冲突，以代码和测试为准。

## 文档导航

1. [00_overview.md](00_overview.md) - 目标、范围、当前能力边界
2. [01_architecture.md](01_architecture.md) - 模块与运行时架构
3. [02_state_machine.md](02_state_machine.md) - 状态机与 next_action 决策
4. [03_data_model.md](03_data_model.md) - 领域模型与 PostgreSQL 存储
5. [04_api_contract_mapping.md](04_api_contract_mapping.md) - 已实现接口映射与权限
6. [05_turn_pipeline.md](05_turn_pipeline.md) - 单回合处理流水线
7. [06_scaffolding_engine.md](06_scaffolding_engine.md) - 脚手架策略（当前实现）
8. [07_scoring_engine.md](07_scoring_engine.md) - 评分引擎与聚合逻辑
9. [08_safety.md](08_safety.md) - 安全检测与处置
10. [09_question_bank_and_rubrics.md](09_question_bank_and_rubrics.md) - 题库/量表 JSON 约定
11. [10_observability_event_export.md](10_observability_event_export.md) - 日志、指标、事件导出
12. [11_deployment.md](11_deployment.md) - 部署与配置（PostgreSQL-only）
13. [12_repo_structure.md](12_repo_structure.md) - 实际仓库结构
14. [13_model_and_package_conventions.md](13_model_and_package_conventions.md) - 模型与分层约定
15. [16_production_readiness_gap.md](16_production_readiness_gap.md) - 生产化差距追踪
