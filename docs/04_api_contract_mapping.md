# 04 接口契约映射（API Contract Mapping）

本节逐个对齐 `openapi.yaml` 的接口，说明：
- 该接口归属模块
- 典型调用时机（主流程/离线/运维）
- 关键字段与注意点
- 示例请求/响应（精简）

> 所有响应包含 `trace_id`，用于排障与链路追踪。所有接口默认 `BearerAuth (JWT)`。

---

## 4.1 system

### GET /health
- 用途：探活
- 200：`ApiResponseHealth`

---

## 4.2 sessions（主流程）

### POST /sessions — 创建会话
- 模块：Session Orchestrator
- 逻辑：
  1) 校验 question_set_id / rubric_id 是否存在  
  2) 初始化 state = S_INIT  
  3) 产生 next_action（通常是 ASK：抛锚“第一步做什么？”）

**请求示例**
```json
{
  "candidate": { "candidate_id": "stu_001", "display_name": "Alice" },
  "mode": "mvp_text",
  "question_set_id": "qs_fermi_v1",
  "scoring_policy_id": "rubric_v1",
  "scaffold_policy_id": "scaffold_v1",
  "thresholds": { "silence_s": 15, "offtrack_threshold": 0.35, "loop_threshold": 0.82 }
}
```

**响应要点**
- `data.session`：当前 session
- `data.next_action`：下一步动作（客户端直接展示）

---

### GET /sessions/{session_id} — 恢复会话
- 用途：断线重连/恢复
- 返回：当前 session（含 state、阈值、题库引用）

---

### POST /sessions/{session_id}/turns — 提交一回合（核心接口）
- 模块：全链路（ASR/NLP/Safety/Scaffold/Eval/State）
- 输入：`TurnCreateRequest`（text 或 audio_ref）
- 输出：`Turn` + `next_action`

**请求示例（文本）**
```json
{
  "input": { "type": "text", "text": "我先定义人群范围和时间点，然后找手机渗透率..." },
  "client_meta": { "client_timestamp": "2026-02-09T10:01:00Z", "client_platform": "web" }
}
```

**响应要点**
- `data.turn`：完整回合快照（含 preprocess/evaluation/evidence）
- `data.next_action`：系统下一步要做什么
- `data.triggers/scaffold/evaluation`：便于前端调试，可按环境开关隐藏

---

### GET /sessions/{session_id}/turns — 分页获取回合
- 用途：回放、调试、数据分析
- 参数：`limit`（1..200）`cursor`（opaque）

---

### POST /sessions/{session_id}/end — 结束并生成报告
- 输出：`Report`（overall + timeline + notes）
- 触发：
  - 达到最大回合数
  - 候选人/考官主动结束
  - safety 决策 END

---

### GET /sessions/{session_id}/report — 获取最终报告
- 用途：报告页渲染
- 返回：`Report`

---

### GET /sessions/{session_id}/events/export — 导出事件流
- 返回：`text/plain`（JSONL）
- 用途：离线分析/回归集/审计

---

## 4.3 asr / nlp / safety / scaffold / evaluation（可离线调用）

### POST /asr/transcribe
- 用途：离线音频转写（MVP）
- 输出：`AsrResult`（tokens 含时间戳、silence_segments）

### POST /nlp/preprocess
- 用途：填充词抽取→特征流；语义清洗→ clean_text
- 输出：`PreprocessResult`

### POST /safety/check
- 用途：提示词注入/敏感内容检测
- 输出：is_safe + category + action + sanitized_text

### POST /scaffold/generate
- 用途：按指定 level(L1-L3) 生成脚手架提示
- 输入：当前任务/候选人最后回答/错误类型/state
- 输出：ScaffoldResult（prompt + rationale）

### POST /evaluation/score
- 用途：无状态对单条回答评分（调试/离线）
- 输出：EvaluationResult（scores + evidence + votes + confidence + discounts）

### POST /evaluation/batch_score
- 用途：离线回归评分（数据集）
- 输出：EvaluationResult[] + stats（可选）

---

## 4.4 admin（只读配置）

### GET /admin/question_sets
- 返回：QuestionSetSummary[]
- 用途：创建 session 前展示可选题库集

### GET /admin/question_sets/{question_set_id}
- 返回：QuestionSetDetail（questions 为自由结构 object[]）
- 用途：服务端加载题库树（含 probes/perturbations）

### GET /admin/rubrics
- 返回：RubricSummary[]

### GET /admin/rubrics/{rubric_id}
- 返回：RubricDetail（scale 为自由结构 object）
- 用途：评分 prompt 读取 0-3 分描述与示例

---

## 4.5 annotation（人工标注闭环）

### POST /sessions/{session_id}/annotations
- 用途：写入人工评分，用于：
  - 评估 LLM 评分偏差
  - 校准聚合权重/折扣策略
  - 形成离线回归集（gold labels）

**请求示例**
```json
{
  "turn_id": "turn_0003",
  "human_scores": { "plan": 2, "monitor": 1, "evaluate": 1, "adapt": 0 },
  "notes": "规划还可以，但中途没有自检。",
  "evidence": [
    { "dimension": "plan", "quote": "我先定义范围...", "reason": "明确了步骤" }
  ]
}
```

---

## 4.6 错误处理约定

- `ok=false` 时，`error` 字段为 `ApiError`（code/message/detail）
- 常见 code：
  - INVALID_ARGUMENT / NOT_FOUND / UNAUTHORIZED / RATE_LIMITED / INTERNAL
- 对所有错误场景，仍应返回 `trace_id`（便于定位）

