"""
评估模块
使用LLM评估学生回答的质量和元认知能力
"""
import os
from typing import Optional, Dict, Any, List
from langchain_community.chat_models import ChatTongyi  # type: ignore[import]
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from src.models import EvaluationResult, DimScores


class EvaluationScore(BaseModel):
    """评估分数结构"""
    plan: float = Field(..., description="规划能力评分 (0.0-1.0)")
    monitor: float = Field(..., description="监控能力评分 (0.0-1.0)")
    evaluate: float = Field(..., description="评估能力评分 (0.0-1.0)")
    adapt: float = Field(..., description="适应能力评分 (0.0-1.0)")


class EvaluationOutput(BaseModel):
    """评估输出结构"""
    scores: EvaluationScore
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="评估证据列表")
    metacognitive_signals: List[str] = Field(default_factory=list, description="元认知信号列表")
    confidence: float = Field(default=0.5, description="评估置信度 (0.0-1.0)")


class EvaluationModule:
    """评估模块"""
    
    def __init__(self, llm=None):
        """
        初始化评估模块
        
        Args:
            llm: LLM实例(ChatTongyi或其他), 如果为None则自动创建
        """
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
    
    def evaluate_answer(
        self,
        question: str,
        answer: str,
        conversation_history: List[Dict[str, Any]],
        scaffold_used: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        评估学生回答
        
        Args:
            question: 问题文本
            answer: 学生回答
            conversation_history: 对话历史
            scaffold_used: 是否使用了脚手架提示
            
        Returns:
            评估结果
        """
        # 构建评估提示
        system_prompt = """你是一位专业的元认知能力评估专家。
你需要从以下四个维度评估学生的回答:
1. **规划(plan)**: 学生是否制定了清晰的计划,是否能够分解目标为具体步骤
2. **监控(monitor)**: 学生是否能够监控自己的思维过程,发现错误或偏离
3. **评估(evaluate)**: 学生是否能够评估自己的方案和结果,进行反思
4. **适应(adapt)**: 学生是否能够根据情况变化灵活调整策略

每个维度的评分范围是0.0-1.0,请给出精确的分数。"""
        
        scaffold_info = ""
        if scaffold_used and scaffold_used.get("used"):
            scaffold_info = f"\n注意: 学生使用了{scaffold_used.get('level', 'L1')}级别的脚手架提示,请在评分时适当考虑这一点。"
        
        prompt = f"""问题: {question}

学生回答: {answer}

对话历史:
{self._format_history(conversation_history)}
{scaffold_info}

请评估学生的元认知能力。返回JSON格式的评估结果,包含以下字段:
- scores: 包含plan、monitor、evaluate、adapt四个字段的对象,每个值为0.0-1.0之间的浮点数
- evidence: 证据列表,每个证据包含dimension、quote、reason三个字段
- metacognitive_signals: 元认知信号列表(字符串数组)
- confidence: 评估置信度,0.0-1.0之间的浮点数"""
        
        try:
            result = self._generate_evaluation_json(
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            # 解析结果并做类型校验
            if not isinstance(result, dict):
                raise ValueError("LLM 返回格式异常，期望 dict")

            # scores已经是DimScores对象
            dim_scores = result.get("scores")
            if not isinstance(dim_scores, DimScores):
                # 如果不是DimScores对象，创建默认值
                dim_scores = DimScores(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5)

            evidence = result.get("evidence") if isinstance(result.get("evidence"), list) else []
            confidence = result.get("confidence")
            try:
                confidence = float(confidence) if confidence is not None else 0.3
            except Exception:
                confidence = 0.3

            metacognitive_signals = result.get("metacognitive_signals") if isinstance(result.get("metacognitive_signals"), list) else []

            return EvaluationResult(
                scores=dim_scores,
                evidence=evidence,
                confidence=confidence
            )
        except Exception as e:
            print(f"\n[评估] ❌ 评估异常: {type(e).__name__}: {str(e)[:200]}")
            print(f"[评估] 使用默认评分 (0.5, 0.5, 0.5, 0.5)\n")
            # 返回默认评分，确保返回类型始终合法
            return EvaluationResult(
                scores=DimScores(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5),
                confidence=0.3
            )
    
    def _generate_evaluation_json(
        self,
        prompt: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """
        使用LangChain JsonOutputParser生成JSON格式的评估结果
        
        Args:
            prompt: 提示词
            system_prompt: 系统提示词
            
        Returns:
            解析后的JSON结果
        """
        default_res = {
            "scores": DimScores(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5),
            "evidence": [],
            "metacognitive_signals": [],
            "confidence": 0.3
        }
        
        try:
            # 创建JsonOutputParser
            parser = JsonOutputParser(pydantic_object=EvaluationOutput)
            
            # 构建消息
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # 调用LLM
            print("\n[评估] 正在调用 LLM 进行评估...")
            response = self.llm.invoke(messages)
            response_text = response.content
            print(f"[评估] LLM 原始输出 (前500字符):\n{response_text[:500]}...\n")
            
            # 如果响应是JSON格式的code block，提取出来
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            print(f"[评估] 提取后的 JSON:\n{response_text[:300]}...\n")
            
            # 使用parser解析
            print("[评估] 正在解析 JSON...")
            result = parser.parse(response_text)
            print(f"[评估] 解析结果类型: {type(result)}, 内容摘要: {str(result)[:300]}...\n")

            # 兼容两种返回形式：
            # 1) EvaluationOutput Pydantic 模型
            # 2) dict（某些版本的 LangChain 可能返回纯 dict）
            if isinstance(result, EvaluationOutput):
                scores_model = result.scores
                evidence = result.evidence
                metacognitive_signals = result.metacognitive_signals
                confidence = result.confidence
            elif isinstance(result, dict):
                scores_raw = result.get("scores", {})
                # scores_raw 可能是 dict 或 EvaluationScore
                if isinstance(scores_raw, dict):
                    scores_model = EvaluationScore(
                        plan=float(scores_raw.get("plan", 0.5)),
                        monitor=float(scores_raw.get("monitor", 0.5)),
                        evaluate=float(scores_raw.get("evaluate", 0.5)),
                        adapt=float(scores_raw.get("adapt", 0.5)),
                    )
                else:
                    scores_model = scores_raw

                evidence = result.get("evidence") or []
                metacognitive_signals = result.get("metacognitive_signals") or []
                confidence = result.get("confidence") or 0.3
            else:
                # 异常情况，直接使用默认值
                scores_model = EvaluationScore(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5)
                evidence = []
                metacognitive_signals = []
                confidence = 0.3

            # 统一转换为 DimScores + 普通 dict 结构
            print(f"[评估] 最终评分 - plan: {scores_model.plan}, monitor: {scores_model.monitor}, evaluate: {scores_model.evaluate}, adapt: {scores_model.adapt}")
            return {
                "scores": DimScores(
                    plan=scores_model.plan,
                    monitor=scores_model.monitor,
                    evaluate=scores_model.evaluate,
                    adapt=scores_model.adapt,
                ),
                "evidence": evidence,
                "metacognitive_signals": metacognitive_signals,
                "confidence": confidence,
            }
        except Exception as e:
            print(f"JSON解析失败: {e}")
            # 返回默认值，scores也使用DimScores对象
            return {
                "scores": DimScores(plan=0.5, monitor=0.5, evaluate=0.5, adapt=0.5),
                "evidence": [],
                "metacognitive_signals": [],
                "confidence": 0.3
            }
    
    def detect_reset_request(self, answer: str) -> Optional[Dict[str, Any]]:
        """
        检测学生是否请求重置
        
        Args:
            answer: 学生回答
            
        Returns:
            如果检测到重置请求,返回重置信息,否则返回None
        """
        reset_keywords_full = [
            "重新开始",
            "我们重新开始吧",
            "完全重新开始",
            "从头再来"
        ]
        
        reset_keywords_partial = [
            "重新定义问题",
            "我重新定义一下",
            "目标定错了",
            "我要重新定义",
            "我发现我最开始的目标定错了"
        ]
        
        answer_lower = answer.lower()
        
        # 检测完全重置
        for keyword in reset_keywords_full:
            if keyword in answer_lower:
                return {
                    "type": "full_reset",
                    "confidence": 0.9,
                    "reason": f"检测到完全重置请求: {keyword}"
                }
        
        # 检测部分重置
        for keyword in reset_keywords_partial:
            if keyword in answer_lower:
                return {
                    "type": "partial_reset",
                    "confidence": 0.9,
                    "reason": f"检测到部分重置请求: {keyword}"
                }
        
        return None
    
    def detect_metacognitive_signals(self, answer: str) -> List[str]:
        """
        检测元认知信号
        
        Args:
            answer: 学生回答
            
        Returns:
            检测到的元认知信号列表
        """
        signals = []
        
        # 监控信号
        monitor_keywords = ["我发现", "我意识到", "我注意到", "我察觉到"]
        for keyword in monitor_keywords:
            if keyword in answer:
                signals.append(f"监控信号: {keyword}")
        
        # 调节信号
        adapt_keywords = ["我搞错了", "让我重新思考", "我应该", "我需要调整"]
        for keyword in adapt_keywords:
            if keyword in answer:
                signals.append(f"调节信号: {keyword}")
        
        # 规划信号
        plan_keywords = ["我的计划是", "我应该先", "第一步", "然后"]
        for keyword in plan_keywords:
            if keyword in answer:
                signals.append(f"规划信号: {keyword}")
        
        # 评估信号
        evaluate_keywords = ["我觉得", "我认为", "从...角度来看", "反思"]
        for keyword in evaluate_keywords:
            if keyword in answer:
                signals.append(f"评估信号: {keyword}")
        
        return signals
    
    def _format_history(self, conversation_history: List[Dict[str, Any]]) -> str:
        """格式化对话历史"""
        if not conversation_history:
            return "暂无对话历史"
        
        parts = []
        for i, turn in enumerate(conversation_history[-3:], 1):  # 只取最近3轮
            q = turn.get("question", "")
            a = turn.get("answer", "")
            parts.append(f"第{i}轮:\nQ: {q}\nA: {a}")
        
        return "\n\n".join(parts)

