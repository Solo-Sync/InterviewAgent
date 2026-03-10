# 08 安全与防注入（Safety）

实现位置：`services/safety/classifier.py`

## 8.1 当前规则

- BLOCK（`category=SENSITIVE`）
  - 命中词：`自杀`、`炸弹`
- SANITIZE（`category=PROMPT_INJECTION`）
  - 命中词：`忽略之前`、`ignore previous`、`system prompt` 等
- ALLOW（`category=OK`）
  - 其余文本

说明：`REPHRASE` 枚举存在，但当前分类器不会返回该动作。

## 8.2 sanitize 行为

- 删除注入关键词（大小写不敏感）
- 合并空白
- 输出 `sanitized_text`

## 8.3 与主流程联动

- safety BLOCK：直接结束会话（next_action=END）
- safety SANITIZE：继续 trigger/scaffold/evaluation
- 事件：`safety_blocked` 或 `safety_sanitized`
