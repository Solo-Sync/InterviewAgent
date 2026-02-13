"""
提问模块
负责从题库读取问题、生成初始问题、追问和扰动注入
"""
import os
import json
import random
from typing import List, Dict, Any, Optional
from pathlib import Path
from langchain_community.chat_models import ChatTongyi  # type: ignore[import]
from langchain_core.messages import HumanMessage, SystemMessage
from src.models import QuestionRef


class QuestionModule:
    """提问模块"""
    
    def __init__(self, question_bank_path: str = "question_bank.json", llm=None):
        """
        初始化提问模块
        
        Args:
            question_bank_path: 题库文件路径
            llm: LLM实例(ChatTongyi或其他), 如果为None则自动创建
        """
        self.question_bank_path = Path(question_bank_path)
        
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
        
        self.question_bank: List[Dict[str, Any]] = []
        self.current_question: Optional[Dict[str, Any]] = None
        self._load_question_bank()
    
    def _load_question_bank(self):
        """加载题库"""
        if not self.question_bank_path.exists():
            raise FileNotFoundError(f"题库文件不存在: {self.question_bank_path}")
        
        with open(self.question_bank_path, 'r', encoding='utf-8') as f:
            self.question_bank = json.load(f)
    
    def get_initial_question(self) -> QuestionRef:
        """
        获取初始问题(随机选择)
        
        Returns:
            初始问题引用
        """
        if not self.question_bank:
            raise ValueError("题库为空")
        
        # 随机选择一个问题
        self.current_question = random.choice(self.question_bank)
        
        # 构建初始问题文本
        question_text = self._build_initial_question_text(self.current_question)
        
        return QuestionRef(
            qid=self.current_question.get("id"),
            text=question_text
        )
    
    def _build_initial_question_text(self, question: Dict[str, Any]) -> str:
        """
        构建初始问题文本
        
        Args:
            question: 问题字典
            
        Returns:
            完整的问题文本
        """
        text_parts = []
        
        # 添加标题
        if "title" in question:
            text_parts.append(f"题目: {question['title']}")
        
        # 添加场景描述
        if "scene" in question:
            text_parts.append(f"\n场景:\n{question['scene']}")
        
        # 如果有procedure,添加第一步
        if "procedure" in question and question["procedure"]:
            first_phase = question["procedure"][0]
            text_parts.append(f"\n{first_phase.get('instruction', '')}")
        
        # 如果有follow_up_design,添加第一步追问
        elif "follow_up_design" in question and question["follow_up_design"]:
            first_step = question["follow_up_design"][0]
            text_parts.append(f"\n{first_step.get('question', '')}")
        
        return "\n".join(text_parts)
    
    def generate_follow_up_question(
        self,
        student_answer: str,
        conversation_history: List[Dict[str, Any]],
        use_llm: bool = True
    ) -> QuestionRef:
        """
        生成追问问题
        优先使用LLM生成,如果LLM不可用则从题库中选择
        
        Args:
            student_answer: 学生的回答
            conversation_history: 对话历史
            use_llm: 是否使用LLM生成(默认True)
            
        Returns:
            追问问题引用
        """
        if not self.current_question:
            raise ValueError("当前没有活跃的问题")
        
        # 如果使用LLM且LLM客户端可用,使用LLM生成追问
        if use_llm and self.llm:
            return self._generate_llm_follow_up(student_answer, conversation_history)
        
        # 否则从题库中选择下一个追问
        return self._get_next_follow_up_from_bank()
    
    def _generate_llm_follow_up(
        self,
        student_answer: str,
        conversation_history: List[Dict[str, Any]]
    ) -> QuestionRef:
        """
        使用LLM生成追问
        
        Args:
            student_answer: 学生回答
            conversation_history: 对话历史
            
        Returns:
            追问问题引用
        """
        # 构建上下文
        context = self._build_conversation_context(conversation_history)
        
        # 构建提示
        system_prompt = """你是一位专业的面试官,擅长通过追问来评估学生的元认知能力。
你的追问应该:
1. 基于学生的回答,深入挖掘其思维过程
2. 适当施加认知压力,测试其监控和调节能力
3. 关注学生的规划、监控、评估、适应四个维度
4. 问题要具体、有针对性,避免泛泛而谈"""
        
        prompt = f"""当前问题: {self.current_question.get('title', '')}
场景: {self.current_question.get('scene', '')}

对话历史:
{context}

学生最新回答:
{student_answer}

请基于学生的回答,生成一个追问问题。追问应该:
- 针对学生回答中的关键点进行深入挖掘
- 可以适当施加认知压力(如提出反例、质疑假设等)
- 关注学生的元认知表现(是否意识到问题、是否调整策略等)
- 问题要自然、有针对性

只返回问题文本,不要添加其他说明。"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            follow_up_text = response.content
            
            return QuestionRef(
                qid=self.current_question.get("id"),
                text=follow_up_text.strip()
            )
        except Exception as e:
            # LLM失败时回退到题库
            print(f"LLM生成追问失败: {e}, 回退到题库")
            return self._get_next_follow_up_from_bank()
    
    def _get_next_follow_up_from_bank(self) -> QuestionRef:
        """
        从题库中获取下一个追问
        
        Returns:
            追问问题引用
        """
        if not self.current_question:
            raise ValueError("当前没有活跃的问题")
        
        # 从follow_up_design中选择下一个
        if "follow_up_design" in self.current_question:
            follow_ups = self.current_question["follow_up_design"]
            # 简单策略: 随机选择一个(实际应该根据已使用的追问来选择)
            if follow_ups:
                selected = random.choice(follow_ups)
                return QuestionRef(
                    qid=self.current_question.get("id"),
                    text=selected.get("question", "")
                )
        
        # 如果没有follow_up_design,生成一个通用追问
        return QuestionRef(
            qid=self.current_question.get("id"),
            text="请详细说明你的思考过程。"
        )
    
    def generate_probe_question(
        self,
        student_answer: str,
        conversation_history: List[Dict[str, Any]]
    ) -> QuestionRef:
        """
        生成认知压力问题(扰动注入)
        
        Args:
            student_answer: 学生回答
            conversation_history: 对话历史
            
        Returns:
            认知压力问题引用
        """
        if not self.llm:
            # 如果没有LLM,使用简单的模板
            return QuestionRef(
                qid=self.current_question.get("id") if self.current_question else None,
                text="如果情况发生变化,你会如何调整你的方案?"
            )
        
        context = self._build_conversation_context(conversation_history)
        
        system_prompt = """你是一位专业的面试官,擅长通过施加认知压力来测试学生的元认知能力。
