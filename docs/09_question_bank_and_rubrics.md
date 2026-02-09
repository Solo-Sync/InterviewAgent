# 09 题库与量表规范（Question Bank & Rubrics）

契约中：
- `QuestionSetDetail.questions` 的 items 为 `object` 且 `additionalProperties=true`  
- `RubricDetail.scale` 为 `object` 且自由结构  

因此你可以在不改动契约的前提下，制定**统一的 JSON 约定**，让题库与评分 prompt 可复用。

---

## 9.1 QuestionSet（题库集）推荐 JSON 结构

`questions[]` 建议每个元素为一个“题目节点”（支持树）：

```json
{
  "qid": "fermi_phone_001",
  "title": "估算：1月28日20:00看手机的中国人人数",
  "text": "如何估算 1 月 28 日 20:00 正在看手机的中国人人数？请说明假设与验证方式。",
  "type": "fermi",
  "difficulty": 2,
  "tags": ["estimation", "assumption", "verification"],
  "anchors": {
    "must_have": ["定义总体范围", "拆分因子", "估算/数据来源", "不确定性说明"],
    "red_flags": ["直接报一个数", "无假设", "无法解释来源"]
  },
  "probes": [
    {
      "id": "probe_goal",
      "when": "plan_low",
      "prompt": "请先不要给最终答案，说说你第一步准备做什么？"
    },
    {
      "id": "probe_verify",
      "when": "evaluate_low",
      "prompt": "你怎么验证你的数量级是合理的？"
    }
  ],
  "perturbations": [
    {
      "id": "pert_missing_data",
      "trigger": "good_flow",
      "prompt": "假设你拿不到任何统计数据，只能用常识估算，你会怎么做？",
      "expected_dimension": "monitor"
    },
    {
      "id": "pert_change_scope",
      "trigger": "good_flow",
      "prompt": "把范围改成“正在刷短视频”的人数，你的拆分会变吗？",
      "expected_dimension": "adapt"
    }
  ],
  "children": [
    { "qid": "fermi_phone_001_sub1", "text": "你打算把哪些因素相乘？为什么？" }
  ]
}
```

### 9.1.1 选择下一题/下一扰动
- 默认：沿着 children 深入（层级性）
- 若 monitor/evaluate 高：优先 perturbations（扰动）
- 若 plan 低：优先 probes（抛锚/策略提示）

---

## 9.2 Rubric（量表）推荐 JSON 结构

`RubricDetail.scale` 建议为：

```json
{
  "range": [0, 3],
  "dimensions": {
    "plan": {
      "0": {"desc": "无步骤/无假设", "examples": ["直接报数字"]},
      "1": {"desc": "粗略步骤", "examples": ["先大概估一下"]},
      "2": {"desc": "步骤清晰+主要假设", "examples": ["先定义范围再拆因子"]},
      "3": {"desc": "分层计划+验证路径", "examples": ["先粗估再 refine 并交叉验证"]}
    },
    "monitor": { "...": "..." },
    "evaluate": { "...": "..." },
    "adapt": { "...": "..." }
  },
  "evidence_rule": "每维至少 1 条引用原话",
  "notes": [
    "L3 脚手架触发时，对相关维度应用折扣",
    "goal reset 属于 adapt 的积极信号"
  ]
}
```

---

## 9.3 题库/量表的版本化与灰度

- `question_set_id` 与 `rubric_id` 建议语义化版本：
  - `qs_fermi_v1`, `qs_policy_v2`
  - `rubric_v1`, `rubric_v1.1`
- 服务端在 session 创建时把版本写死到 session（保证可复现）
- 做 A/B 时：
  - 随机分配 question_set_id / rubric_id / scoring_policy_id
  - 事件流里记录分组信息（便于离线分析）

