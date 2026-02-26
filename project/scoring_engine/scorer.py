"""评分执行器，协调多个模型调用并聚合结果"""

from typing import List, Optional, Dict, Any
import logging
from .interfaces import LLMInterface
from .aggregator import Aggregator
from .models import ScoreResult, AggregatedResult

logger = logging.getLogger(__name__)


class Scorer:
    """
    评分执行器，管理多个模型或采样，并执行聚合
    """

    def __init__(
        self,
        models: List[LLMInterface],
        aggregator: Aggregator,
        prompt_template: str = None
    ):
        """
        :param models: 模型实例列表（可包含同一模型不同参数以模拟多次采样）
        :param aggregator: 聚合器实例
        :param prompt_template: 可选的 prompt 模板，用于生成调用时的完整 prompt
        """
        self.models = models
        self.aggregator = aggregator
        self.prompt_template = prompt_template or (
            "请根据以下信息对回答进行四维能力评估（0-3分）：\n"
            "问题：{question}\n"
            "上下文：{context}\n"
            "考生回答：{answer}\n"
            "请以 JSON 格式输出，包含 dimensions 对象（planning, monitoring, evaluation, transfer），"
            "confidence（0-1），deductions（列表）。"
        )

    def score(
        self,
        answer: str,
        question: str = "",
        context: str = "",
        model_kwargs: Optional[List[Dict]] = None
    ) -> AggregatedResult:
        """
        执行评分流程
        :param answer: 考生回答
        :param question: 问题描述
        :param context: 上下文信息
        :param model_kwargs: 每个模型调用时的额外参数列表，长度应与 models 一致
        :return: 聚合结果
        """
        prompt = self.prompt_template.format(question=question, context=context, answer=answer)

        results = []
        for idx, model in enumerate(self.models):
            kwargs = model_kwargs[idx] if model_kwargs and idx < len(model_kwargs) else {}
            try:
                result = model.invoke(prompt, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"模型 {model} 调用失败: {e}")
                # 添加一个默认结果，防止整个流程崩溃
                results.append(ScoreResult(
                    dimensions={'planning': 0, 'monitoring': 0, 'evaluation': 0, 'transfer': 0},
                    confidence=0.0,
                    deductions=[f"调用异常: {str(e)}"],
                    model_name=getattr(model, 'model_name', 'unknown')
                ))

        # 聚合
        aggregated = self.aggregator.aggregate(results)
        return aggregated