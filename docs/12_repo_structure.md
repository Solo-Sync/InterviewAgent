# 14 代码仓库结构建议（Repo Structure）— Postgres-only 版本

## 14.1 单仓（推荐）
```
metacog-interview/
  frontend/                 # Next.js 前端
  backend/
    apps/
      api/                  # FastAPI 服务（对外 OpenAPI）
        main.py
        routers/            # sessions/asr/nlp/safety/scaffold/evaluation/admin/annotation
        middleware/         # auth, trace_id, logging
    services/
    orchestrator/           # 状态机与会话推进
      state_machine.py
      policy.py
      selector.py           # 选择下一题/扰动
    trigger/
      detector.py
      features.py
    nlp/
      preprocess.py
    safety/
      rules.py
      classifier.py
    scaffold/
      generator.py
      templates/
    evaluation/
      judges/               # 多评委适配
      aggregator.py
      prompts/
    libs/
    schemas/                # Pydantic models（与 OpenAPI 对齐）
    storage/
      postgres.py           # Postgres DAO（sessions/turns/events/annotations）
      migrations/           # Alembic 迁移（可选）
      files.py              # 本地文件/对象存储适配（可选）
    llm_gateway/            # 统一 LLM 调用、限流、重试、（可选）进程内缓存
    data/
    question_sets/          # JSON 题库
    rubrics/                # JSON 量表
    tests/
      unit/
      integration/
  docs/                     # 本设计文档（你现在看到的这些 md）
  infra/
    docker-compose.yml      # 仅 api + postgres（最小可跑）
```

## 14.2 关键接口（建议）
- `Orchestrator.handle_turn(session_id, TurnCreateRequest) -> (Turn, NextAction)`
- `TriggerDetector.detect(context) -> List[Trigger]`
- `ScaffoldPolicy.choose_level(triggers, history) -> ScaffoldLevel`
- `ScaffoldGenerator.generate(req) -> ScaffoldResult`
- `ScoringEngine.score(req) -> EvaluationResult`
- `Aggregator.aggregate(votes) -> (DimScores, confidence)`
- `EventWriter.append(event)`

## 14.3 ASR 模块落位与边界（统一约定）
- ASR 能力放在 `services/asr/`，不要在仓库根目录新增独立包。
- `backend/apps/api/routers/asr.py` 只负责 HTTP/错误码/响应封装，不承载业务逻辑。
- `services/asr/` 可定义内部领域模型，但对外返回必须映射到 `libs/schemas/base.py` 的 `AsrResult`。
- 若替换底层引擎（FunASR/Whisper），只改 `services/asr`，不改 API 契约层。
