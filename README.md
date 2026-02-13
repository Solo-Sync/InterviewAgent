# 元认知面试系统

本项目基于 LangGraph 状态机与大模型，实现一个元认知能力面试系统，支持 **无 ASR 时的命令行交互测试**，也预留了与 **语音 ASR 系统集成** 的接口。

---

## 快速开始（无 ASR，本地键盘面试）

1. **创建并激活虚拟环境，安装依赖**

   参考 `env_setup.md`：

   ```bash
   uv venv
   .venv\Scripts\activate  # Windows
   uv pip install -e .
   ```

2. **配置千问 API 密钥**

   在项目根目录创建或编辑 `.env`：

   ```env
   DASHSCOPE_API_KEY=your_actual_api_key_here
   ```

3. **运行交互式命令行面试**

   ```bash
   python example_usage.py
   ```

   在终端中你可以：

   - 直接 **键盘输入回答**（中文/英文均可）
   - 输入 `exit` / `quit` / `q` 结束面试
   - 实时看到：
     - 当前 **状态机状态**（S_INIT / S_WAIT / S_PROBE / S_SCAFFOLD / S_EVAL_RT / S_END）
     - 当前轮次 `turn_index`
     - 每轮的 **评估分数**（plan / monitor / evaluate / adapt）
     - 各模块对 LLM 的调用详情（prompt 与 LLM 的原始回复）

   这些信息由以下文件负责输出：

   - `example_usage.py`：打印状态机状态、下一步动作、评估分数
   - `src/question_module.py`：打印追问 / 认知压力问题时的 LLM prompt 与完整回复
   - `src/scaffold.py`：打印各级脚手架提示（L1/L2/L3）的 LLM prompt 与完整回复
   - `src/evaluation.py`：打印实时评估（打分 JSON）的 LLM prompt 与完整回复

---

## 接入 ASR 的思路与步骤

当前代码已经通过 `InterviewStateMachine.process_turn` 和一个简单的 ASR 开关预留了集成接口。

在 `src/state_machine.py` 顶部有一个全局开关:

```python
USE_MOCK_ASR = True
```

- **开发/本地调试阶段**: 保持 `True`，状态机会通过 `input()` 让你在命令行里手动输入回答，相当于“模拟 ASR”。
- **上线接入真实 ASR 时**: 把它改成 `False`，状态机会调用真实接口 `/api/v1/asr/transcribe` 获取学生回答文本和沉默时长。

> **上线时只需要把 `USE_MOCK_ASR = True` 改成 `False` 即可走真实 ASR 接口。**

内部封装了一个统一的获取输入方法(见 `src/state_machine.py`):

```python
def get_asr_input(self) -> tuple[str, float]:
    """
    - USE_MOCK_ASR = True  -> 命令行 input() 模拟 ASR
    - USE_MOCK_ASR = False -> 调用 /api/v1/asr/transcribe
    返回 (student_input, silence_duration)
    """
```

你可以在自己的循环里调用 `get_asr_input()` 拿到 `student_input` 和 `silence_duration`，再传给 `process_turn`。

一个典型的 ASR 集成伪代码如下（简化版）：

```python
from src.state_machine import InterviewStateMachine

state_machine = InterviewStateMachine(llm=llm, question_bank_path="question_bank.json")
session_id = "asr_session_1"

while True:
    # 1. 获取一轮 ASR 输入 (根据 USE_MOCK_ASR 走模拟或真实接口)
    student_text, silence = state_machine.get_asr_input()

    # 2. 调用状态机，获取当前要说的话（欢迎语 / 问题 / 提示）
    result = state_machine.process_turn(
        session_id=session_id,
        student_input=student_text,
        silence_duration=silence
    )

    # 3. 把 result["output_text"] 交给 TTS 播放或前端显示
    output_text = result.get("output_text", "")
    if output_text:
        tts_play(output_text)  # 伪代码：播放到扬声器

    # 4. 结束条件：下一步动作为 END
    next_action = result.get("next_action") or {}
    na_type = next_action.get("type") if isinstance(next_action, dict) else getattr(next_action, "type", None)
    if na_type == "END":
        break
```

### 与当前设计的对应关系

