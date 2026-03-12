# 07 评分引擎（Scoring Engine）

当前代码里存在三种“评分”语义，不能混为一谈。

## 7.1 路径 A：工具接口 turn 评分

入口：

- `POST /api/v1/evaluation/score`
- `POST /api/v1/evaluation/batch_score`

实现：

- `services/evaluation/aggregator.py`

当前行为：

- 使用 `ScoreAggregator()` 默认构造
- 默认 `judge_mode="heuristic"`
- 不是旧文档中的 LLM/mixed judge 模式

默认会创建 3 个 heuristic judges：

- `judge_structure`
- `judge_evidence`
- `judge_adapt`

输出包括：

- `scores`
- `evidence`
- `judge_votes`
- `final_confidence`
- `discounts`

## 7.2 路径 B：在线主流程 turn 评分

当前在线主流程默认不执行这条路径。

实际表现：

- `handle_turn()` 不会调用 `ScoreAggregator.score()`
- `Turn.evaluation` 通常为 `None`
- 事件里仍会写 `evaluation_completed`
- 但 payload 固定为：
  - `{"skipped": true, "reason": "turn_scoring_disabled"}`

这意味着：

- trigger、safety、报告仍然工作
- 但 per-turn 分数、证据、judge votes 在在线会话里通常缺失

## 7.3 路径 C：会话结束评分

实现：

- `services/evaluation/session_scorer.py`

调用时机：

- 显式 `end_session()`
- safety block 自动结束
- 正常回合自动 `END`

不会调用时机：

- prompt injection 导致 invalidation

## 7.4 `SessionScorer` 的真实策略

优先路径：

- 使用 LLM 做“每个维度多次采样”的 dimension ensemble

触发 fallback 的条件：

- session 没有 turns
- 在 pytest 环境下且 `allow_test_mode_llm=False`
- gateway readiness 不是 `ready`
- LLM 调用异常

fallback 行为：

- 返回全 0 分
- `source = llm_zero_fallback`
- 再执行 post guards

## 7.5 Session 级后处理 guards

当前实现的 guard 包括：

- refusal dominant cap
  - 若至少一半 turn 呈现拒答/放弃模式，四维都 cap 到 `0.2`
- keyword stuffing cap
  - 若明显是关键词堆砌，四维 cap 到 `0.8`
- turn alignment cap
  - 只有当 turn 里存在至少 3 个 `evaluation` 时才生效
  - 当前在线主流程通常达不到这个条件

## 7.6 `Report` 的生成后果

`_build_report()` 会生成：

- `overall`
- `timeline`
- `conversation`
- `llm_scoring`
- `notes`

在当前在线行为下，需要注意：

1. `overall`
   来自 `SessionScorer`
2. `timeline`
   如果没有 turn 级评分，会对每个 turn 复用 `overall`
3. `llm_scoring.turns`
   会记录 question / answer，但 `scores` 常为 `None`

## 7.7 置信度计算

### 工具接口评分

`ScoreAggregator` 会：

- 先聚合多个 heuristic judge
- 再用 `global_disagreement * 0.05` 惩罚 confidence

### 会话结束评分

`SessionScorer` 的 confidence 是各维度多次 LLM 调用的平均值。

## 7.8 一个容易误解的实现细节

`routers/evaluation.py` 捕获异常后统一返回：

- `502`
- `message = "LLM upstream error"`

但当前默认 judge stack 实际是 heuristic。

也就是说，这个错误文案更像“历史遗留措辞”，不能据此推断当前 `/evaluation/*` 一定调用了 LLM。
