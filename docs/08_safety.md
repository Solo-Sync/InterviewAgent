# 08 安全与防注入（Safety）

当前代码里“安全”分成两层，必须分开理解。

## 8.1 第一层：Prompt Injection 检测

实现位置：

- `services/safety/prompt_injection_detector.py`

特点：

- 依赖 LLM
- 在 `handle_turn()` 里先于 preprocess 与 safety 执行
- 目标是识别候选人是否在试图探测/覆盖/操控系统

典型类别：

- `instruction_override`
- `prompt_exfiltration`
- `role_hijack`
- `policy_probe`
- `format_manipulation`
- `other`
- `none`

处置规则：

- 第一次命中：警告并继续
- 第二次命中：结束并标记 invalid

## 8.2 第二层：规则安全分类器

实现位置：

- `services/safety/classifier.py`
- `services/safety/rules.py`

当前非常简单，只检查 `BLOCK_TERMS`：

- `自杀`
- `炸弹`

若命中：

- `category = SENSITIVE`
- `action = BLOCK`
- `is_safe = false`

否则：

- `category = OK`
- `action = ALLOW`
- `is_safe = true`

## 8.3 当前没有生效的安全动作

虽然 schema 里有：

- `SANITIZE`
- `REPHRASE`

但当前 `SafetyClassifier` 实际不会返回这些动作。

唯一会出现 `safety_sanitized` 事件的条件，是未来有人扩展 `SafetyClassifier` 返回 `SANITIZE`；当前默认代码路径基本不会触发。

## 8.4 在线主流程中的顺序

真实顺序是：

1. Prompt Injection 检测
2. preprocess
3. rules-based safety

这意味着：

- prompt injection 不走 `SafetyClassifier`
- `SafetyClassifier` 也不会替代 prompt injection detector

## 8.5 失败模式

这是一个重要的开发注意点。

若 prompt injection detector 的 LLM 调用失败：

- `create_turn()` 会返回 502
- 整个回合不会继续执行

若 `SafetyClassifier` 运行：

- 当前是纯本地规则，不依赖远程服务

## 8.6 对 report 和 review status 的影响

### safety block

- 会结束会话
- 会生成 report
- review status 通常是 `completed`

### prompt injection invalidation

- 会结束会话
- 不会生成 report
- review status 是 `invalid`

这是两类“终止”里最容易被混淆的差异。
