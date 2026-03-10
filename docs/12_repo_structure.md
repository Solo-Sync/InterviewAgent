# 12 代码仓库结构（Repo Structure）

## 12.1 实际目录

```text
InterviewAgent/
  frontend/
    app/
      api/
        auth/
        v1/[...path]/
    components/
    lib/
  backend/
    apps/api/
      core/
      middleware/
      routers/
    services/
      asr/
      evaluation/
      nlp/
      orchestrator/
      safety/
      scaffold/
      trigger/
    libs/
      schemas/
      storage/
      llm_gateway/
    data/
      question_sets/
      rubrics/
      candidates/
    migrations/
    tests/
  docs/
  infra/
```

## 12.2 关键调用链

- Router -> `OrchestratorService`
- `OrchestratorService` -> preprocess/safety/trigger/scaffold/evaluation/asr
- `OrchestratorService` -> `SqlStore`（session/turn/event/report/annotation）

## 12.3 设计原则

- API 契约模型集中在 `libs/schemas`
- 服务层可有内部模型，但要做 adapter 映射
- 数据库 schema 由 Alembic 管理
