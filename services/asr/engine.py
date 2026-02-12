import logging
import tempfile
from pathlib import Path
from typing import Any

from services.asr.config import ASRConfig
from services.asr.models import (
    ASRDomainResult,
    ASRErrorCode,
    ASRServiceError,
    SilenceSegment,
    WordTimestamp,
)

logger = logging.getLogger(__name__)


class FunASREngine:
    def __init__(self, config: ASRConfig | None = None):
        self.config = config or ASRConfig()
        self._model = None
        self._load_error: Exception | None = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from funasr import AutoModel

            self._model = AutoModel(
                model=self.config.model_name,
                vad_model=self.config.vad_model if self.config.enable_vad else None,
                punc_model=self.config.punc_model if self.config.enable_punc else None,
                device=self.config.device,
            )
            self._load_error = None
        except Exception as exc:  # pragma: no cover - depends on runtime env
            self._load_error = exc
            logger.exception("Failed to initialize FunASR model")
            raise ASRServiceError(
                ASRErrorCode.MODEL_NOT_READY,
                f"ASR model not ready: {exc}",
            ) from exc

    def transcribe(self, audio_bytes: bytes, filename: str, language: str) -> ASRDomainResult:
        if not audio_bytes:
            raise ASRServiceError(ASRErrorCode.INVALID_INPUT, "empty audio payload")

        self._ensure_model()

        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            try:
                assert self._model is not None
                raw = self._model.generate(
                    input=tmp.name,
                    language=language or None,
                    use_itn=True,
                    batch_size_s=self.config.batch_size_s,
                )
            except Exception as exc:  # pragma: no cover - depends on runtime env
                logger.exception("ASR inference failed")
                raise ASRServiceError(
                    ASRErrorCode.INFERENCE_FAILED,
                    f"ASR inference failed: {exc}",
                ) from exc

        return self._parse(raw, language)

    def _parse(self, raw_result: Any, language: str) -> ASRDomainResult:
        item = self._first_item(raw_result)
        text = str(item.get("text") or "")

        tokens = self._parse_tokens(item, text)
        vad_segments = self._parse_vad_segments(item)

        return ASRDomainResult(
            transcript=text,
            language=str(item.get("language") or language or "unknown"),
            tokens=tokens,
            silence_segments=self._vad_to_silence(vad_segments),
            audio_features={
                "backend": "funasr",
                "model": self.config.model_name,
                "vad_model": self.config.vad_model if self.config.enable_vad else None,
                "punc_model": self.config.punc_model if self.config.enable_punc else None,
                "token_count": len(tokens),
            },
        )

    @staticmethod
    def _first_item(raw_result: Any) -> dict[str, Any]:
        if isinstance(raw_result, list) and raw_result:
            item = raw_result[0]
            return item if isinstance(item, dict) else {}
        if isinstance(raw_result, dict):
            return raw_result
        return {}

    @staticmethod
    def _parse_tokens(item: dict[str, Any], text: str) -> list[WordTimestamp]:
        timestamps = item.get("timestamp")
        words = item.get("words")

        if not isinstance(timestamps, list) or not timestamps:
            return []

        if not isinstance(words, list) or len(words) != len(timestamps):
            words = list(text) if text else []

        if len(words) != len(timestamps):
            return []

        tokens: list[WordTimestamp] = []
        for word, ts in zip(words, timestamps):
            if not (isinstance(ts, (list, tuple)) and len(ts) >= 2):
                continue
            start_ms = int(ts[0])
            end_ms = int(ts[1])
            if end_ms <= start_ms:
                continue
            tokens.append(
                WordTimestamp(token=str(word), start_ms=start_ms, end_ms=end_ms)
            )
        return tokens

    @staticmethod
    def _parse_vad_segments(item: dict[str, Any]) -> list[tuple[int, int]]:
        raw_segments = item.get("vad_segments") or []
        segments: list[tuple[int, int]] = []

        for seg in raw_segments:
            if isinstance(seg, dict):
                start = seg.get("start")
                end = seg.get("end")
            elif isinstance(seg, (list, tuple)) and len(seg) >= 2:
                start, end = seg[0], seg[1]
            else:
                continue

            if start is None or end is None:
                continue
            start_ms = int(start)
            end_ms = int(end)
            if end_ms > start_ms:
                segments.append((start_ms, end_ms))

        segments.sort(key=lambda x: x[0])
        return segments

    @staticmethod
    def _vad_to_silence(vad_segments: list[tuple[int, int]]) -> list[SilenceSegment]:
        if len(vad_segments) < 2:
            return []

        silence: list[SilenceSegment] = []
        for i in range(len(vad_segments) - 1):
            _, prev_end = vad_segments[i]
            next_start, _ = vad_segments[i + 1]
            if next_start > prev_end:
                silence.append(SilenceSegment(start_ms=prev_end, end_ms=next_start))
        return silence
