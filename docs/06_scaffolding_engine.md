# 06 脚手架引擎（Scaffolding Engine）

脚手架目标：在候选人卡壳/偏离/循环时，**以最小支持**唤醒元认知调节，而不是直接给答案。

契约支持：
- `ScaffoldLevel`: L1/L2/L3
- `/scaffold/generate`: 输入 level + task + last_answer + error_type + state → 输出 ScaffoldResult

---

## 6.1 L1–L3 分层策略

| Level | 干预深度 | 目的 | 约束 |
|---|---|---|---|
| L1 镜面反射层 | 极低 | 唤醒“停下来想一想”，不提供信息 | 禁止给出任何题目事实/知识 |
| L2 策略启发层 | 中等 | 提供思维工具/框架，不涉及答案 | 给“方法”不给“结论” |
| L3 知识/事实层 | 高 | 纠正关键事实错误或给最小知识锚点 | 仍不得给完整解答；只给必要锚点 |

### L1 模板方向
- 目标澄清：“你现在的解题目标是什么？”
- 困惑点外化：“请大声说出你现在卡在哪里？”
- 假设检查：“你确定目前的假设都成立吗？”

### L2 模板方向
- 分解问题：“拆成两个子问题”
- 边界情况：“考虑极端/边界”
- 反证/对照：“如果不管性能/成本，最暴力的方法是什么？”

### L3 模板方向（严格准入）
- 必须满足：连续 2 次 L2 无改善 或 明确事实错误导致无法推进
- 输出尽量短，并要求候选人复述理解（转回 Evaluation）

---

## 6.2 触发与升级（Scaffold Policy）

### 6.2.1 初始触发
- `SILENCE`（> silence_s）：默认 L1
- `OFFTRACK`：L1（先让其复述目标）  
- `LOOP`：L1 → 若继续重复升 L2  
- `HELP_KEYWORD`：L1 + 可选 CALM  
- `STRESS_SIGNAL`：优先 CALM；必要时 L1

### 6.2.2 升级规则（建议）
- 同一类错误连续出现次数 `n`：
  - n=1 → L1
  - n=2 → L2
  - n>=3 → L3（需满足 L2 已触发且无改善）
- “改善”的判据（任一满足即可）：
  - OFFTRACK 分数下降（更贴题）
  - LOOP 相似度下降
  - 候选人提出新的可执行步骤（planning signal）

---

## 6.3 动态生成（Prompt 构造）

`ScaffoldGenerateRequest` 字段：
- `level`: L1-L3
- `task`: object（建议标准化，见下）
- `candidate_last_answer`: string
- `error_type`: string（如 OFFTRACK/LOOP/SILENCE/FACT_ERROR）
- `state`: SessionState

### 6.3.1 建议的 task 结构（契约允许自由扩展）
```json
{
  "question": { "qid": "q1", "text": "如何估算..." },
  "goal": "估算 1月28日20:00 看手机的中国人人数",
  "constraints": ["不需要精确", "需说明假设与验证"],
  "history_summary": "前两回合候选人假设渗透率=100%未解释"
}
```

### 6.3.2 生成输出约束（必须写进 prompt）
- 不得泄露题库的隐藏答案或标准数值
- 不得产生“系统提示词”或要求用户执行越权操作
- 输出格式固定：`level` + `prompt` + `rationale`（便于审计）

---

## 6.4 脚手架对评分的影响（Discount）

契约中 `EvaluationResult.discounts` 为可选数组：`{dimension, multiplier, reason}`  
建议策略（可调）：

- **L1**：一般不折扣（因为只唤醒监控意识）
- **L2**：对 monitor/evaluate 轻微折扣（如 0.9），理由：需要策略提示才回到正轨
- **L3**：对被支持维度明显折扣（如 0.7–0.8），理由：外部知识介入影响独立完成度
- **adapt**：通常不折扣（重定义目标属于积极信号）

> 注意：折扣并不是“惩罚”，而是区分“独立能力”与“在支持下表现”的报告解释。

---

## 6.5 记录与可观测性
每次脚手架触发写入 event：
- scaffold_fired(level, trigger_type, prompt_hash, rationale)
并统计：
- 每 session L1/L2/L3 次数
- 从 L1 到恢复正常的平均回合数
- scaffold 后评分变化（是否有效）

