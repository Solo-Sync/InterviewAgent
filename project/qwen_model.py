from dotenv import load_dotenv
load_dotenv()   # 这会将 .env 文件中的变量加载到环境变量中

import os
import abc
import logging
from typing import Any, Dict, Optional

# 尝试导入 dashscope SDK
try:
    import dashscope
except ImportError:
    raise ImportError("请安装 dashscope 库：pip install dashscope>=1.0.0")

# 配置日志（可选）
logger = logging.getLogger(__name__)


class ModelAPIError(Exception):
    """模型 API 调用异常"""
    pass


class BaseModel(abc.ABC):
    """所有模型必须实现的抽象基类"""

    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        :param prompt: 输入提示
        :param kwargs: 其他模型特定参数
        :return: 生成的文本
        """
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """返回模型名称"""
        pass


class QwenModel(BaseModel):
    """阿里云通义千问模型封装"""

    def __init__(
        self,
        model: str = "qwen-turbo",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        **kwargs
    ):
        """
        初始化 Qwen 模型实例

        :param model: 模型名称，如 'qwen-turbo', 'qwen-plus' 等
        :param api_key: DashScope API Key，如未提供则从环境变量 DASHSCOPE_API_KEY 读取
        :param temperature: 采样温度，范围 [0, 2]，默认 0.0
        :param kwargs: 其他传递给 dashscope.Generation.call 的额外参数
        """
        self.model = model
        self.temperature = temperature
        self.extra_kwargs = kwargs

        # 校验 temperature 范围
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature 必须在 0 到 2 之间")

        # 获取 API Key
        if api_key is None:
            api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("必须提供 DashScope API Key，可通过参数 api_key 或环境变量 DASHSCOPE_API_KEY 设置")
        self.api_key = api_key

    def generate(
        self,
        prompt: str,
        strip: bool = False,
        **kwargs
    ) -> str:
        """
        调用 Qwen 生成文本

        :param prompt: 输入提示
        :param strip: 是否移除返回文本的首尾空白字符，默认 False
        :param kwargs: 调用时临时指定的参数，将覆盖初始化时传入的同名参数
        :return: 生成的文本
        :raises ModelAPIError: API 调用失败时抛出
        """
        # 合并参数：初始化时的 extra_kwargs 为基础，kwargs 覆盖
        params = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            **self.extra_kwargs,
            **kwargs
        }

        # 保存当前全局 API Key，并临时设置实例的 Key
        original_key = getattr(dashscope, "api_key", None)
        dashscope.api_key = self.api_key

        try:
            logger.debug(f"调用 Qwen 模型，参数: {params}")
            response = dashscope.Generation.call(**params)
        except Exception as e:
            # 捕获网络异常、SDK 内部异常等
            raise ModelAPIError(f"API 调用过程中发生异常: {e}") from e
        finally:
            # 恢复全局 API Key
            dashscope.api_key = original_key

        if response.status_code != 200:
            error_msg = f"API 调用失败 (HTTP {response.status_code}): {response.message}"
            logger.error(error_msg)
            raise ModelAPIError(error_msg)

        text = response.output.text
        if strip:
            text = text.strip()
        return text

    @property
    def model_name(self) -> str:
        return self.model