from dataclasses import dataclass, field
from enum import Enum


@dataclass
class WordTimestamp:
    token: str
    start_ms: int
    end_ms: int


@dataclass
class SilenceSegment:
    start_ms: int
    end_ms: int


@dataclass
class ASRDomainResult:
    transcript: str
    language: str
    tokens: list[WordTimestamp] = field(default_factory=list)
    silence_segments: list[SilenceSegment] = field(default_factory=list)
    audio_features: dict[str, object] = field(default_factory=dict)


class ASRErrorCode(str, Enum):
    MODEL_NOT_READY = "MODEL_NOT_READY"
    INVALID_INPUT = "INVALID_INPUT"
    INFERENCE_FAILED = "INFERENCE_FAILED"


class ASRServiceError(RuntimeError):
    def __init__(self, code: ASRErrorCode, message: str):
        self.code = code
        super().__init__(message)
