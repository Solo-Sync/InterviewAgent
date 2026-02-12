from libs.schemas.base import AsrResult, AsrToken, SilenceSegment
from services.asr.models import ASRDomainResult


def to_contract(result: ASRDomainResult, need_word_timestamps: bool) -> AsrResult:
    tokens = None
    if need_word_timestamps:
        tokens = [
            AsrToken(token=t.token, start_ms=t.start_ms, end_ms=t.end_ms)
            for t in result.tokens
        ]

    silence_segments = [
        SilenceSegment(start_ms=s.start_ms, end_ms=s.end_ms)
        for s in result.silence_segments
    ]

    return AsrResult(
        raw_text=result.transcript,
        tokens=tokens,
        silence_segments=silence_segments,
        audio_features=result.audio_features,
    )
