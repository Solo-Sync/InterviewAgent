"""
使用示例
演示如何使用元认知面试系统(支持键盘交互)
"""
import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatTongyi  # type: ignore[import]
from src.state_machine import InterviewStateMachine
import httpx

load_dotenv()


def _print_state_debug(result):
    """打印状态机调试信息,包括当前状态和下一步动作"""
    context = result.get("context")
    if context is not None:
        try:
            state = context.state
            turn_index = context.turn_index
        except AttributeError:
            state = context.get("state")
            turn_index = context.get("turn_index")
        print(f"【调试】当前状态: {state}, 轮次: {turn_index}")

    next_action = result.get("next_action")
    if next_action is not None:
        if isinstance(next_action, dict):
            na_type = next_action.get("type")
        else:
            na_type = next_action.type
        # 仅打印下一步动作类型,避免重复打印已由主流程输出的系统文本



def _print_evaluation(result):
    """打印评估分数(如果有)"""
    evaluation = result.get("evaluation")
    if not evaluation:
        return

    # 兼容 EvaluationResult 对象和 dict 两种情况
    if isinstance(evaluation, dict):
        scores = evaluation.get("scores", {})
    else:
        scores = evaluation.scores

    # 如果是字典，用中括号；如果是对象，用点
    if isinstance(scores, dict):
        plan = scores.get("plan", 0)
        monitor = scores.get("monitor", 0)
        evaluate = scores.get("evaluate", 0)
        adapt = scores.get("adapt", 0)
    else:
        plan = scores.plan
        monitor = scores.monitor
        evaluate = scores.evaluate
        adapt = scores.adapt

    print(f"【评估】规划:{plan:.2f} 监控:{monitor:.2f} "
          f"评估:{evaluate:.2f} 适应:{adapt:.2f}")
    print()


def main():
    """主函数: 支持键盘交互式面试"""
    # 初始化LLM客户端(从环境变量读取API密钥)
    api_key = os.getenv("DASHSCOPE_API_KEY")
    try:
        llm = ChatTongyi(
            api_key=api_key,
            model="qwen-plus",
            http_client=httpx.Client(trust_env=False)
        )
    except ValueError as e:
        print(f"错误: {e}")
        print("请设置DASHSCOPE_API_KEY环境变量")
        return

    # 创建状态机
    state_machine = InterviewStateMachine(
        llm=llm,
        question_bank_path="question_bank.json"
    )

    session_id = "cli_session_1"

    print("=" * 60)
    print("元认知面试系统 - 交互式命令行")
    print("=" * 60)
    print("提示: 输入 'exit' 或 'quit' 可随时结束面试。")
    print()

    # 第一轮: 初始化
    print("【系统】初始化面试...")
    result = state_machine.process_turn(
        session_id=session_id,
        student_input="",
        silence_duration=0.0
    )
    # 输出规则说明和第一个问题
    output = result.get("output_text", "")
    if output:
        print(f"【系统】{output}")
        print()
    _print_state_debug(result)

    # 交互式循环: 键盘输入学生回答
    while True:
        answer = input("【你】").strip()
        if not answer:
            print("请输入内容,或输入 'exit' 结束面试。")
            continue
        if answer.lower() in {"exit", "quit", "q"}:
            print("已退出面试。")
            break

        result = state_machine.process_turn(
            session_id=session_id,
            student_input=answer,
            silence_duration=0.0
        )

        # 重置逻辑由状态机内部处理（S_INIT -> END 已改为不自动回到 S_WAIT）

        # 输出系统回复/下一问题
        output = result.get("output_text", "")
        if output:
            print(f"【系统】{output}")
            print()

        # 打印状态机调试信息和评估结果
        _print_state_debug(result)
        _print_evaluation(result)

        # 如果到达结束状态,显示报告并退出
        next_action = result.get("next_action") or {}
        na_type = next_action.get("type") if isinstance(next_action, dict) else getattr(next_action, "type", None)
        if na_type == "END":
            print("=" * 60)
            print("面试结束")
            print("=" * 60)
            report = result.get("report", {})
            if report:
                print("最终评分与元认知信号见 report 字段:")
                print(report)
            break


if __name__ == "__main__":
    main()

