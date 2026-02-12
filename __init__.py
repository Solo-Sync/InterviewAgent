"""
asr - 语音识别与分析模块
"""

from .config import ASRConfig
from .models import (
    WordInfo,
    TranscriptionResult,
    AcousticFeatures,
    FluencyMetrics,
    CognitiveMetrics,
    SpeechAnalysisResult,
)
from .engine import FunASREngine, ASRError, ASRErrorCode
from .features import AcousticFeatureExtractor
from .cognitive import CognitiveLoadAnalyzer
from .analyzer import SpeechAnalyzer
from .adapter import (
    ApiAdapter,
    SpeechAnalysisResponse,
    ScaffoldTrigger,
    AnalysisStatus,
    AnalysisError,
)

__version__ = "0.1.0"

__all__ = [
    # Config
    "ASRConfig",
    # Models
    "WordInfo",
    "TranscriptionResult",
    "AcousticFeatures",
    "FluencyMetrics",
    "CognitiveMetrics",
    "SpeechAnalysisResult",
    # Engine
    "FunASREngine",
    "ASRError",
    "ASRErrorCode",
    # Extractors
    "AcousticFeatureExtractor",
    "CognitiveLoadAnalyzer",
    # Analyzer
    "SpeechAnalyzer",
    # Adapter
    "ApiAdapter",
    "SpeechAnalysisResponse",
    "ScaffoldTrigger",
    "AnalysisStatus",
    "AnalysisError",
]