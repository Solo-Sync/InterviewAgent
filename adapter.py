"""API 适配器 - 将内部数据结构转换为 OpenAPI 规范格式"""
import re
from typing import List, Dict

from .models import FillerEvent, CognitiveLoadSignal, FeatureStream


class ApiAdapter:
    """将内部数据结构转换为 OpenAPI 规范格式"""
    
    @staticmethod
    def to_asr_result(transcribe_result: Dict) -> Dict:
        """转换为 API 的 AsrResult 格式"""
        tokens = []
        for w in transcribe_result.get('word_timestamps', []):
            tokens.append({
                'token': w['word'],
                'start_ms': int(w['start'] * 1000),
                'end_ms': int(w['end'] * 1000)
            })
        
        # VAD 间隙 = silence_segments
        silence_segments = []
        vad_segs = transcribe_result.get('vad_segments', [])
        for i in range(len(vad_segs) - 1):
            gap_start = vad_segs[i]['end']
            gap_end = vad_segs[i + 1]['start']
            if gap_end > gap_start:
                silence_segments.append({
                    'start_ms': int(gap_start * 1000),
                    'end_ms': int(gap_end * 1000)
                })
        
        return {
            'raw_text': transcribe_result.get('text', ''),
            'tokens': tokens,
            'silence_segments': silence_segments,
            'audio_features': None
        }
    
    @staticmethod
    def to_preprocess_result(
        clean_text: str, 
        fillers: List[FillerEvent]
    ) -> Dict:
        """转换为 API 的 PreprocessResult 格式"""
        # 统计各类填充词
        filler_stats = {}
        for f in fillers:
            filler_stats[f.filler_type] = filler_stats.get(f.filler_type, 0) + 1
        
        # 计算犹豫率
        total_fillers = len(fillers)
        hesitation_count = filler_stats.get('hesitation', 0)
        hesitation_rate = hesitation_count / total_fillers if total_fillers > 0 else 0.0
        
        return {
            'clean_text': clean_text,
            'filler_stats': filler_stats,
            'hesitation_rate': hesitation_rate
        }
    
    @staticmethod
    def to_triggers(
        cognitive_signals: List[CognitiveLoadSignal],
        feature_stream: FeatureStream
    ) -> List[Dict]:
        """将认知负荷信号转换为 API 的 Trigger 格式"""
        triggers = []
        
        for sig in cognitive_signals:
            if not sig.trigger_scaffold:
                continue
            
            max_indicator = max(sig.indicators.items(), key=lambda x: x[1])
            indicator_name, indicator_value = max_indicator
            
            trigger_type_map = {
                'pause_frequency': 'SILENCE',
                'long_pause_ratio': 'SILENCE',
                'silence_ratio': 'SILENCE',
                'filler_frequency': 'STRESS_SIGNAL',
                'hesitation_density': 'STRESS_SIGNAL',
                'speech_rate_variance': 'STRESS_SIGNAL',
            }
            
            trigger_type = trigger_type_map.get(indicator_name, 'STRESS_SIGNAL')
            
            triggers.append({
                'type': trigger_type,
                'score': float(sig.load_score),
                'detail': f"{indicator_name}={indicator_value:.2f} @ {sig.timestamp:.1f}s"
            })
        
        return triggers
    
    @staticmethod
    def to_audio_features(
        feature_stream: FeatureStream,
        summary_metrics: Dict
    ) -> Dict:
        """转换为 API 的 AudioFeatures 格式"""
        return {
            'pause_count': summary_metrics.get('pause_count', 0),
            'pause_total_duration_ms': int(summary_metrics.get('pause_total_duration', 0) * 1000),
            'long_pause_count': summary_metrics.get('long_pause_count', 0),
            'filler_count': summary_metrics.get('filler_count', 0),
            'filler_by_type': summary_metrics.get('filler_by_type', {}),
            'speech_rate_mean': summary_metrics.get('speech_rate_mean', 0),
            'speech_rate_std': summary_metrics.get('speech_rate_std', 0),
            'cognitive_load_mean': summary_metrics.get('cognitive_load_mean', 0),
            'cognitive_load_max': summary_metrics.get('cognitive_load_max', 0),
        }
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本中的特殊标记"""
        return re.sub(r'<\|[^|]+\|>', '', text).strip()