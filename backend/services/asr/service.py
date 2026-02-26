from services.asr.adapter import to_contract
from services.asr.engine import FunASREngine


class ASRService:
    """ASR service boundary.

    Internal implementation can be replaced (FunASR/Whisper/etc.), but API output
    must always conform to libs.schemas.base.AsrResult.
    """

    def __init__(self):
        self.engine = FunASREngine()

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str,
        need_word_timestamps: bool,
    ):
        domain_result = self.engine.transcribe(
            audio_bytes=audio_bytes, filename=filename, language=language
        )
        domain_result.audio_features.setdefault("filename", filename)
        domain_result.audio_features.setdefault("bytes", len(audio_bytes))
        domain_result.audio_features.setdefault("language", language)
        return to_contract(domain_result, need_word_timestamps)
