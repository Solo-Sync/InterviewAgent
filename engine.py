"""
asr/engine.py - FunASR 语音识别引擎
"""

import logging
from pathlib import Path
from typing import Union, Optional
from dataclasses import dataclass
from enum import Enum

from .config import ASRConfig
from .models import TranscriptionResult, WordInfo

logger = logging.getLogger(__name__)


class ASRErrorCode(Enum):
    """ASR 错误码"""
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"


class ASRError(Exception):
    """ASR 异常基类"""
    def __init__(self, code: ASRErrorCode, message: str, cause: Optional[Exception] = None):
        self.code = code
        self.message = message
        self.cause = cause
        super().__init__(f"[{code.value}] {message}")


class FunASREngine:
    """
    基于 FunASR 的语音识别引擎
    集成 SenseVoice + VAD + Punctuation
    """
    
    def __init__(self, config: Optional[ASRConfig] = None):
        self.config = config or ASRConfig()
        self._model = None
        self._model_loaded = False
        self._load_error: Optional[Exception] = None
    
    def load_model(self) -> None:
        """
        加载 ASR 模型
        
        Raises:
            ASRError: 模型加载失败时抛出
        """
        if self._model_loaded:
            return
            
        try:
            from funasr import AutoModel
            
            logger.info(f"Loading ASR model: {self.config.model_name}")
            
            self._model = AutoModel(
                model=self.config.model_name,
                vad_model=self.config.vad_model if self.config.enable_vad else None,
                punc_model=self.config.punc_model if self.config.enable_punc else None,
                device=self.config.device,
            )
            
            self._model_loaded = True
            self._load_error = None
            logger.info("ASR model loaded successfully")
            
        except ImportError as e:
            self._load_error = e
            logger.error(f"FunASR not installed: {e}")
            raise ASRError(
                ASRErrorCode.MODEL_NOT_LOADED,
                "FunASR library not installed. Run: pip install funasr",
                cause=e
            )
        except Exception as e:
            self._load_error = e
            logger.error(f"Failed to load ASR model: {e}")
            raise ASRError(
                ASRErrorCode.MODEL_NOT_LOADED,
                f"Failed to load model '{self.config.model_name}': {str(e)}",
                cause=e
            )
    
    @property
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._model_loaded and self._model is not None
    
    def transcribe(
        self,
        audio_input: Union[str, Path, bytes],
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        执行语音识别
        
        Args:
            audio_input: 音频文件路径或音频数据
            language: 语言代码 (如 "zh", "en")，None 表示自动检测
            
        Returns:
            TranscriptionResult: 识别结果
            
        Raises:
            ASRError: 模型未加载、输入无效或推理失败时抛出
        """
        # 检查模型状态
        if not self.is_ready:
            raise ASRError(
                ASRErrorCode.MODEL_NOT_LOADED,
                "ASR model not loaded. Call load_model() first.",
                cause=self._load_error
            )
        
        # 验证输入
        audio_path = self._validate_input(audio_input)
        
        # 执行推理
        try:
            result = self._model.generate(
                input=str(audio_path) if audio_path else audio_input,
                language=language or self.config.language,
                use_itn=True,
                batch_size_s=self.config.batch_size_s,
            )
            
            return self._parse_result(result)
            
        except Exception as e:
            logger.error(f"ASR inference failed: {e}")
            raise ASRError(
                ASRErrorCode.INFERENCE_FAILED,
                f"Speech recognition failed: {str(e)}",
                cause=e
            )
    
    def _validate_input(self, audio_input: Union[str, Path, bytes]) -> Optional[Path]:
        """
        验证输入参数
        
        Returns:
            Path if file input, None if bytes input
            
        Raises:
            ASRError: 输入无效时抛出
        """
        if isinstance(audio_input, bytes):
            if len(audio_input) == 0:
                raise ASRError(
                    ASRErrorCode.INVALID_INPUT,
                    "Empty audio data provided"
                )
            return None
            
        audio_path = Path(audio_input)
        if not audio_path.exists():
            raise ASRError(
                ASRErrorCode.FILE_NOT_FOUND,
                f"Audio file not found: {audio_path}"
            )
        
        if audio_path.stat().st_size == 0:
            raise ASRError(
                ASRErrorCode.INVALID_INPUT,
                f"Audio file is empty: {audio_path}"
            )
            
        return audio_path
    
    def _parse_result(self, raw_result: list) -> TranscriptionResult:
        """解析 FunASR 输出"""
        if not raw_result:
            return TranscriptionResult(
                text="",
                words=[],
                language="unknown",
                duration=0.0
            )
        
        item = raw_result[0]
        text = item.get("text", "")
        
        words = []
        if "timestamp" in item and "words" in item:
            timestamps = item["timestamp"]
            word_list = item["words"] if isinstance(item.get("words"), list) else text.split()
            
            for i, (word, ts) in enumerate(zip(word_list, timestamps)):
                if isinstance(ts, (list, tuple)) and len(ts) >= 2:
                    words.append(WordInfo(
                        word=word,
                        start_time=ts[0] / 1000.0,
                        end_time=ts[1] / 1000.0,
                        confidence=item.get("confidence", 0.9)
                    ))
        
        duration = 0.0
        if words:
            duration = words[-1].end_time
        
        return TranscriptionResult(
            text=text,
            words=words,
            language=item.get("language", self.config.language or "zh"),
            duration=duration,
            raw_result=item
        )
    
    def transcribe_safe(
        self,
        audio_input: Union[str, Path, bytes],
        language: Optional[str] = None
    ) -> tuple[Optional[TranscriptionResult], Optional[ASRError]]:
        """
        安全版本的 transcribe，返回 (result, error) 元组
        不抛异常，适合需要自行处理错误的场景
        
        Returns:
            (TranscriptionResult, None) 成功时
            (None, ASRError) 失败时
        """
        try:
            result = self.transcribe(audio_input, language)
            return result, None
        except ASRError as e:
            return None, e
        except Exception as e:
            error = ASRError(
                ASRErrorCode.INFERENCE_FAILED,
                f"Unexpected error: {str(e)}",
                cause=e
            )
            return None, error
    
    def health_check(self) -> dict:
        """
        健康检查，返回引擎状态
        """
        return {
            "ready": self.is_ready,
            "model_loaded": self._model_loaded,
            "model_name": self.config.model_name,
            "device": self.config.device,
            "last_error": str(self._load_error) if self._load_error else None
        }