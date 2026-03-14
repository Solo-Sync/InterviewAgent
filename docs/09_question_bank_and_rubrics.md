# 09 题库与量表规范（Question Bank & Rubrics）

## 9.1 题库文件位置

默认目录：

- `backend/data/question_sets/*.json`

当前示例文件：

- `qs_fermi_v1.json`

## 9.2 `QuestionSelector` 能识别的结构

当前 selector 支持以下字段：

### 顶层

- `question_set_id`
- `title`
- `description`
- `questions`

### 题目节点

- `qid` 或 `question_id`
- `text`
- `probes`
- `perturbations`
- `children`

### probe 项

- `id`
- `prompt` 或 `text`
- `when`

`when` 支持的典型值：

- `any_low`
- `plan_low`
- `monitor_low`
- `evaluate_low`
- `adapt_low`

### perturbation 项

- `id`
- `prompt` 或 `text`
- `trigger`

当前只内置识别：

- `good_flow`

## 9.3 `QuestionSelector` 设计能力

如果完整接线，`QuestionSelector.select_next()` 可以：

- opening 时在根题目中随机选一题
- 低分维度时优先发 probe
- `good_flow` 时发 perturbation
- 当前节点用完后走 child
- child 用完后走下一个根节点
- 全部耗尽时返回 `END`

## 9.4 当前在线主流程的真实使用方式

这是本章最重要的现实约束。

当前在线主流程只在两个地方用到 selector：

- `create_session()`
  - 调 `random_opening_selection()` 从根题目里随机抽 opening 题
- `get_opening_prompt()`
  - 用于恢复题面文本；管理端详情页优先展示 session 实际抽到的 opening prompt

在线回合后续并不会调用 `select_next()`。

因此：

- 题库中的 `probes / perturbations / children` 结构目前对在线面试的后续推进不生效
- 它们更像“未来可用能力”和“离线可解释结构”

## 9.5 Opening Prompt 的拼装

opening 文本不是直接把题库原文返回给前端，而是会附加引导句：

`不要着急作答，先说说你打算怎么做。`

所以如果前端或测试依赖 opening prompt 文案，应以服务端拼接后的结果为准。

## 9.6 Rubric 文件位置

默认目录：

- `backend/data/rubrics/*.json`

当前示例：

- `rubric_v1.json`

最小有用字段：

- `rubric_id`
- `title`
- `description`
- `scale`

可选扩展字段：

- `dimensions`

## 9.7 Rubric 在当前代码里的真实作用

当前 rubric 的作用主要有两种：

1. `create_session()` 时校验 `rubric_id` 对应 JSON 文件存在且可读
2. admin 接口展示 rubric 元数据

当前 turn 评分与 session 评分并不会直接读取 rubric 里的细粒度描述来驱动算法。

换句话说：

- rubric 现在是“被引用的资源标识”
- 还不是“真正驱动评分逻辑的配置中心”
