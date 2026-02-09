# 07 评分引擎（Scoring Engine）

评分引擎负责把候选人的回答映射为：
- `DimScores`：plan/monitor/evaluate/adapt
- `EvidenceSpan[]`：每个维度的证据引用 + 理由
- `JudgeVote[]`：多个评委的打分与置信度
- `final_confidence`：聚合后置信度
- `Discount[]`：脚手架/特殊情况折扣

契约接口：
- `/evaluation/score`：单条无状态评分
- `/evaluation/batch_score`：批量回归评分

---

## 7.1 评分量表（0–3）建议（可写入 RubricDetail.scale）

> 契约的 RubricDetail.scale 为自由结构 object；建议统一为如下 JSON（见 09_question_bank_and_rubrics.md）。

### 7.1.1 Planning（规划）

### 7.1.2 Monitoring & Control（监控与调节）

### 7.1.3 Evaluation（评估）

### 7.1.4 Adaptability（应变/迁移）

---

## 7.2 证据优先（EvidenceSpan）

每个维度至少 1 条 evidence：
- `quote`：直接引用候选人原话（或 clean_text 片段）
- `reason`：为什么这段话支持该分数
- `start/end`：可选（字符索引，便于前端高亮）

工程建议：
- 先由 LLM 输出 evidence（带 quote）
- 再做后处理：在 clean_text 中定位 quote（找到 start/end），找不到则置空

---

## 7.3 多评委（JudgeVote）设计

### 7.3.1 评委配置
- `judge_id`：如 `gpt-4o-mini`, `gpt-5.2`, `gemini`, `claude`（示例）
- 每个评委输出：
  - `scores`（0-3）
  - `confidence`（0-1）
  - `evidence`（可并入 vote 或由主输出统一返回）

### 7.3.2 评委输出的强约束（必须结构化）
- 要求 JSON 输出，并用 server-side schema 校验
- 若输出不合规：重试一次（temperature=0）→ 仍失败则丢弃该评委 vote

---

## 7.4 聚合算法（可供参考）

### 7.4.1 基础聚合：加权中位数 / 截尾均值
对每个维度 d：
1. 取所有 vote 的分数集合 `S_d`
2. 若评委数 ≥ 3：用**截尾均值**（去掉最高/最低各 1 个）  
   否则用加权平均
3. 权重 = vote.confidence（或固定权重 × confidence）

### 7.4.2 一致性与 final_confidence
- 计算每个维度的方差/分歧度
- 再结合评委平均置信度，得到 `final_confidence`
- 如果分歧很大：
  - 触发“复核评委”（再调用 1 个模型）
  - 或在报告 notes 中标注“该维度不确定性较高”

### 7.4.3 折扣（Discount）应用
对聚合后的分数 `score_d`：
- 若存在 discounts 中 dimension=d 的 multiplier m：
  - `score_d = score_d * m`
并在最终报告注明折扣原因（脚手架影响）。

---

## 7.5 θ（能力状态）更新（跨回合）

契约未显式暴露 θ，但可内部维护并在 Report.overall 输出。

推荐使用指数滑动平均（EMA）：
- `theta_d(t) = α * theta_d(t-1) + (1-α) * score_d(t)`
- α 建议 0.6–0.8（更看重长期稳定）

并可按“题目阶段”加权：
- 在 S_INIT 初期给较低权重（防止热启动偏差）
- 在后期 probe/扰动回合对 monitor/adapt 加权更高

---

## 7.6 把评分用于决策（闭环）

评分不仅用于报告，还用于选择 next_action：
- monitor/evaluate 高：更适合进入 `PROBE` 扰动
- plan 低：优先 L1/L2 让其先定步骤
- adapt 信号强：立刻追问其新目标与验证路径（PROBE）

