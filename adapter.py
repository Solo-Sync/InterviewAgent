"""
asr/adapter.py - OpenAPI 适配层
将 ASR 分析结果转换为 InterviewAgent 主系统可消费的格式
"""

import logging
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from .config import ASRConfig
from .engine import FunASREngine, ASRError, ASRErrorCode
from .analyzer import SpeechAnalyzer
from .models import TranscriptionResult, SpeechAnalysisResult

logger = logging.getLogger(__name__)


class AnalysisStatus(Enum):
    """分析状态"""
    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功（如转录成功但分析失败）
    FAILED = "failed"


@dataclass
class ScaffoldTrigger:
    """脚手架触发建议"""
    trigger_type: str          # 触发类型
    confidence: float          # 置信度 0-1
    reason: str               # 触发原因
    suggested_action: str     # 建议动作
    priority: int = 1         # 优先级 1-5, 5最高


@dataclass 
class AnalysisError:
    """分析错误信息"""
    code: str                 # 错误码
    message: str              # 错误信息
    recoverable: bool         # 是否可恢复
    suggestion: str           # 建议操作


@dataclass
class SpeechAnalysisResponse:
    """
    语音分析 API 响应
    与 InterviewAgent 主系统对接的标准格式
    """
    status: AnalysisStatus
    
    # 转录结果
    transcript: str = ""
    language: str = ""
    duration: float = 0.0
    
    # 流利度指标
    fluency_score: float = 0.0
    speech_rate: float = 0.0          # 字/分钟
    pause_ratio: float = 0.0          # 停顿占比
    filler_ratio: float = 0.0         # 填充词占比
    
    # 认知负荷指标
    cognitive_load_level: str = ""    # low/medium/high
    cognitive_load_score: float = 0.0
    hesitation_density: float = 0.0
    
    # 脚手架触发建议
    scaffold_triggers: list[ScaffoldTrigger] = field(default_factory=list)
    
    # 详细数据（可选，用于调试）
    details: Optional[dict] = None
    
    # 错误信息（失败时填充）
    error: Optional[AnalysisError] = None
    
    def to_dict(self) -> dict:
        """转换为字典，用于 JSON 序列化"""
        result = asdict(self)
        result["status"] = self.status.value
        if self.error:
            result["error"]["code"] = self.error.code
        result["scaffold_triggers"] = [
            {**asdict(t)} for t in self.scaffold_triggers
        ]
        return result


