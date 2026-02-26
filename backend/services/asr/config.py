import os
from dataclasses import dataclass


@dataclass
class ASRConfig:
    model_name: str = os.getenv("ASR_MODEL_NAME", "iic/SenseVoiceSmall")
    vad_model: str = os.getenv(
        "ASR_VAD_MODEL", "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    )
    punc_model: str = os.getenv(
        "ASR_PUNC_MODEL", "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    )
    device: str = os.getenv("ASR_DEVICE", "cpu")
    batch_size_s: int = int(os.getenv("ASR_BATCH_SIZE_S", "300"))
    enable_vad: bool = os.getenv("ASR_ENABLE_VAD", "true").lower() == "true"
    enable_punc: bool = os.getenv("ASR_ENABLE_PUNC", "true").lower() == "true"
