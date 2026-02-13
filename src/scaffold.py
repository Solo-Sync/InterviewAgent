"""
脚手架提示模块
根据学生卡顿情况提供不同级别的提示
"""
import os
from typing import Optional, Dict, Any
from langchain_community.chat_models import ChatTongyi  # type: ignore[import]
from langchain_core.messages import HumanMessage, SystemMessage
from src.models import ScaffoldResult, ScaffoldLevel, SessionState


class ScaffoldModule:
    """脚手架提示模块"""
    
    def __init__(self, llm=None):
        """
        初始化脚手架模块
        
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
    
    def generate_scaffold(
        self,
        level: ScaffoldLevel,
        question: str,
        student_answer: str,
        error_type: str,
        state: SessionState
    ) -> ScaffoldResult:
        """
        生成脚手架提示
        
        Args:
            level: 提示级别 (L1/L2/L3)
            question: 当前问题
            student_answer: 学生回答(可能为空或卡顿)
            error_type: 错误类型 (STUCK/OFFTRACK/LOOP/FACT_ERROR/HIGH_STRESS)
            state: 当前状态
            
        Returns:
            脚手架结果
        """
        print(f"\n[脚手架] 生成脚手架提示 - 级别: {level.value}, 错误类型: {error_type}")
        # 根据级别生成提示
        if level == ScaffoldLevel.L1:
            result = self._generate_l1(question, student_answer, error_type)
            print(f"[脚手架] 生成 L1 提示: {result.prompt[:100]}..." if result.prompt else "[脚手架] L1 未触发")
            return result
        elif level == ScaffoldLevel.L2:
            result = self._generate_l2(question, student_answer, error_type)
            print(f"[脚手架] 生成 L2 提示: {result.prompt[:100]}..." if result.prompt else "[脚手架] L2 未触发")
            return result
        elif level == ScaffoldLevel.L3:
            result = self._generate_l3(question, student_answer, error_type)
            print(f"[脚手架] 生成 L3 提示: {result.prompt[:100]}..." if result.prompt else "[脚手架] L3 未触发")
            return result
        else:
            return ScaffoldResult(fired=False)
    
    def _generate_l1(
        self,
        question: str,
        student_answer: str,
        error_type: str
    ) -> ScaffoldResult:
        """
        生成L1级别提示(温和提醒)
        
        Args:
            question: 当前问题
            student_answer: 学生回答
            error_type: 错误类型
            
        Returns:
            L1提示结果
        """
        if self.llm:
            try:
                system_prompt = """你是一位温和的面试官,当学生卡顿时给予鼓励性提示。
L1提示应该是温和的提醒,不直接给出答案,而是引导学生思考方向。"""
                
                prompt = f"""当前问题: {question}
学生回答: {student_answer if student_answer else "(学生沉默或卡顿)"}
错误类型: {error_type}

请生成一个温和的L1级别提示,鼓励学生继续思考。提示应该:
- 语气温和、鼓励
- 不直接给出答案
- 给出思考方向或提示
- 帮助学生重新聚焦问题

只返回提示文本。"""
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ]
                response = self.llm.invoke(messages)
                prompt_text = response.content
                
                return ScaffoldResult(
                    fired=True,
                    level=ScaffoldLevel.L1,
                    prompt=prompt_text.strip(),
                    rationale="L1: 温和提醒,引导学生思考"
                )
            except Exception as e:
                print(f"生成L1提示失败: {e}")
        
        # 默认L1提示
        default_prompts = {
            "STUCK": "没关系,慢慢来。你可以先思考一下问题的关键点是什么。",
            "OFFTRACK": "让我们回到问题的核心。这个问题主要想了解的是...",
            "LOOP": "看起来你在重复思考同一个点。也许可以换个角度考虑?",
            "FACT_ERROR": "这个细节可能需要再确认一下。",
            "HIGH_STRESS": "放轻松,这只是一个讨论。你可以慢慢说。"
        }
        
        return ScaffoldResult(
            fired=True,
            level=ScaffoldLevel.L1,
            prompt=default_prompts.get(error_type, "没关系,慢慢思考。"),
            rationale="L1: 温和提醒"
        )
    
    def _generate_l2(
        self,
        question: str,
        student_answer: str,
        error_type: str
    ) -> ScaffoldResult:
        """
        生成L2级别提示(具体方向)
        
        Args:
            question: 当前问题
            student_answer: 学生回答
            error_type: 错误类型
            
        Returns:
            L2提示结果
        """
        if self.llm:
            try:
                system_prompt = """你是一位专业的面试官,当学生持续卡顿时提供更具体的思考方向。
