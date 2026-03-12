# 00 目标与范围（Overview）

## 0.1 产品目标

构建一个自动化面试 Agent，用于评估候选人在开放题中的四个元认知维度：

- `plan`
- `monitor`
- `evaluate`
- `adapt`

系统当前以“服务端驱动会话状态 + 前端展示聊天式 UI”的方式运行。

## 0.2 当前已经实现的 MVP

当前代码已经覆盖：

- 候选人登录、管理员登录、后端签名 bearer token
- 会话创建、回合提交、会话结束、报告读取、事件导出
- 文本输入与 `audio_ref` 输入
- ASR、preprocess、敏感词安全检查、提示词注入检测
- trigger 识别与 LLM `next_action` 决策
- 题库与量表管理只读接口
- annotator 标注接口
- 健康检查、结构化日志、Prometheus 指标

## 0.3 当前在线主流程的真实特点

这是本项目最容易被旧文档误导的部分。

1. 主流程里的 `next_action` 目前主要由 `LLMNextActionDecider` 决定。
2. `TriggerDetector` 仍然执行，但结果当前只用于记录日志和给决策上下文，不直接通过 `OrchestratorPolicy` 决定动作。
3. 主流程里的 turn 级评分当前默认关闭。
   现象：
   - `Turn.evaluation` 在正常在线回合里通常为 `None`
   - 事件仍会写 `evaluation_completed`，但 payload 为 `{"skipped": true, "reason": "turn_scoring_disabled"}`
4. `theta` 字段仍存在于 schema 与数据库，但当前在线主流程不会更新它。
5. 题库树的 opening question 会在 `create_session()` 使用，但后续回合并不会调用 `QuestionSelector.select_next()` 推进题树；后续 prompt 主要来自 LLM 决策器。

## 0.4 关键约束

1. 后端只支持 PostgreSQL。
2. schema 生命周期由 Alembic 管理，不依赖运行时 `create_all()`。
3. 回合顺序一致性依赖数据库事务、`SELECT ... FOR UPDATE` 和唯一约束。
4. 所有 API 成功/失败响应都带 `trace_id`。
5. 浏览器通常不直接持有后端地址和 bearer token，而是通过前端 `/api/v1/*` 代理。

## 0.5 重要的“结束”语义

系统当前存在几种不同的结束路径：

- 候选人主动调用 `POST /sessions/{id}/end`
- 正常回合中 LLM 或时间规则决定 `END`
- safety block 触发 `END`
- 第二次 prompt injection 触发 `END` 并将会话标为 `invalid`

其中最后一种要特别注意：

- 会话会结束
- 会写 `session_invalidated`
- 但不会生成最终 report
- 之后再调用 `end_session()` 会因为 invalidated 被拒绝

## 0.6 关键术语

- `Session`：一次完整面试会话
- `Turn`：一次候选人输入及服务端处理快照
- `NextAction`：服务端返回给前端的下一句系统动作
- `QuestionCursor`：当前 prompt 的游标快照，包含 prompt 文本与已问 prompt id 列表
- `ReviewStatus`：管理端用来表达 `in-progress / completed / invalid` 的派生状态