- **student_input**：ASR 的转写文本（一次完整的回答或一句话）
- **silence_duration**：本轮统计到的有效沉默时长（秒），用于触发脚手架、判断卡顿等
- **多轮对话管理**：通过 `session_id` 与 LangGraph 的 checkpoint 机制自动管理
- **结束检测**：当 `next_action.type == "END"` 时，即可结束会话并输出最终报告

更多关于挂起机制与 ASR 集成的说明，可参考：

- `QUICK_REFERENCE.md`
- `test_fix.py`

---

## 现在是否支持“无 ASR 测试”？

是的，当前代码已经 **完全支持在没有 ASR 的情况下进行本地测试与实时面试**：

- 使用 `example_usage.py` 键盘输入即可全流程跑通
- 所有 ASR 相关参数（如 `silence_duration`）可以在本地测试阶段简单设为 `0.0`
- 当你准备接入 ASR 时，只需要：
  1. 在你自己的 ASR 模块中算出 `student_input` 和 `silence_duration`
  2. 用上面的伪代码调用 `InterviewStateMachine.process_turn`
  3. 利用已有的调试输出监控 LLM 行为与状态机状态

# 元认知面试系统

基于LangGraph实现的元认知面试系统,用于评估学生的元认知能力。

## 功能特性

- **6个状态的状态机**: S_INIT / S_WAIT / S_PROBE / S_SCAFFOLD / S_EVAL_RT / S_END
- **智能提问模块**: 从题库读取问题,使用LLM生成追问和认知压力问题
- **实时评估**: 使用千问LLM评估学生的元认知能力(规划/监控/评估/适应)
- **脚手架提示**: 三级提示系统(L1/L2/L3)帮助学生克服卡顿
- **异常处理**: 支持学生主动纠错和重置请求

## 环境配置

使用 `uv` 管理环境:

```bash
# 安装uv (如果还没有)
pip install uv

# 安装依赖
uv pip install -e .

# 配置API密钥
cp .env.example .env
# 编辑.env文件,填入您的DASHSCOPE_API_KEY
```

## 使用方法

```python
import os
from langchain_community.chat_models import ChatTongyi
from src.state_machine import InterviewStateMachine
import httpx

# 初始化LLM
llm = ChatTongyi(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model="qwen-plus",
    http_client=httpx.Client(trust_env=False)
)

# 创建状态机
state_machine = InterviewStateMachine(
    llm=llm,
    question_bank_path="question_bank.json"
)

# 处理第一轮(初始化)
result = state_machine.process_turn(
    session_id="test_session_1",
    student_input="",  # 初始为空
    silence_duration=0.0
)

print(result["output_text"])  # 显示初始问题和欢迎语

# 处理学生回答
result = state_machine.process_turn(
    session_id="test_session_1",
    student_input="我的第一步是确定活动目标和参与人数...",
    silence_duration=0.0
)

print(result["output_text"])  # 显示追问或评估结果
```

## 项目结构

```
Interview/
├── src/
│   ├── __init__.py
│   ├── models.py           # 数据模型
│   ├── question_module.py  # 提问模块
│   ├── evaluation.py       # 评估模块
│   ├── scaffold.py         # 脚手架提示
│   ├── state_machine.py   # LangGraph状态机
│   └── utils.py            # 工具函数
├── defination.md           # 状态机定义文档
├── openapi.yaml            # API接口规范
├── question_bank.json      # 题库
├── pyproject.toml          # 项目配置
└── README.md               # 本文件
```

## 状态机流程

1. **S_INIT**: 播放欢迎语,从题库随机选择初始问题
2. **S_WAIT**: 监听学生回答,计算沉默时长等特征
3. **S_EVAL_RT**: 实时评估学生回答的元认知能力
4. **S_PROBE**: 生成追问问题,施加认知压力
5. **S_SCAFFOLD**: 提供脚手架提示(L1/L2/L3)
6. **S_END**: 生成能力评估报告

## 异常处理

系统支持以下异常处理:

- **学生主动纠错**: 检测到"我搞错了"等信号,记录为元认知良好
- **重置请求**: 检测到"重新定义问题"等信号,跳转到S_INIT
- **沉默超时**: 超过阈值自动触发脚手架提示
- **LLM超时**: 使用基于规则的简单评估

## 注意事项

- 请确保已正确配置千问API密钥
- 题库文件 `question_bank.json` 需要存在
- 状态机使用LangGraph的checkpoint机制保存状态,支持会话恢复

