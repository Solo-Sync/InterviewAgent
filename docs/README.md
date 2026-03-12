# 元认知自动化面试 Agent 设计文档

- 仓库基线：`frontend/` + `backend/`
- 当前代码基线时间：2026-03-12
- 后端 API 前缀：`/api/v1`

本目录描述的是当前仓库已经实现的行为，重点服务于“把项目交给下一位开发者继续开发”。

判定优先级：

1. 代码与测试
2. 本目录文档
3. 其他介绍性材料

特别说明：

- 当前系统的主决策链已经与早期文档有明显偏差。
- `OrchestratorService.handle_turn()` 里的真实行为应被视为最高优先级事实来源。
- `docs/openapi.yaml` 是接口快照；接口变更时应同步更新，但阅读代码仍然更可靠。

## 阅读顺序

1. [00_overview.md](00_overview.md)
   当前能力边界、真实在线路径、项目约束。
2. [01_architecture.md](01_architecture.md)
   前后端运行时结构、主依赖、关键入口。
3. [02_state_machine.md](02_state_machine.md)
   `next_action` 来源、状态迁移、时间与异常分支。
4. [03_data_model.md](03_data_model.md)
   领域模型、PostgreSQL 表、事件、报告与 review status。
5. [04_api_contract_mapping.md](04_api_contract_mapping.md)
   路由、权限、响应封装、前端代理关系。
6. [05_turn_pipeline.md](05_turn_pipeline.md)
   单回合完整处理顺序与事务边界。
7. [06_scaffolding_engine.md](06_scaffolding_engine.md)
   当前脚手架能力、接线路径、未接线路径。
8. [07_scoring_engine.md](07_scoring_engine.md)
   在线回合评分、离线工具评分、会话结束评分的真实差异。
9. [08_safety.md](08_safety.md)
   Safety 与 Prompt Injection 两层机制。
10. [09_question_bank_and_rubrics.md](09_question_bank_and_rubrics.md)
    题库 JSON、量表 JSON、当前真实使用方式。
11. [10_observability_event_export.md](10_observability_event_export.md)
    trace、日志、指标、事件导出。
12. [11_deployment.md](11_deployment.md)
    本地启动、环境变量、依赖约束。
13. [12_repo_structure.md](12_repo_structure.md)
    实际目录、关键文件、常见改动入口。
14. [13_model_and_package_conventions.md](13_model_and_package_conventions.md)
    分层约束、模型来源、变更建议。
15. [16_production_readiness_gap.md](16_production_readiness_gap.md)
    当前代码仍然保留的产品化/工程化缺口。
