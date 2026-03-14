# 16 当前工程化缺口与演进方向（Current Gaps）

本文不记录历史修复过程，而是聚焦当前实现距离更完整产品化状态仍存在的真实缺口。

## 16.1 结论摘要

当前系统已经可以完成：

- 候选人登录
- 文本面试
- 管理端只读查看
- 安全与 prompt injection 处理
- 会话结束报告

但若要继续迭代为更完整的产品，当前最关键的缺口有 6 类。

## 16.2 G1 主流程与文档目标不一致：题库树和 trigger policy 未真正驱动后续提问

现状：

- opening question 来自 `QuestionSelector`
- 后续提问主要来自 `LLMNextActionDecider`
- `OrchestratorPolicy` 未接线
- `QuestionSelector.select_next()` 未接线

影响：

- 题库 JSON 中的 `probes / perturbations / children` 当前不会真实影响在线后续回合
- trigger 只能观测，不能稳定控制策略

优先级参考：

- `P0` 若团队打算继续按“可控题树”路线开发
- `P2` 若团队接受“LLM 主导式面试官”

## 16.3 G2 在线 turn 评分默认关闭，导致 report 中大量字段只是占位

现状：

- 在线回合 `Turn.evaluation` 通常为空
- `timeline` 复用 `overall`
- `llm_scoring.turns[*].scores` 常为空
- `theta` 不更新

影响：

- 管理端看不到细粒度每轮评分
- 题树/脚手架/自适应策略无法依赖 turn 分数闭环

优先级参考：

- `P0`

## 16.4 G3 Prompt Injection 检测对 LLM 上游强依赖，失败会阻断整个 turn

现状：

- prompt injection detector 在回合很靠前的位置执行
- 上游失败时，`create_turn()` 直接 502

影响：

- 只要 LLM 不稳，候选人主流程就会被硬阻断

可行方向：

- 增加降级策略
- 或至少加入本地规则 fallback

优先级参考：

- `P0`

## 16.5 G4 管理端仍是只读视图，annotator 能力没有前端入口

现状：

- 前端只有 candidate/admin 登录流
- annotator 没有独立 UI
- annotation 只能通过 API 调用

影响：

- 人工标注能力虽然后端存在，但无法形成完整运营闭环

优先级参考：

- `P1`

## 16.6 G5 音频链路后端可用，但前端主路径仍是文本面试

现状：

- 后端支持 `audio_ref`
- ASR 工具接口可用
- 候选人前端主界面当前只走文本输入

影响：

- 产品体验与“语音面试 agent”目标仍有距离

优先级参考：

- `P1`

## 16.7 G6 健康检查与 readiness 仍偏开发态

现状：

- `LLMGateway.readiness()` 主要看 provider 和 API key
- `FunASREngine.readiness()` 在未真正加载模型时也可能返回 `ready`

影响：

- `/health` 更像“配置态提示”，不是强生产探针

优先级参考：

- `P2`

## 16.8 可参考的演进顺序

若以补齐核心产品能力为目标，可以按以下顺序推进：

1. 恢复在线 turn 评分与 `theta` 更新
2. 决定是否继续保留“LLM 主导提问”，还是重新接回 `QuestionSelector` / `OrchestratorPolicy`
3. 给 prompt injection detector 增加 fallback
4. 补 annotator 前端
5. 把候选人端接上音频上传

## 16.9 相关文档

- `docs/02_state_machine.md`
- `docs/05_turn_pipeline.md`
- `docs/06_scaffolding_engine.md`
- `docs/07_scoring_engine.md`
- `docs/09_question_bank_and_rubrics.md`