你的问题应该:
1. 提出反例、质疑假设、引入新约束
2. 测试学生是否能够监控自己的思维,发现并修正错误
3. 观察学生是否能够灵活调整策略"""
        
        prompt = f"""当前问题: {self.current_question.get('title', '') if self.current_question else ''}

对话历史:
{context}

学生最新回答:
{student_answer}

请生成一个认知压力问题,通过以下方式之一施加压力:
- 提出反例或边界情况
- 质疑学生的假设
- 引入新的约束条件
- 要求学生在更复杂的情况下应用其方案

只返回问题文本。"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            probe_text = response.content

            return QuestionRef(
                qid=self.current_question.get("id") if self.current_question else None,
                text=probe_text.strip()
            )
        except Exception as e:
            print(f"生成认知压力问题失败: {e}")
            return QuestionRef(
                qid=self.current_question.get("id") if self.current_question else None,
                text="如果情况发生变化,你会如何调整你的方案?"
            )
    
    def _build_conversation_context(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        构建对话历史上下文
        
        Args:
            conversation_history: 对话历史
            
        Returns:
            格式化的对话历史文本
        """
        if not conversation_history:
            return "暂无对话历史"
        
        context_parts = []
        for i, turn in enumerate(conversation_history[-5:], 1):  # 只取最近5轮
            question = turn.get("question", "")
            answer = turn.get("answer", "")
            context_parts.append(f"第{i}轮:\n问题: {question}\n回答: {answer}")
        
        return "\n\n".join(context_parts)
    
    def reset_question(self):
        """重置当前问题"""
        self.current_question = None

