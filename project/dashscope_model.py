"""DashScope 模型实现示例"""

import json
import logging
from dashscope import Generation  # 需安装 dashscope 库
from scoring_engine.interfaces import LLMInterface
from scoring_engine.models import ScoreResult

logger = logging.getLogger(__name__)


class DashScopeLLM(LLMInterface):
    def __init__(
        self,
        model_name: str,
        api_key: str = None,
        temperature: float = 0.7,
        top_p: float = 0.9
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.top_p = top_p
        if api_key:
            import dashscope
            dashscope.api_key = api_key

    def invoke(self, prompt: str, **kwargs) -> ScoreResult:
        """实际调用 DashScope，需要根据返回解析出分数和扣分项"""
        params = {
            'model': self.model_name,
            'prompt': prompt,
            'temperature': kwargs.get('temperature', self.temperature),
            'top_p': kwargs.get('top_p', self.top_p),
        }
        response = Generation.call(**params)
        if response.status_code != 200:
            logger.error(f"DashScope 调用失败: {response}")
            return ScoreResult(
                dimensions={'planning': 0, 'monitoring': 0, 'evaluation': 0, 'transfer': 0},
                confidence=0.0,
                deductions=["模型调用失败"],
                model_name=self.model_name,
                raw_response=str(response)
            )
        text = response.output.text
        parsed = self._parse_response(text)
        return ScoreResult(
            dimensions=parsed.get('dimensions', {'planning': 0, 'monitoring': 0, 'evaluation': 0, 'transfer': 0}),
            confidence=parsed.get('confidence', 0.5),
            deductions=parsed.get('deductions', []),
            model_name=self.model_name,
            raw_response=text
        )

    def _parse_response(self, text: str) -> dict:
        """
        解析模型输出，假设输出是 JSON 格式，例如：
        {
            "dimensions": {"planning": 2, "monitoring": 1, "evaluation": 2, "transfer": 1},
            "confidence": 0.8,
            "deductions": ["缺少备选方案", "未检查计算结果"]
        }
        """
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                dims = data.get('dimensions', {})
                required = ['planning', 'monitoring', 'evaluation', 'transfer']
                for d in required:
                    if d not in dims:
                        dims[d] = 0
                return {
                    'dimensions': dims,
                    'confidence': data.get('confidence', 0.5),
                    'deductions': data.get('deductions', [])
                }
        except Exception:
            pass
        return {
            'dimensions': {'planning': 0, 'monitoring': 0, 'evaluation': 0, 'transfer': 0},
            'confidence': 0.0,
            'deductions': []
        }