"""
LangGraph状态机实现
实现6个状态的元认知面试系统
"""
import os
from typing import Dict, Any, Literal, Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.chat_models import ChatTongyi

# ASR 开关: 开发阶段使用本地 input() 模拟 ASR,
# 上线时请将此开关改为 False, 使用真实 ASR 接口 /api/v1/asr/transcribe
USE_MOCK_ASR = True

from src.models import (
    SessionContext, SessionState, NextAction, NextActionType,
    ScaffoldLevel, ResetType, QuestionRef, EvaluationResult
)
from src.question_module import QuestionModule
from src.evaluation import EvaluationModule
from src.scaffold import ScaffoldModule
from src.utils import (
    detect_hesitation, clean_text, should_trigger_scaffold,
    determine_scaffold_level, determine_error_type
)


# 定义状态类型
class InterviewState(TypedDict):
    """状态机状态类型"""
    session_id: str
    context: SessionContext
    student_input: str
    student_answer: str
    silence_duration: float
    reset_detected: bool
    evaluation: EvaluationResult
    scaffold: Any
    next_action: NextAction
    output_text: str
    report: Dict[str, Any]
    has_evaluated: bool  # 【关键】标记本轮是否已评估过


class InterviewStateMachine:
    """面试状态机"""
    
    def __init__(
        self,
        llm=None,
        question_bank_path: str = "question_bank.json"
    ):
        """
        初始化状态机
        
        Args:
            llm: LLM实例(ChatTongyi或其他), 如果为None则自动创建
            question_bank_path: 题库路径
        """
        # 创建或使用传入的LLM实例
        if llm is None:
            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("未设置 DASHSCOPE_API_KEY 环境变量")
            import httpx
            self.llm = ChatTongyi(
                api_key=api_key,
                model="qwen-plus",
                http_client=httpx.Client(trust_env=False)
            )
        else:
            self.llm = llm
        
        self.question_module = QuestionModule(question_bank_path, self.llm)
        self.evaluation_module = EvaluationModule(self.llm)
        self.scaffold_module = ScaffoldModule(self.llm)
        
        # 构建状态图
        self.graph = self._build_graph()

    def _mock_asr_input(self) -> tuple[str, float]:
        """
        使用命令行 input() 模拟 ASR, 返回(文本, 沉默时长).

        仅在 USE_MOCK_ASR = True 时使用, 方便本地调试。
        """
        text = input("【ASR模拟】请输入学生回答(回车结束, 为空表示沉默): ").strip()
        # 简化起见, 本地模拟时沉默时长固定为 0.0
        return text, 0.0

    def _real_asr_input(self) -> tuple[str, float]:
        """
        调用真实 ASR 接口 /api/v1/asr/transcribe, 返回(文本, 沉默时长).

        说明:
        - 接口路径: /api/v1/asr/transcribe
        - 基础地址通过环境变量 ASR_BASE_URL 配置, 默认为 http://localhost:8000
        - 期望返回格式示例:
          {
            "text": "学生的回答文本",
            "silence_duration": 1.23
          }
        """
        base_url = os.getenv("ASR_BASE_URL", "http://localhost:8000").rstrip("/")
        url = f"{base_url}/api/v1/asr/transcribe"

        try:
            import httpx

            with httpx.Client(timeout=30.0, trust_env=False) as client:
                resp = client.post(url, json={})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            print(f"调用 ASR 接口失败: {e}")
            # 失败时返回空文本和 0.0 秒沉默, 由上层决定如何处理
            return "", 0.0

        text = str(data.get("text", "")).strip()
        try:
            silence = float(data.get("silence_duration", 0.0))
        except Exception:
            silence = 0.0

        return text, silence

    def get_asr_input(self) -> tuple[str, float]:
        """
        获取一轮学生输入:
        - 当 USE_MOCK_ASR = True 时, 使用本地 input() 模拟 ASR;
        - 当 USE_MOCK_ASR = False 时, 调用真实 ASR 接口。

        该方法仅封装"获取 student_input 和 silence_duration"的逻辑,
        不改变原有 process_turn 的接口与行为。
        """
        if USE_MOCK_ASR:
            return self._mock_asr_input()
        return self._real_asr_input()
    
    def _build_graph(self) -> StateGraph:
        """
        构建LangGraph状态图
        
        Returns:
            配置好的状态图
        """
        # 创建状态图
        workflow = StateGraph(InterviewState)
        
        # 添加节点
        workflow.add_node("S_INIT", self._state_init)
        workflow.add_node("S_WAIT", self._state_wait)
        workflow.add_node("S_PROBE", self._state_probe)
        workflow.add_node("S_SCAFFOLD", self._state_scaffold)
        workflow.add_node("S_EVAL_RT", self._state_eval_rt)
        workflow.add_node("S_END", self._state_end)
        
        # 设置入口点
        workflow.set_entry_point("S_INIT")
        
        # 添加边
        # 【修复】将 S_INIT 的出口改为 S_WAIT：初始化后进入等待状态
        # 这样第一次 invoke 会执行 S_INIT -> S_WAIT -> END（如果无输入）
        # 第二次 invoke(None) 会从 S_WAIT 恢复，避免重新执行 S_INIT 导致的死循环
        workflow.add_edge("S_INIT", "S_WAIT")
        
        # S_WAIT -> 根据输入决定路由
        # 【改进】当收到学生回答时进入评估；无输入时进入 END 挂起
        workflow.add_conditional_edges(
            "S_WAIT",
            self._route_from_wait,
            {
                "eval": "S_EVAL_RT",
                "reset": "S_INIT",
                "wait": END,  # 无输入时进入 END，不循环
                "end": "S_END"  # 支持显式 end 返回
            }
        )
        
        # S_EVAL_RT -> 根据评估结果路由
        workflow.add_conditional_edges(
            "S_EVAL_RT",
            self._route_from_eval,
            {
                "wait": "S_WAIT",
                "probe": "S_PROBE",
                "scaffold": "S_SCAFFOLD",
                "end": "S_END",
                "reset": "S_INIT"
            }
        )
        
        # S_PROBE -> S_WAIT 而不是 END 
        # 这样追问后系统会自动回到路由器，准备处理下一轮输入
        # 而不是卡在 END，导致 invoke(None) 无法继续
        workflow.add_edge("S_PROBE", "S_WAIT")

        # S_SCAFFOLD -> S_WAIT 而不是 END
        # 这样脚手架提示后系统会自动回到路由器，准备处理下一轮输入
        # 而不是卡在 END，导致 invoke(None) 无法继续
        workflow.add_edge("S_SCAFFOLD", "S_WAIT")
        
        # S_END -> END

        workflow.add_edge("S_END", END)
        
        # 编译图
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    def _state_init(self, state: InterviewState) -> InterviewState:
        """
        S_INIT状态: 初始化,播放欢迎语和规则,选择初始问题
        
        【优化】确保不会覆盖已有的context：
        - 如果context已存在且没有重置标记，说明这不是真正的初始化，直接返回
        - 这样可以防止在历史状态中重复执行初始化，导致评估缺失
        
        【修复】区分 PARTIAL_RESET 和 FULL_RESET：
        - PARTIAL_RESET（重新定义问题）：保留当前问题，重新组织思路
        - FULL_RESET（完全重新开始）：换题，清除历史
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("🟢 现在进入 S_INIT 状态")
        context: SessionContext = state.get("context")
        
        # 【优化】 如果context已存在且不是因为重置，说明不该进这里，直接返回
        # 这防止了盲目初始化时覆盖已有的评估历史和会话上下文
        if context is not None and not state.get("reset_detected"):
            print("[_state_init] ⚠️ Context已存在且无重置，跳过初始化，防止覆盖历史")
            return state
        
        if context is None:
            # 创建新会话
            from src.models import SessionContext
            context = SessionContext(
                session_id=state.get("session_id", "default_session")
            )
        
        # 【修复】检查是否有重置请求，并确定重置类型
        reset_detected = state.get("reset_detected", False)
        student_answer = state.get("student_answer", "")
        
        if reset_detected:
            # 通过检测学生答案来确定重置类型
            reset_info = self.evaluation_module.detect_reset_request(student_answer)
            reset_type = ResetType(reset_info["type"]) if reset_info else ResetType.FULL_RESET
        else:
            reset_type = None
        
        if reset_type == ResetType.PARTIAL_RESET:
            # 【修复重点】部分重置：重新定义问题但不换题
            context.metacognitive_signals.append(
                "学生主动要求重新定义问题 - 元认知监控能力良好"
            )
            welcome_text = "好的，没问题。那我们针对这个活动规划重新梳理一下思路。你刚才说要重新定义，那你现在的想法是？"
            
            # 【关键】保持当前问题不变，只重置对话轮数或清理本轮缓存
            initial_question = context.current_question
            # 但我们应该在这里清空本轮的回答缓存和评估，为新一轮思考做准备
            context.turn_index = 0  # 重置轮数，重新开始计算
            
        elif reset_type == ResetType.FULL_RESET:
            # 完全重置：彻底重来，换题
            context.metacognitive_signals.append(
                "学生主动请求完全重新开始 - 元认知调节能力良好"
            )
            welcome_text = "没问题，那我们换一个话题重新开始。" + self._get_welcome_message()
            initial_question = self.question_module.get_initial_question()
            # 重置所有上下文
            context.conversation_history = []
            context.evaluation_history = []
            context.turn_index = 0
            
        else:
            # 正常初始化（非重置）
            welcome_text = self._get_welcome_message()
            initial_question = self.question_module.get_initial_question()
        
        context.current_question = initial_question
        context.state = SessionState.S_WAIT
        context.reset_type = None  # 清除重置标记
        
        # 构建完整的问题文本(包含欢迎语)
        full_question_text = f"{welcome_text}\n\n{initial_question.text}"
        
        # 更新状态
        state["context"] = context
        state["next_action"] = NextAction(
            type=NextActionType.ASK,
            text=full_question_text
        )
        state["output_text"] = full_question_text
        # 清除重置检测标记，避免在同一次 invoke 中重复触发 reset 路由
        state["reset_detected"] = False
        # 清空本次 invoke 的输入，确保初始化后不会再用相同的触发词重复进入 S_WAIT
        state["student_input"] = ""
        state["student_answer"] = ""
        
        return state
    
    def _get_welcome_message(self) -> str:
        """获取欢迎语"""
        return """欢迎参加元认知面试!

