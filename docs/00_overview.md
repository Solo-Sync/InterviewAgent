# 00 目标与范围（Overview）

## 0.1 产品目标

构建一个自动化面试 Agent，用于评估候选人在开放题中的四个维度：
- planning
- monitoring
- evaluation
- adaptability

系统由服务端状态机驱动，每回合输出 `next_action`，并持久化回合与事件用于回放和审计。

## 0.2 当前实现范围（MVP）

已实现：
- Session 生命周期：创建、回合提交、结束、报告、事件导出
- 文本与 audio_ref 输入（audio_id / data URL / 可选远程 URL）
- 预处理、Safety、Trigger、Scaffold、Evaluation 串联
- 题库与量表管理接口（admin 只读）
- 人工标注接口（annotator 写入）
- 健康检查与 Prometheus 文本指标

暂未实现或仅保留扩展点：
- 自动触发 L3 脚手架（当前策略只会自动触发 L1/L2）
- 基于 `offtrack_threshold` 的连续值判定（字段存在，当前 detector 未使用）

## 0.3 当前实现的关键约束

1. 后端仅支持 PostgreSQL（配置和代码均拒绝 SQLite）
2. 会话回合顺序由数据库事务和唯一约束保证
3. turn 级评分在主流程默认使用 heuristic 多评委（`judge_mode=turn_aux`）
4. `/evaluation/*` 离线接口默认走 LLM/混合评委（由环境变量决定）
5. 所有 API 响应统一返回 `trace_id`

## 0.4 核心术语

- Session：一次面试会话
- Turn：一次完整输入与处理快照
- NextAction：服务端给客户端的下一步动作（ASK/PROBE/SCAFFOLD/END/WAIT）
- Trigger：规则触发器（SILENCE/OFFTRACK/LOOP/HELP_KEYWORD/STRESS_SIGNAL）
- theta：会话级四维能力平滑值（EMA）
