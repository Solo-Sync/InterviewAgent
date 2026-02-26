"""评分结果聚合器"""

import numpy as np
from typing import List, Dict, Optional
from collections import defaultdict
import logging
from .models import ScoreResult, AggregatedResult

try:
    from difflib import SequenceMatcher
except ImportError:
    SequenceMatcher = None

logger = logging.getLogger(__name__)


class Aggregator:
    """负责对多个 ScoreResult 进行聚合"""

    def __init__(
        self,
        dimension_agg: str = 'median',          # 维度分数聚合方法：median 或 mean
        confidence_agg: str = 'median',         # 置信度聚合方法：median, mean
        deduction_deduplication: str = 'exact',  # 扣分项去重：exact, fuzzy
        disagreement_metric: str = 'iqr',        # 分歧度指标：iqr, std, range
        alert_config: Optional[Dict] = None      # 报警配置
    ):
        self.dimension_agg = dimension_agg
        self.confidence_agg = confidence_agg
        self.deduction_deduplication = deduction_deduplication
        self.disagreement_metric = disagreement_metric
        self.alert_config = alert_config or {
            'dimension_iqr_threshold': 1.0,      # 单个维度 IQR > 1 报警
            'global_iqr_threshold': 0.8,         # 平均 IQR > 0.8 报警
            'min_confidence': 0.6,                # 置信度中位数 < 0.6 报警
        }

    def aggregate(self, results: List[ScoreResult]) -> AggregatedResult:
        if not results:
            raise ValueError("结果列表不能为空")

        # 1. 维度分数聚合
        dim_values = defaultdict(list)
        for r in results:
            for dim, score in r.dimensions.items():
                dim_values[dim].append(score)

        final_dims = {}
        for dim, values in dim_values.items():
            if self.dimension_agg == 'median':
                final_dims[dim] = np.median(values)
            elif self.dimension_agg == 'mean':
                final_dims[dim] = np.mean(values)
            else:
                final_dims[dim] = np.median(values)  # 默认

        # 2. 置信度聚合
        confidences = []
        for r in results:
            if isinstance(r.confidence, dict):
                # 简单取各维度平均作为该模型的整体置信度
                conf = np.mean(list(r.confidence.values()))
            else:
                conf = r.confidence
            confidences.append(conf)

        if self.confidence_agg == 'median':
            final_confidence = np.median(confidences)
        elif self.confidence_agg == 'mean':
            final_confidence = np.mean(confidences)
        else:
            final_confidence = np.median(confidences)

        # 3. 扣分项去重
        all_deductions = []
        for r in results:
            all_deductions.extend(r.deductions)

        if self.deduction_deduplication == 'exact':
            # 精确去重（大小写敏感）
            seen = set()
            unique = []
            for d in all_deductions:
                if d not in seen:
                    seen.add(d)
                    unique.append(d)
            final_deductions = unique
        elif self.deduction_deduplication == 'fuzzy' and SequenceMatcher:
            # 简单模糊去重：如果相似度大于阈值则合并
            threshold = 0.8
            unique = []
            for d in all_deductions:
                if not any(SequenceMatcher(None, d, existing).ratio() > threshold for existing in unique):
                    unique.append(d)
            final_deductions = unique
        else:
            final_deductions = all_deductions  # 不去重

        # 4. 分歧度计算
        disagreement = {}
        iqr_list = []
        for dim, values in dim_values.items():
            if self.disagreement_metric == 'iqr':
                q75, q25 = np.percentile(values, [75, 25])
                iqr = q75 - q25
                disagreement[dim] = iqr
                iqr_list.append(iqr)
            elif self.disagreement_metric == 'std':
                std = np.std(values)
                disagreement[dim] = std
                iqr_list.append(std)
            elif self.disagreement_metric == 'range':
                rng = max(values) - min(values)
                disagreement[dim] = rng
                iqr_list.append(rng)
        global_disagreement = np.mean(iqr_list)

        # 5. 报警判断
        alert = False
        alert_reasons = []

        for dim, iqr in disagreement.items():
            if iqr > self.alert_config.get('dimension_iqr_threshold', 1.0):
                alert = True
                alert_reasons.append(f"维度 {dim} 分歧度(IQR={iqr:.2f}) 超过阈值")

        if global_disagreement > self.alert_config.get('global_iqr_threshold', 0.8):
            alert = True
            alert_reasons.append(f"全局平均分歧度({global_disagreement:.2f}) 超过阈值")

        if final_confidence < self.alert_config.get('min_confidence', 0.6):
            alert = True
            alert_reasons.append(f"聚合置信度({final_confidence:.2f}) 低于阈值")

        return AggregatedResult(
            dimensions=final_dims,
            confidence=final_confidence,
            deductions=final_deductions,
            disagreement=disagreement,
            global_disagreement=global_disagreement,
            alert=alert,
            alert_reasons=alert_reasons,
            raw_results=results
        )