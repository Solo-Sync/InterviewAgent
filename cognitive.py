"""认知负荷分析器"""
import numpy as np
from typing import List, Dict, Optional

from .models import FeatureStream, CognitiveLoadSignal
from .config import (
    COGNITIVE_WEIGHTS, 
    SCAFFOLD_THRESHOLDS,
    COGNITIVE_WINDOW,
    COGNITIVE_STEP
)


class CognitiveLoadAnalyzer:
    """认知负荷分析器"""
    
    def analyze(
        self, 
        feature_stream: FeatureStream,
        word_timestamps: List[Dict],
        total_duration: float
    ) -> List[CognitiveLoadSignal]:
        """分析认知负荷信号"""
        signals = []
        
        current_time = 0.0
        
        while current_time < total_duration:
            window_end = min(current_time + COGNITIVE_WINDOW, total_duration)
            
            indicators = self._calculate_indicators(
                feature_stream,
                word_timestamps,
                current_time,
                window_end
            )
            
            load_score = self._calculate_load_score(indicators)
            load_level = self._classify_load_level(load_score)
            trigger_scaffold = load_score >= SCAFFOLD_THRESHOLDS['medium']
            intervention = self._generate_intervention(load_level, indicators)
            
            signals.append(CognitiveLoadSignal(
                timestamp=current_time,
                load_level=load_level,
                load_score=load_score,
                indicators=indicators,
                trigger_scaffold=trigger_scaffold,
                suggested_intervention=intervention
            ))
            
            current_time += COGNITIVE_STEP
        
        return signals
    
    def _calculate_indicators(
        self,
        feature_stream: FeatureStream,
        word_timestamps: List[Dict],
        start_time: float,
        end_time: float
    ) -> Dict[str, float]:
        """计算时间窗口内的各项指标"""
        window_duration = end_time - start_time
        
        # 停顿频率
        pauses_in_window = [
            p for p in feature_stream.pauses
            if start_time <= p.start_time < end_time
        ]
        pause_frequency = len(pauses_in_window) / (window_duration / 60) if window_duration > 0 else 0
        pause_frequency_norm = min(pause_frequency / 15, 1.0)
        
        # 长停顿比例
        long_pauses = [p for p in pauses_in_window if p.pause_type == 'long']
        long_pause_ratio = len(long_pauses) / len(pauses_in_window) if pauses_in_window else 0
        
        # 填充词频率
        fillers_in_window = [
            f for f in feature_stream.fillers
            if start_time <= f.start_time < end_time
        ]
        filler_frequency = len(fillers_in_window) / (window_duration / 60) if window_duration > 0 else 0
        filler_frequency_norm = min(filler_frequency / 10, 1.0)
        
        # 语速变化
        rates_in_window = [
            r for r in feature_stream.speech_rate_timeline
            if start_time <= r['time_start'] < end_time
        ]
        if rates_in_window:
            rate_values = [r['chars_per_minute'] for r in rates_in_window]
            mean_rate = np.mean(rate_values)
            rate_variance = np.std(rate_values) / (mean_rate + 1e-6)
            rate_variance_norm = min(rate_variance / 0.5, 1.0)
        else:
            rate_variance_norm = 0.0
        
        # 犹豫密度
        hesitation_fillers = [
            f for f in fillers_in_window 
            if f.filler_type == 'hesitation'
        ]
        hesitation_density = len(hesitation_fillers) / len(fillers_in_window) if fillers_in_window else 0
        
        # 静音比例（基于VAD）
        speech_time = 0.0
        for seg in feature_stream.vad_segments:
            seg_start = max(seg['start'], start_time)
            seg_end = min(seg['end'], end_time)
            if seg_end > seg_start:
                speech_time += seg_end - seg_start
        
        silence_ratio = 1 - (speech_time / window_duration) if window_duration > 0 else 0
        
        return {
            'pause_frequency': pause_frequency_norm,
            'long_pause_ratio': long_pause_ratio,
            'filler_frequency': filler_frequency_norm,
            'speech_rate_variance': rate_variance_norm,
            'hesitation_density': hesitation_density,
            'silence_ratio': silence_ratio
        }
    
    def _calculate_load_score(self, indicators: Dict[str, float]) -> float:
        """计算认知负荷得分"""
        score = sum(
            COGNITIVE_WEIGHTS.get(k, 0) * v 
            for k, v in indicators.items()
        )
        return min(max(score, 0.0), 1.0)
    
    def _classify_load_level(self, score: float) -> str:
        """分类负荷等级"""
        if score < SCAFFOLD_THRESHOLDS['low']:
            return 'low'
        elif score < SCAFFOLD_THRESHOLDS['high']:
            return 'medium'
        else:
            return 'high'
    
    def _generate_intervention(
        self, 
        load_level: str, 
        indicators: Dict[str, float]
    ) -> Optional[str]:
        """生成干预建议"""
        if load_level == 'low':
            return None
        
        max_indicator = max(indicators.items(), key=lambda x: x[1])
        
        interventions = {
            'pause_frequency': "学习者频繁停顿，可能在组织语言，建议提供结构化提示",
            'long_pause_ratio': "出现长时间停顿，学习者可能遇到困难，建议分解问题",
            'filler_frequency': "填充词较多，学习者可能不确定，可以提供确认或示例",
            'speech_rate_variance': "语速变化大，思维可能不稳定，建议稳定引导",
            'hesitation_density': "犹豫明显，可能需要更多背景知识支持",
            'silence_ratio': "静音时间长，学习者可能需要更多思考时间或提示"
        }
        
        return interventions.get(max_indicator[0], "建议提供适当支持")