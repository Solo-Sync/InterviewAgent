# 09 题库与量表规范（Question Bank & Rubrics）

## 9.1 题库文件

默认目录：`backend/data/question_sets/*.json`

`QuestionSelector` 当前读取字段：
- 顶层：`question_set_id`, `questions[]`
- 题目节点：
  - `qid` 或 `question_id`
  - `text`
  - `probes[]`（`id`, `prompt`/`text`, `when`）
  - `perturbations[]`（`id`, `prompt`/`text`, `trigger`）
  - `children[]`（递归同结构）

## 9.2 选择逻辑（当前）

- opening：第一题 `ASK`
- 优先 probe：当 `when` 命中低分维度（阈值 `<1.5`）
- good_flow 时可发 perturbation：
  - 平均分 `>=1.8`
  - `final_confidence >= 0.55`
  - 若有 theta，则平均 `>=1.6`
- 当前节点耗尽后走 child，再走下一个根节点
- 全部耗尽时返回 `END`

## 9.3 rubric 文件

默认目录：`backend/data/rubrics/*.json`

当前代码只强校验文件存在和 JSON 可读；评分逻辑不直接读取 rubric 细目。
建议保持最小字段：
- `rubric_id`
- `title`
- `description`
- `scale`（对象）
