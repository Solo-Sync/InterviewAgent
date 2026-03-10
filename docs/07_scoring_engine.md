# 07 评分引擎（Scoring Engine）

## 7.1 两条评分路径

### A. 主流程 turn 评分
- 位置：`OrchestratorService.scoring = ScoreAggregator(judge_mode="turn_aux")`
- 评委：3 个 heuristic judge（规则打分）
- 用途：保证主流程稳定、低依赖

### B. 工具接口评分（/evaluation/*）
- 位置：`routers/evaluation.py` 使用 `ScoreAggregator()` 默认 `judge_mode="llm"`
- 评委来源：
  - `EVAL_JUDGE_MODELS` 多模型时使用多 LLM judge
  - 单模型时：1 LLM + 2 heuristic（混合）

## 7.2 聚合与置信度

`ResultAggregator` 默认配置：
- 维度聚合：`median`
- confidence 聚合：`median`
- 分歧度：`IQR`

最终 `final_confidence`：
- `aggregated_confidence - global_disagreement * 0.05`
- 结果截断到 `[0,1]`

## 7.3 输出结构

`EvaluationResult` 包含：
- `scores`
- `evidence`（每维 1 条）
- `judge_votes`
- `final_confidence`
- `discounts`（可选）

## 7.4 证据提取

- 每个维度从各评委 evidence 中选最长 quote（最多 120 字符）
- 尝试在原文本定位 `start/end`
- 若全弱信号，reason 标注低置信提示

## 7.5 会话结束评分

`POST /sessions/{id}/end` 使用 `SessionScorer`：
- 优先 LLM dimension ensemble（每维多次采样）
- 不可用时 fallback 到 turn 均值
- 含 keyword stuffing / refusal guard 上限策略