L2提示应该给出具体的思考方向或方法,但不直接给出答案。"""
                
                prompt = f"""当前问题: {question}
学生回答: {student_answer if student_answer else "(学生持续卡顿)"}
错误类型: {error_type}

请生成一个L2级别提示,提供具体的思考方向。提示应该:
- 给出具体的思考步骤或方法
- 指出可以关注的关键点
- 提供一些思考框架
- 仍然不直接给出答案

只返回提示文本。"""
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ]
                response = self.llm.invoke(messages)
                prompt_text = response.content
                
                return ScaffoldResult(
                    fired=True,
                    level=ScaffoldLevel.L2,
                    prompt=prompt_text.strip(),
                    rationale="L2: 提供具体思考方向"
                )
            except Exception as e:
                print(f"生成L2提示失败: {e}")
        
        # 默认L2提示
        default_prompts = {
            "STUCK": "你可以尝试这样思考: 1) 明确目标是什么 2) 分析有哪些关键因素 3) 考虑可能的方案",
            "OFFTRACK": "让我们聚焦到核心问题: [问题关键点]。你可以从这个角度思考。",
            "LOOP": "也许可以尝试: 1) 暂停当前思路 2) 从另一个维度分析 3) 考虑是否有遗漏的因素",
            "FACT_ERROR": "关于这个点,你可以考虑: [相关事实或方法]",
            "HIGH_STRESS": "让我们简化一下。你可以先回答核心部分,细节可以后续补充。"
        }
        
        return ScaffoldResult(
            fired=True,
            level=ScaffoldLevel.L2,
            prompt=default_prompts.get(error_type, "你可以尝试从以下几个角度思考: [具体方向]"),
            rationale="L2: 提供具体方向"
        )
    
    def _generate_l3(
        self,
        question: str,
        student_answer: str,
        error_type: str
    ) -> ScaffoldResult:
        """
        生成L3级别提示(直接答案/示例)
        
        Args:
            question: 当前问题
            student_answer: 学生回答
            error_type: 错误类型
            
        Returns:
            L3提示结果
        """
        if self.llm:
            try:
                system_prompt = """你是一位专业的面试官,当学生严重卡顿时提供直接帮助。
L3提示可以给出答案示例或直接提示,帮助学生理解问题。"""
                
                prompt = f"""当前问题: {question}
学生回答: {student_answer if student_answer else "(学生严重卡顿)"}
错误类型: {error_type}

请生成一个L3级别提示,提供直接的帮助。提示可以:
- 给出答案示例或思路
- 直接指出关键点
- 提供完整的思考框架
- 帮助学生理解问题本质

只返回提示文本。"""
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ]
                response = self.llm.invoke(messages)
                prompt_text = response.content
                
                return ScaffoldResult(
                    fired=True,
                    level=ScaffoldLevel.L3,
                    prompt=prompt_text.strip(),
                    rationale="L3: 提供直接帮助"
                )
            except Exception as e:
                print(f"生成L3提示失败: {e}")
        
        # 默认L3提示
        default_prompts = {
            "STUCK": "这个问题可以从以下角度思考: [具体思路]。例如: [示例]",
            "OFFTRACK": "问题的核心是: [核心点]。一个可能的思路是: [思路]",
            "LOOP": "让我们换个思路。一个常见的方法是: [方法], 例如: [示例]",
            "FACT_ERROR": "关于这一点,正确的理解是: [正确信息]",
            "HIGH_STRESS": "让我们简化回答。你可以这样说: [示例回答]"
        }
        
        return ScaffoldResult(
            fired=True,
            level=ScaffoldLevel.L3,
            prompt=default_prompts.get(error_type, "一个可能的思路是: [思路示例]"),
            rationale="L3: 提供直接帮助"
        )

