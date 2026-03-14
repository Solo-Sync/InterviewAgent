# 12 代码仓库结构（Repo Structure）

## 12.1 目录总览

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
      dialogue/
      evaluation/
      nlp/
      orchestrator/
      safety/
      scaffold/
      trigger/
    libs/
      llm_gateway/
      schemas/
      storage/
    data/
      candidates/
      question_sets/
      rubrics/
    migrations/
    tests/
  docs/
  infra/
```

## 12.2 关键入口文件

### 会话主流程

- `backend/apps/api/routers/sessions.py`
- `backend/services/orchestrator/service.py`
- `backend/services/orchestrator/state_machine.py`
- `backend/services/orchestrator/next_action_decider.py`

### 鉴权

- `backend/apps/api/routers/auth.py`
- `backend/apps/api/core/auth.py`
- `backend/apps/api/core/candidates.py`
- `frontend/app/api/auth/login/route.ts`
- `frontend/app/api/v1/[...path]/route.ts`

### 管理端

- `backend/apps/api/routers/admin.py`
- `frontend/components/admin-dashboard.tsx`
- `frontend/components/admin-review.tsx`

### 候选人端

- `frontend/components/candidate-interview.tsx`
- `frontend/lib/api.ts`

## 12.3 数据与配置文件

- `backend/data/question_sets/*.json`
- `backend/data/rubrics/*.json`
- `backend/.env.example`
- `frontend/.env.example`

## 12.4 相关功能对应的主要入口

### turn 流程

核心入口：

- `backend/services/orchestrator/service.py`

相关模块：

- `backend/services/trigger/*`
- `backend/services/safety/*`
- `backend/services/evaluation/*`

### 会话状态与结束条件

核心入口：

- `backend/services/orchestrator/state_machine.py`
- `backend/services/orchestrator/next_action_decider.py`
- `backend/services/orchestrator/service.py`

### 题库推进逻辑

核心入口：

- `backend/services/orchestrator/selector.py`

需要额外确认：

- 当前在线主流程是否真实调用对应分支

### 前端 API 代理

核心入口：

- `frontend/app/api/v1/[...path]/route.ts`
- `frontend/lib/server-auth.ts`
- `frontend/lib/api.ts`

## 12.5 当前“代码存在但默认不生效”的区域

这些位置最容易造成对在线行为的误判：

- `backend/services/orchestrator/policy.py`
- `backend/services/orchestrator/selector.py` 的 `select_next()`
- `backend/services/evaluation/aggregator.py` 在在线主流程中的使用
- `Session.theta` 在线更新

分析这些文件时，建议先确认调用链是否真的经过它们。
