"""数据结构定义"""
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class WordSegment:
    """词级别分段"""
    word: str
    start_time: float  # 秒
    end_time: float
    confidence: float = 1.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class PauseEvent:
    """停顿事件"""
    start_time: float
    end_time: float
    pause_type: str  # 'short', 'medium', 'long'
    preceding_word: Optional[str] = None
    following_word: Optional[str] = None
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class FillerEvent:
    """填充词/语气词事件"""
    word: str
    start_time: float
    end_time: float
    filler_type: str  # 'hesitation', 'thinking', 'confirmation', 'uncertainty'


@dataclass
class SemanticStream:
    """语义流"""
    full_text: str
    segments: List[WordSegment]
    sentences: List[Dict]
    language: str = "zh"


@dataclass
class FeatureStream:
    """特征流"""
    pauses: List[PauseEvent]
    fillers: List[FillerEvent]
    speech_rate_timeline: List[Dict]
    energy_timeline: List[Dict]
    vad_segments: List[Dict]


@dataclass
class CognitiveLoadSignal:
    """认知负荷信号"""
    timestamp: float
    load_level: str  # 'low', 'medium', 'high'
    load_score: float  # 0.0 - 1.0
    indicators: Dict[str, float]
    trigger_scaffold: bool
    suggested_intervention: Optional[str] = None


@dataclass
class AnalysisResult:
    """完整分析结果"""
    semantic_stream: SemanticStream
    feature_stream: FeatureStream
    cognitive_signals: List[CognitiveLoadSignal]
    summary_metrics: Dict
    scaffold_recommendations: List[Dict]