class ApiAdapter:
    """
    API 适配器
    整合 ASR 引擎和分析器，提供统一的对外接口
    """
    
    def __init__(self, config: Optional[ASRConfig] = None):
        self.config = config or ASRConfig()
        self._engine: Optional[FunASREngine] = None
        self._analyzer: Optional[SpeechAnalyzer] = None
        self._initialized = False
        self._init_error: Optional[ASRError] = None
    
    def initialize(self) -> None:
        """
        初始化引擎和分析器
        
        Raises:
            ASRError: 初始化失败时抛出
        """
        if self._initialized:
            return
            
        try:
            self._engine = FunASREngine(self.config)
            self._engine.load_model()
            self._analyzer = SpeechAnalyzer(self.config)
            self._initialized = True
            self._init_error = None
            logger.info("ApiAdapter initialized successfully")
        except ASRError as e:
            self._init_error = e
            logger.error(f"ApiAdapter initialization failed: {e}")
            raise
        except Exception as e:
            self._init_error = ASRError(
                ASRErrorCode.MODEL_NOT_LOADED,
                f"Unexpected initialization error: {str(e)}",
                cause=e
            )
            logger.error(f"ApiAdapter initialization failed: {e}")
            raise self._init_error
    
    @property
    def is_ready(self) -> bool:
        """检查适配器是否就绪"""
        return (
            self._initialized 
            and self._engine is not None 
            and self._engine.is_ready
        )
    
    def analyze(
        self,
        audio_input,
        language: Optional[str] = None,
        include_details: bool = False
    ) -> SpeechAnalysisResponse:
        """
        执行完整的语音分析
        
        Args:
            audio_input: 音频文件路径或音频数据
            language: 语言代码
            include_details: 是否包含详细数据
            
        Returns:
            SpeechAnalysisResponse: 始终返回响应对象，通过 status 判断成功/失败
        """
        # 检查初始化状态
        if not self.is_ready:
            return self._create_error_response(
                ASRErrorCode.MODEL_NOT_LOADED,
                "API not initialized. Call initialize() first.",
                recoverable=True,
                suggestion="Ensure initialize() is called before analyze()"
            )
        
        # Step 1: 语音识别
        transcription, asr_error = self._engine.transcribe_safe(audio_input, language)
        
        if asr_error:
            return self._create_error_response(
                asr_error.code,
                asr_error.message,
                recoverable=self._is_recoverable(asr_error.code),
                suggestion=self._get_suggestion(asr_error.code)
            )
        
        # Step 2: 语音分析
        try:
            analysis = self._analyzer.analyze(transcription)
            return self._build_success_response(transcription, analysis, include_details)
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            # 转录成功但分析失败，返回部分结果
            return self._build_partial_response(transcription, str(e))
    
    def analyze_or_raise(
        self,
        audio_input,
        language: Optional[str] = None,
        include_details: bool = False
    ) -> SpeechAnalysisResponse:
        """
        执行分析，失败时抛出异常
        适合需要严格错误处理的场景
        
        Raises:
            ASRError: 分析失败时抛出
        """
        if not self.is_ready:
            raise ASRError(
                ASRErrorCode.MODEL_NOT_LOADED,
                "API not initialized. Call initialize() first.",
                cause=self._init_error
            )
        
        transcription = self._engine.transcribe(audio_input, language)
        analysis = self._analyzer.analyze(transcription)
        return self._build_success_response(transcription, analysis, include_details)
    
    def _build_success_response(
        self,
        transcription: TranscriptionResult,
        analysis: SpeechAnalysisResult,
        include_details: bool
    ) -> SpeechAnalysisResponse:
        """构建成功响应"""
        triggers = self._generate_scaffold_triggers(analysis)
        
        response = SpeechAnalysisResponse(
            status=AnalysisStatus.SUCCESS,
            transcript=transcription.text,
            language=transcription.language,
            duration=transcription.duration,
            fluency_score=analysis.fluency.overall_score,
            speech_rate=analysis.fluency.speech_rate,
            pause_ratio=analysis.fluency.pause_ratio,
            filler_ratio=analysis.fluency.filler_ratio,
            cognitive_load_level=analysis.cognitive.load_level,
            cognitive_load_score=analysis.cognitive.composite_score,
            hesitation_density=analysis.cognitive.hesitation_density,
            scaffold_triggers=triggers,
        )
        
        if include_details:
            response.details = {
                "acoustic_features": asdict(analysis.acoustic),
                "fluency_metrics": asdict(analysis.fluency),
                "cognitive_metrics": asdict(analysis.cognitive),
                "word_count": len(transcription.words),
                "raw_transcript": transcription.raw_result,
            }
        
        return response
    
    def _build_partial_response(
        self,
        transcription: TranscriptionResult,
        error_message: str
    ) -> SpeechAnalysisResponse:
        """构建部分成功响应（转录成功，分析失败）"""
        return SpeechAnalysisResponse(
            status=AnalysisStatus.PARTIAL,
            transcript=transcription.text,
            language=transcription.language,
            duration=transcription.duration,
            error=AnalysisError(
                code="ANALYSIS_FAILED",
                message=f"Transcription succeeded but analysis failed: {error_message}",
                recoverable=True,
                suggestion="Transcript is available, but metrics are unavailable"
            )
        )
    
    def _create_error_response(
        self,
        code: ASRErrorCode,
        message: str,
        recoverable: bool,
        suggestion: str
    ) -> SpeechAnalysisResponse:
        """构建错误响应"""
        return SpeechAnalysisResponse(
            status=AnalysisStatus.FAILED,
            error=AnalysisError(
                code=code.value,
                message=message,
                recoverable=recoverable,
                suggestion=suggestion
            )
        )
    
    def _is_recoverable(self, code: ASRErrorCode) -> bool:
        """判断错误是否可恢复"""
        recoverable_codes = {
            ASRErrorCode.INVALID_INPUT,
            ASRErrorCode.FILE_NOT_FOUND,
        }
        return code in recoverable_codes
    
    def _get_suggestion(self, code: ASRErrorCode) -> str:
        """获取错误处理建议"""
        suggestions = {
            ASRErrorCode.MODEL_NOT_LOADED: "Check model installation and call initialize()",
            ASRErrorCode.INFERENCE_FAILED: "Retry with a different audio file or check audio format",
            ASRErrorCode.INVALID_INPUT: "Provide a valid audio file or non-empty audio data",
            ASRErrorCode.FILE_NOT_FOUND: "Check the file path exists and is accessible",
        }
        return suggestions.get(code, "Contact support if the issue persists")
    
    def _generate_scaffold_triggers(
        self,
        analysis: SpeechAnalysisResult
    ) -> list[ScaffoldTrigger]:
        """根据分析结果生成脚手架触发建议"""
        triggers = []
        
        # 高认知负荷触发
        if analysis.cognitive.load_level == "high":
            triggers.append(ScaffoldTrigger(
                trigger_type="cognitive_overload",
                confidence=min(analysis.cognitive.composite_score / 100, 1.0),
                reason=f"高认知负荷 (得分: {analysis.cognitive.composite_score:.1f})",
                suggested_action="simplify_question",
                priority=5
            ))
        
        # 频繁停顿触发
        if analysis.fluency.pause_ratio > 0.3:
            triggers.append(ScaffoldTrigger(
                trigger_type="frequent_pauses",
                confidence=min(analysis.fluency.pause_ratio / 0.5, 1.0),
                reason=f"停顿比例过高 ({analysis.fluency.pause_ratio:.1%})",
                suggested_action="provide_hint",
                priority=4
            ))
        
        # 填充词过多触发
        if analysis.fluency.filler_ratio > 0.1:
            triggers.append(ScaffoldTrigger(
                trigger_type="excessive_fillers",
                confidence=min(analysis.fluency.filler_ratio / 0.2, 1.0),
                reason=f"填充词比例过高 ({analysis.fluency.filler_ratio:.1%})",
                suggested_action="encourage_pause",
                priority=3
            ))
        
        # 语速异常触发
        if analysis.fluency.speech_rate < 100:
            triggers.append(ScaffoldTrigger(
                trigger_type="slow_speech",
                confidence=0.7,
                reason=f"语速过慢 ({analysis.fluency.speech_rate:.0f} 字/分钟)",
                suggested_action="check_understanding",
                priority=3
            ))
        elif analysis.fluency.speech_rate > 300:
            triggers.append(ScaffoldTrigger(
                trigger_type="fast_speech",
                confidence=0.7,
                reason=f"语速过快 ({analysis.fluency.speech_rate:.0f} 字/分钟)",
                suggested_action="slow_down_prompt",
                priority=2
            ))
        
        # 整体流利度低触发
        if analysis.fluency.overall_score < 60:
            triggers.append(ScaffoldTrigger(
                trigger_type="low_fluency",
                confidence=1 - (analysis.fluency.overall_score / 100),
                reason=f"整体流利度较低 (得分: {analysis.fluency.overall_score:.1f})",
                suggested_action="offer_break",
                priority=4
            ))
        
        # 按优先级排序
        triggers.sort(key=lambda t: t.priority, reverse=True)
        
        return triggers
    
    def health_check(self) -> dict:
        """健康检查"""
        engine_health = self._engine.health_check() if self._engine else {"ready": False}
        
        return {
            "adapter_ready": self.is_ready,
            "initialized": self._initialized,
            "engine": engine_health,
            "last_init_error": str(self._init_error) if self._init_error else None
        }