本次面试旨在评估您的元认知能力,包括:
- 规划能力: 能否制定清晰的计划并分解目标
- 监控能力: 能否监控自己的思维过程,发现错误
- 评估能力: 能否评估自己的方案和结果
- 适应能力: 能否根据情况变化灵活调整

请放松,如实回答即可。如果您在思考过程中发现需要调整,可以随时说明。"""
    
    def _state_wait(self, state: InterviewState) -> InterviewState:
        """
        S_WAIT状态: 监听学生回答,计算沉默时长等特征
        
        【修复】如果没有学生输入，说明是刚从S_INIT过来或者刚发出了追问，直接返回
        不再被迫运行，由_route_from_wait决定是否挂起还是继续处理
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("⏳ 现在进入 S_WAIT 状态")
        context: SessionContext = state.get("context")
        # 如果context不存在,说明是第一次调用,应该先经过S_INIT
        if context is None:
            # 这种情况不应该发生,但如果发生了,创建一个默认context
            from src.models import SessionContext
            context = SessionContext(session_id=state.get("session_id", "default"))
            state["context"] = context
        
        # 获取学生输入
        student_input = state.get("student_input", "")
        silence_duration = state.get("silence_duration", 0.0)
        
        # 【关键】如果没有输入，说明是刚从 S_INIT 过来或系统在等待，直接返回
        # 由 _route_from_wait 根据情况决定是否挂起（返回"wait"进 END）
        if not student_input:
            print(f"[S_WAIT] 无学生输入，状态保持，等待外部继续调用...")
            # 【核心修复】清空 student_answer，防止路由器被上一轮的残留值欺骗
            state["student_answer"] = ""
            state["context"] = context
            return state
        
        # 更新沉默时长
        context.silence_duration = silence_duration
        
        # 有输入时才进行清理和检测
        cleaned_text = clean_text(student_input)
        state["student_answer"] = cleaned_text
        
        # 检测重置请求
        reset_info = self.evaluation_module.detect_reset_request(cleaned_text)
        if reset_info:
            context.reset_type = ResetType(reset_info["type"])
            state["reset_detected"] = True
            return state
        
        # 检测元认知信号
        signals = self.evaluation_module.detect_metacognitive_signals(cleaned_text)
        context.metacognitive_signals.extend(signals)
        
        # 更新状态
        state["context"] = context
        
        return state
    
    def _route_from_wait(self, state: InterviewState) -> str:
        """
        从S_WAIT状态路由 - 【修复】与新的图架构兼容
        
        新流程（修复后）：
        - 第一次invoke(initial_input)：S_INIT -> S_WAIT -> 返回"wait"进 END
        - 第二次invoke(None)：从 S_WAIT 恢复 -> 根据新输入决定
        
        规则（按优先级）：
        1. 如果检测到重置请求 -> reset
        2. 如果有有效的学生回答（非空） -> eval （【修复】确保优先于脚手架）
        3. 否则 -> wait（返回 END 进行挂起，等待外部新 invoke）
        
        Args:
            state: 当前状态
            
        Returns:
            下一个状态名称
        """
        print(f"\n[路由器] ------- 进入 _route_from_wait -------")
        
        # 获取学生输入与沉默时长
        student_answer = state.get("student_answer", "").strip()
        silence_duration = state.get("silence_duration", 0.0)
        has_evaluated = state.get("has_evaluated", False)
        reset_detected = state.get("reset_detected", False)

        print(f"[路由器] student_answer: '{student_answer}' (长度: {len(student_answer)})")
        print(f"[路由器] has_evaluated: {has_evaluated}")
        print(f"[路由器] silence_duration: {silence_duration}")
        print(f"[路由器] reset_detected: {reset_detected}")
        
        # 检测重置请求（优先级最高）
        if reset_detected:
            print(f"[路由器] ✓ 检测到重置请求 -> 返回 'reset'")
            return "reset"

        # 【双检机制】如果 reset_detected 为 False 但答案中包含重置关键词，强制识别为重置
        if student_answer:
            reset_info = self.evaluation_module.detect_reset_request(student_answer)
            if reset_info:
                print(f"[路由器] ✓ 双检发现重置请求: {reset_info} -> 返回 'reset'")
                return "reset"

        # 只要有有效的学生回答（非空），**必须优先进入评估**
        # 这是打破脚手架死循环的关键：确保所有输入都有机会被评估，而不是直接判入脚手架
        if student_answer:
            print(f"[路由器] ✓ 有效输入（无论是否已评估）-> 优先返回 'eval'")
            return "eval"

        # 如果沉默时间过长（例如 60 秒），将会话结束，避免长期挂起导致问题
        try:
            if float(silence_duration) >= 60.0:
                print(f"[路由器] ⏱ 沉默超时 -> 返回 'end'")
                return "end"
        except Exception:
            pass

        # 【关键修复】默认返回 "wait"，会进入 END（挂起）
        # 这样状态机会安全地等待下一次外部 invoke 调用
        # 下一次 invoke(None, config) 时，LangGraph 会从 S_WAIT 之后恢复执行
        print(f"[路由器] ⏸ 无有效输入 -> 返回 'wait' (系统挂起，等待外部输入)\n")
        return "wait"
    
    def _state_eval_rt(self, state: InterviewState) -> InterviewState:
        """
        S_EVAL_RT状态: 实时评估学生回答
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("🔎 现在进入 S_EVAL_RT 状态")
        context: SessionContext = state.get("context")
        if context is None:
            raise ValueError("上下文不存在")
        
        student_answer = state.get("student_answer", "")
        question = context.current_question
        
        if not question:
            raise ValueError("当前没有活跃的问题")
        
        # 再次检测重置请求(可能在评估阶段发现)
        reset_info = self.evaluation_module.detect_reset_request(student_answer)
        if reset_info:
            context.reset_type = ResetType(reset_info["type"])
            state["reset_detected"] = True
            state["context"] = context
            return state
        
        # 评估回答
        scaffold_used = None
        if context.scaffold_level_used:
            scaffold_used = {
                "used": True,
                "level": context.scaffold_level_used
            }
        
        try:
            print(f"\n[状态机] ===== 进入 S_EVAL_RT 状态 =====")
            evaluation = self.evaluation_module.evaluate_answer(
                question=question.text,
                answer=student_answer,
                conversation_history=context.conversation_history,
                scaffold_used=scaffold_used
            )
            print(f"[状态机] ✓ 评估完成 - 平均分: {(evaluation.scores.plan + evaluation.scores.monitor + evaluation.scores.evaluate + evaluation.scores.adapt) / 4:.2f}\n")
        except Exception as e:
            print(f"评估失败: {e}, 使用默认评估")
            # 使用默认评估
            from src.models import DimScores
            evaluation = EvaluationResult(
                scores=DimScores(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5),
                confidence=0.3
            )
        
        # 保存评估结果
        context.evaluation_history.append(evaluation)
        
        # 记录对话历史
        context.conversation_history.append({
            "question": question.text,
            "answer": student_answer,
            "turn_index": context.turn_index
        })
        context.turn_index += 1
        
        # 更新状态
        state["context"] = context
        state["evaluation"] = evaluation
        # 标记本轮回答已经完成一次评估, 防止在同一次 process_turn 调用中重复评估
        state["has_evaluated"] = True
        
        return state
    
    def _route_from_eval(self, state: InterviewState) -> str:
        """
        从S_EVAL_RT状态路由 - 【改进】增强 ASR 兼容性
        
        规则（按优先级）：
        1. 如果检测到重置请求 -> reset
        2. 如果需要脚手架（基于犹豫度或沉默时长）-> scaffold
        3. 如果回答质量高且轮次未达上限 -> probe
        4. 如果回答完成或轮次达上限 -> end
        5. 否则 -> wait（安全返回等待下一次 invoke）
        """

        print(f"\n[路由器] ------- 进入 _route_from_eval -------")

        # 获取必要字段
        context: SessionContext = state.get("context")
        evaluation = state.get("evaluation")
        student_answer = state.get("student_answer", "")
        silence_duration = state.get("silence_duration", 0.0)

        # 如果缺少上下文或评估结果，安全回退到等待
        if context is None or evaluation is None:
            print("[路由器] 缺失 context 或 evaluation -> 返回 'wait'")
            return "wait"

        # 检测重置请求优先级最高
        if state.get("reset_detected"):
            print("[路由器] 检测到重置请求 -> 返回 'reset'")
            return "reset"

        # 计算犹豫度和错误类型
        hesitation_rate = detect_hesitation(student_answer)
        error_type = determine_error_type(
            student_answer,
            context.silence_duration,
            hesitation_rate
        )

        # 判断是否需要脚手架（多条件）
        if should_trigger_scaffold(
            context.silence_duration,
            hesitation_rate,
            student_answer
        ):
            print("[路由器] 触发脚手架条件 -> 返回 'scaffold'")
            return "scaffold"

        # ASR 兼容性：无输入但沉默超过阈值，触发脚手架
        if not student_answer and context.silence_duration > 5.0:
            print("[路由器] 无输入且沉默超过5秒 -> 返回 'scaffold'")
            return "scaffold"

        # 计算平均评分，兼容 dict 或 对象
        try:
            if isinstance(evaluation, dict):
                scores = evaluation.get("scores")
            else:
                scores = evaluation.scores

            if isinstance(scores, dict):
                avg_score = (
                    scores.get("plan", 0.5) +
                    scores.get("monitor", 0.5) +
                    scores.get("evaluate", 0.5) +
                    scores.get("adapt", 0.5)
                ) / 4.0
            else:
                avg_score = (
                    scores.plan +
                    scores.monitor +
                    scores.evaluate +
                    scores.adapt
                ) / 4.0

            print(f"[路由器] 平均评分: {avg_score:.2f}, 轮次: {context.turn_index}")
        except Exception as e:
            print(f"[路由器] 计算评分异常: {e} -> 返回 'probe'")
            return "probe"

        # 高质量回答时进行追问施压
        if avg_score > 0.6 and context.turn_index < 10:
            print("[路由器] ✓ 高质量回答 (分数 > 0.6) -> 返回 'probe'")
            return "probe"

        # 回答完成或达到轮次上限
        if context.turn_index >= 10 or self._is_answer_complete(student_answer):
            print("[路由器] 回答完成或轮次达上限 -> 返回 'end'")
            return "end"

        # 低分时考虑脚手架或追问
        if avg_score <= 0.6 and context.turn_index < 10:
            if error_type in ["STUCK", "OFFTRACK", "LOOP", "FACT_ERROR", "HIGH_STRESS"]:
                print(f"[路由器] 低分且有明确错误类型 ({error_type}) -> 返回 'scaffold'")
                return "scaffold"
            else:
                print("[路由器] 低分回答但无明确错误类型 -> 返回 'probe'")
                return "probe"

        # 兜底等待
        print("[路由器] 其他情况 -> 返回 'wait'")
        return "wait"
    
    def _is_answer_complete(self, answer: str) -> bool:
        """判断回答是否完成"""
        complete_keywords = ["回答完毕", "就是这样", "说完了", "就这些"]
        answer_lower = answer.lower()
        return any(keyword in answer_lower for keyword in complete_keywords)
    
    def _state_probe(self, state: InterviewState) -> InterviewState:
        """
        S_PROBE状态: 生成追问问题,施加认知压力
        
        【优化】在发出追问后，重置评估标记并清空学生回答，
        确保系统强制等待外部新输入而不是立即跳到评估。
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("🧭 现在进入 S_PROBE 状态")
        context: SessionContext = state.get("context")
        if context is None:
            raise ValueError("上下文不存在")
        
        student_answer = state.get("student_answer", "")
        
        # 生成认知压力问题
        try:
            probe_question = self.question_module.generate_probe_question(
                student_answer=student_answer,
                conversation_history=context.conversation_history
            )
        except Exception as e:
            print(f"生成追问失败: {e}")
            # 使用简单追问
            probe_question = QuestionRef(
                qid=context.current_question.qid if context.current_question else None,
                text="如果情况发生变化,你会如何调整你的方案?"
            )
        
        context.current_question = probe_question
        
        # 更新状态
        state["context"] = context
        state["next_action"] = NextAction(
            type=NextActionType.PROBE,
            text=probe_question.text
        )
        state["output_text"] = probe_question.text
        
        # 发出追问后，只重置评估标记，不清空 student_answer
        # 原因：student_answer 是学生对前一个问题的回答，清空它会丢失评估基础
        # 只有当接收到明确的新回答时，process_turn 才会更新 student_answer
        state["has_evaluated"] = False
        # 同步清空 student_input，避免在同一次 invoke 中被重新读取
        state["student_input"] = ""
        print(f"\n[S_PROBE] ✓ 发出追问: {probe_question.text[:80]}...")
        
        return state
    
    def _state_scaffold(self, state: InterviewState) -> InterviewState:
        """
        S_SCAFFOLD状态: 生成脚手架提示
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("🛠️ 现在进入 S_SCAFFOLD 状态")
        context: SessionContext = state.get("context")
        if context is None:
            raise ValueError("上下文不存在")
        
        student_answer = state.get("student_answer", "")
        question = context.current_question
        
        if not question:
            raise ValueError("当前没有活跃的问题")
        
        # 确定脚手架级别
        scaffold_level_str = determine_scaffold_level(
            context.silence_duration,
            context.scaffold_level_used.value if context.scaffold_level_used else None,
            consecutive_failures=0  # 可以扩展记录连续失败次数
        )
        scaffold_level = ScaffoldLevel(scaffold_level_str)
        
        # 确定错误类型
        hesitation_rate = detect_hesitation(student_answer)
        error_type = determine_error_type(
            student_answer,
            context.silence_duration,
            hesitation_rate
        )
        
        # 生成脚手架提示
        scaffold_result = self.scaffold_module.generate_scaffold(
            level=scaffold_level,
            question=question.text,
            student_answer=student_answer,
            error_type=error_type,
            state=context.state
        )
        
        # 更新上下文
        context.scaffold_level_used = scaffold_level
        
        # 更新状态
        state["context"] = context
        state["scaffold"] = scaffold_result
        
        if scaffold_result.fired and scaffold_result.prompt:
            state["next_action"] = NextAction(
                type=NextActionType.SCAFFOLD,
                text=scaffold_result.prompt,
                level=scaffold_level
            )
            state["output_text"] = scaffold_result.prompt
        
        # 【核心修复】脚手架执行完后，清空 student_answer 和 student_input
        # 这是防止死循环的关键：确保下一轮只有真正的新输入才会被路由器检测到
        state["has_evaluated"] = False
        state["student_answer"] = ""
        state["student_input"] = ""
        print(f"\n[S_SCAFFOLD] ✓ 发出脚手架提示: {scaffold_result.prompt[:80] if scaffold_result.prompt else '(未触发)'}...")
        print(f"[S_SCAFFOLD] 已清空 student_answer 和重置 has_evaluated，等待新输入\n")
        
        return state
    
    def _state_end(self, state: InterviewState) -> InterviewState:
        """
        S_END状态: 生成能力评估报告
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态
        """
        print("📋 现在进入 S_END 状态")
        context: SessionContext = state.get("context")
        if context is None:
            raise ValueError("上下文不存在")
        
        # 使用完整历史生成报告（累加而非覆盖）
        history = context.evaluation_history or []

        if history:
            total_plan = total_monitor = total_evaluate = total_adapt = 0.0
            score_history = []

            for e in history:
                if isinstance(e, dict):
                    scores = e.get("scores")
                else:
                    scores = e.scores

                if isinstance(scores, dict):
                    p = float(scores.get("plan", 0.0))
                    m = float(scores.get("monitor", 0.0))
                    ev = float(scores.get("evaluate", 0.0))
                    a = float(scores.get("adapt", 0.0))
                    score_history.append({"plan": p, "monitor": m, "evaluate": ev, "adapt": a})
                else:
                    p = float(getattr(scores, "plan", 0.0))
                    m = float(getattr(scores, "monitor", 0.0))
                    ev = float(getattr(scores, "evaluate", 0.0))
                    a = float(getattr(scores, "adapt", 0.0))
                    score_history.append({"plan": p, "monitor": m, "evaluate": ev, "adapt": a})

                total_plan += p
                total_monitor += m
                total_evaluate += ev
                total_adapt += a

            count = len(score_history)
            avg_scores = {
                "plan": total_plan / count,
                "monitor": total_monitor / count,
                "evaluate": total_evaluate / count,
                "adapt": total_adapt / count,
            }
        else:
            # 如果没有历史则使用 0.0 起始（显式反映未评估）
            avg_scores = {"plan": 0.0, "monitor": 0.0, "evaluate": 0.0, "adapt": 0.0}
            score_history = []

        # 生成报告文本
        report_text = self._generate_report(avg_scores, context)

        # 更新状态
        context.state = SessionState.S_END
        state["context"] = context
        state["next_action"] = NextAction(
            type=NextActionType.END,
            text=report_text
        )
        # 提供更丰富的报告结构: 最终摘要、每轮得分历史、以及所有元认知信号
        state["report"] = {
            "final_summary": report_text,
            "score_history": score_history,
            "total_metacognitive_signals": context.metacognitive_signals,
            "total_turns": context.turn_index
        }
        state["output_text"] = report_text

        return state
    
    def _generate_report(self, scores: Dict[str, float], context: SessionContext) -> str:
        """生成评估报告"""
        report_parts = [
            "=" * 50,
            "元认知能力评估报告",
            "=" * 50,
            "",
            f"总轮次: {context.turn_index}",
            "",
            "维度评分:",
            f"  规划能力 (Plan): {scores['plan']:.2f}",
            f"  监控能力 (Monitor): {scores['monitor']:.2f}",
            f"  评估能力 (Evaluate): {scores['evaluate']:.2f}",
            f"  适应能力 (Adapt): {scores['adapt']:.2f}",
            "",
        ]
        
        if context.metacognitive_signals:
            report_parts.extend([
                "元认知信号:",
            ])
            for signal in context.metacognitive_signals:
                report_parts.append(f"  - {signal}")
            report_parts.append("")
        
        report_parts.append("=" * 50)
        
        return "\n".join(report_parts)
    
    def process_turn(
        self,
        session_id: str,
        student_input: str = "",
        silence_duration: float = 0.0,
        config: Dict[str, Any] = None
    ) -> InterviewState:
        """
        处理一轮对话 - 【修复版】
        
        核心修复：
        - 当 invoke 第一次被调用时，执行完整的初始化流程：S_INIT -> S_WAIT -> END
          输出欢迎语和第一个问题，然后等待外部输入
        
        - 当 invoke 第二次及以后被调用时，只需更新 student_input，然后调用 invoke(None)
          LangGraph 会从上一次中断点（S_WAIT）恢复执行，避免重复初始化
        
        这样就打破了"死循环 S_INIT"的问题：
        1. 不再从 S_INIT -> END，而是 S_INIT -> S_WAIT -> END
        2. 第二次 invoke 从 S_WAIT 恢复，不会再执行 S_INIT
        3. 评估流程可以正常进行
        
        Args:
            session_id: 会话ID
            student_input: 学生输入
            silence_duration: 沉默时长(秒)
            config: LangGraph配置
            
        Returns:
            处理结果
        """
        if config is None:
            config = {"configurable": {"thread_id": session_id}}
        
        try:
            # 【核心】检查是否已有历史状态
            existing_state = self.graph.get_state(config)
            
            if not existing_state.values:
                # ============ 第一次调用：执行完整初始化 ============
                print("[process_turn] 🚀 第一次调用 - 无历史状态，执行初始化流程（S_INIT）")
                initial_input: InterviewState = {
                    "session_id": session_id,
                    "context": None,  # 将在S_INIT中创建
                    "student_input": student_input,  # 第一次通常为空
                    "student_answer": "",
                    "silence_duration": silence_duration,
                    "reset_detected": False,
                    "evaluation": None,
                    "scaffold": None,
                    "next_action": None,
                    "output_text": "",
                    "report": {},
                    "has_evaluated": False
                }
                
                # 第一次 invoke：S_INIT -> S_WAIT -> END（如果没有输入）
                # 这会输出欢迎语和第一个问题，然后挂起
                result = self.graph.invoke(initial_input, config)
                print("[process_turn] ✓ 初始化完成，系统已挂起，等待学生输入")
                return result
            else:
                # ============ 第二次及以后的调用：从 S_WAIT 恢复执行 ============
                print("[process_turn] 🔄 后续调用 - 已有历史状态，从 S_WAIT 恢复执行")
                print(f"    学生输入: '{student_input}'")
                print(f"    沉默时长: {silence_duration}s")
                
                # 【关键修复】预先清洗输入，避免路由器看不到有效答案
                # 因为 invoke(None) 会直接跳过 _state_wait 节点的清洗逻辑
                cleaned_ans = clean_text(student_input)
                
                # --- 新增：手动检测重置意图 ---
                # 【重要】这里提前识别"重新定义问题"等重置行为，确保路由器能看到
                reset_info = self.evaluation_module.detect_reset_request(cleaned_ans)
                is_reset = True if reset_info else False
                if is_reset:
                    print(f"[process_turn] 🔄 检测到重置请求: {reset_info}")
                
                # 【关键步骤1】通过 update_state 更新当前的输入信息
                # 这会修改 checkpoint 中保存的 state，为下一步执行做准备
                self.graph.update_state(config, {
                    "student_input": student_input,
                    "student_answer": cleaned_ans,  # 直接更新清洗后的答案
                    "silence_duration": silence_duration,
                    "has_evaluated": False,  # 重置评估标记，准备新一轮评估
                    "reset_detected": is_reset  # 【修复】确保路由器能看到检测到的重置信号
                })
                print("[process_turn] ✓ State 已更新")
                
                # 【关键步骤2】调用 invoke(None, config)
                # LangGraph 会：
                # 1. 读取 checkpoint 中的保存状态
                # 2. 应用 update_state 的改动
                # 3. 从上一次中断点（S_WAIT 之后的 conditional edge）恢复执行
                # 4. 由于 student_input 现在不为空，_route_from_wait 会返回 "eval"
                # 5. 执行 S_EVAL_RT 进行评估
                result = self.graph.invoke(None, config)
                print("[process_turn] ✓ 本轮处理完成")
                return result
                
        except Exception as e:
            print(f"❌ 状态机执行失败: {e}")
            raise
















