from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union


@dataclass
class ScoreResult:
    """单个模型（或单次采样）的评分结果"""
    dimensions: Dict[str, int]          # 四维分数，键为 'planning','monitoring','evaluation','transfer'
    confidence: Union[float, Dict[str, float]] = 0.0   # 可以是整体置信度或各维度置信度
    deductions: List[str] = field(default_factory=list)  # 扣分项列表
    model_name: str = ""                 # 模型标识
    raw_response: Optional[str] = None    # 原始返回，用于调试


@dataclass
class AggregatedResult:
    """聚合后的最终结果"""
    dimensions: Dict[str, float]          # 聚合后的维度分数（可为小数，最终四舍五入取整）
    confidence: Union[float, Dict[str, float]]  # 聚合置信度
    deductions: List[str]                  # 去重后的扣分项
    disagreement: Dict[str, float]          # 每个维度的分歧度（IQR 或标准差）
    global_disagreement: float              # 全局分歧度（如平均 IQR）
    alert: bool                             # 是否触发报警
    alert_reasons: List[str] = field(default_factory=list)  # 报警原因
    raw_results: List[ScoreResult] = field(default_factory=list)  # 保留原始结果供分析
