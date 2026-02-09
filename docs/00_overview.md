# 00 目标与范围（Overview）

## 0.1 产品目标

构建一个**自动化面试 Agent**，对大一新生进行“多解性、层级性”的开放问题面试，通过**状态机**驱动对话流程，并针对 4 个元认知维度评分：

- **Planning（规划）**：动手前能否拆步骤、设目标、列假设、确定验证路径  
- **Monitoring & Control（监控与调节，核心）**：执行中能否发现偏离/错误并修正  
- **Evaluation（评估）**：是否主动验证、交叉检查、自证或反证  
- **Adaptability（应变/迁移）**：题目条件改变或发现目标不当时的重构能力

系统支持：
- 题目与扰动由人预先设计（question sets）
- 对每回合回答生成**触发器**（沉默、跑题、死循环、求助、压力信号）
- 必要时按 **L1–L3** 分层脚手架介入（最小支持原则）
- 评分由多个 LLM “评委”打分并提供**证据引用**，再聚合成最终分数与置信度
- 全流程事件溯源（turns + event stream），可导出 JSONL 供分析/训练

## 0.2 MVP 范围（与 OpenAPI 对齐）

契约（`openapi.yaml`）已包含：

- Session 生命周期：创建 / 获取 / 提交 turn / 结束 / 报告 / 导出事件
- 模块化工具接口：ASR、预处理、安全检查、脚手架生成、评分（单条/批量）
- 管理只读接口：题库集、量表（rubrics）
- 人工标注接口：对 turn 提交 human_scores 作为校准数据

### MVP 强约束
1. **面试流程由服务端状态机统一控制**（客户端只负责展示下一步动作）
2. **评分必须“证据优先”**：每个维度给分必须引用被试回答片段（EvidenceSpan）
3. **脚手架影响要记录**：触发了 L1–L3，需要对部分维度应用折扣（Discount）

## 0.3 核心工程决策

### 0.3.1 “状态机 + 事件溯源”优先
- 状态机保证流程一致性与可解释性
- 事件溯源保证：可回放、可审计、可做离线回归评分与提示策略评估

### 0.3.2 模块边界清晰
- `/sessions/**`：**有状态**（orchestrator）
- `/evaluation/**` `/scaffold/**` `/safety/**` `/nlp/**` `/asr/**`：**尽量无状态**（便于离线调参、批处理、替换实现）

### 0.3.3 评分的可靠性策略
- 多评委投票（JudgeVote）+ 置信度（final_confidence）
- 剔除异常评委（离群）+ 量表约束 + 引用证据约束
- 引入人工标注闭环（/annotations）

## 0.4 术语表（与契约字段一致）
- **Session**：一次面试会话（SessionState）
- **Turn**：一次“系统提问/动作 → 候选人回答 → 系统处理”的完整回合
- **NextAction**：服务端给客户端的下一步指令（ASK/PROBE/SCAFFOLD/CALM/END/WAIT）
- **Trigger**：回合内触发器（SILENCE/OFFTRACK/LOOP/HELP_KEYWORD/STRESS_SIGNAL）
- **θ（能力状态）**：plan/monitor/evaluate/adapt 的全局估计（内部维护，可映射到 Report.overall）
