from abc import ABC, abstractmethod
from .models import ScoreResult  # 避免循环导入，因为 models 不依赖 interfaces


class LLMInterface(ABC):
    """所有评分模型必须实现的接口"""

    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> ScoreResult:
        """
        调用模型，传入 prompt，返回 ScoreResult
        """
        pass