"""
asr/config.py - 配置管理
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict


def get_default_model_dir() -> str:
    """
    获取默认模型目录，按优先级查找:
    1. 环境变量 ASR_MODEL_DIR
    2. 用户目录下的 .cache/funasr
    3. 当前目录下的 models
    """
    # 环境变量优先
    if env_dir := os.environ.get("ASR_MODEL_DIR"):
        return env_dir
    
    # 用户缓存目录
    home = Path.home()
    cache_dir = home / ".cache" / "funasr"
    if cache_dir.exists():
        return str(cache_dir)
    
    # 当前目录
    local_dir = Path.cwd() / "models"
    if local_dir.exists():
        return str(local_dir)
    
    # 默认返回用户缓存目录（FunASR 会自动下载到这里）
    return str(cache_dir)


# 默认模型目录
MODEL_DIR = get_default_model_dir()


@dataclass
class ASRConfig:
    """ASR 配置"""
    
    # 模型配置
    model_name: str = "iic/SenseVoiceSmall"
    model_dir: str = field(default_factory=get_default_model_dir)
    
    # VAD 配置
    enable_vad: bool = True
    vad_model: str = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    
    # 标点配置
    enable_punc: bool = True
    punc_model: str = "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    
    # 推理配置
    device: str = "auto"  # "cuda", "cpu", "auto"
    batch_size_s: int = 300
    
    # 语言配置
    language: Optional[str] = None  # None = 自动检测
    
    def __post_init__(self):
        """初始化后处理"""
        if self.device == "auto":
            self.device = self._detect_device()
    
    def _detect_device(self) -> str:
        """自动检测可用设备"""
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"


# 填充词词典
FILLER_WORDS: Dict[str, List[str]] = {
    # 犹豫/迟疑（按长度降序排列，确保最长优先匹配）
    "hesitation": [
        "嗯嗯嗯", "啊啊啊", "呃呃呃",
        "嗯嗯", "啊啊", "呃呃", "额额",
        "嗯", "啊", "呃", "额", "唔", "欸",
    ],
    
    # 思考
    "thinking": [
        "让我想一下", "让我想想", "让我考虑一下",
        "我想一下", "我想想", "我考虑一下",
        "稍等一下", "稍等",
        "这个嘛", "那个嘛",
    ],
    
    # 确认/强调（按长度降序）
    "confirmation": [
        "对对对对", "是是是是",
        "对对对", "是是是", "好好好",
        "对对", "是是", "好好", "行行",
        "对", "是", "好", "行", "嗯",
        "没错", "确实", "的确",
    ],
    
    # 不确定
    "uncertainty": [
        "可能是", "应该是", "大概是",
        "可能", "应该", "大概", "也许", "或许",
        "好像是", "好像", "似乎",
        "不太确定", "不确定",
    ],
    
    # 转折/连接
    "connector": [
        "然后的话", "就是说", "也就是说",
        "然后", "就是", "所以", "因为", 
        "但是", "不过", "其实", "反正",
    ],
}
# 在 config.py 中添加语速分析配置

@dataclass
class SpeechRateConfig:
    """语速分析配置"""
    window_size: float = 5.0        # 窗口大小（秒）
    step_size: float = 2.5          # 滑动步长（秒）
    anomaly_threshold: float = 1.5  # 异常检测阈值（标准差倍数）
    
    # 语速参考范围（字/分钟）
    normal_min: float = 180.0
    normal_max: float = 300.0

# 停顿阈值配置
@dataclass
class PauseConfig:
    """停顿检测配置"""
    short_pause_min: float = 0.3    # 短停顿最小时长(秒)
    short_pause_max: float = 0.8    # 短停顿最大时长(秒)
    long_pause_min: float = 0.8     # 长停顿最小时长(秒)
    very_long_pause_min: float = 2.0  # 超长停顿阈值(秒)


# 认知负荷阈值配置
@dataclass  
class CognitiveLoadConfig:
    """认知负荷分析配置"""
    window_size: float = 5.0        # 分析窗口大小(秒)
    window_step: float = 2.5        # 窗口滑动步长(秒)
    
    # 负荷等级阈值
    low_threshold: float = 30.0
    high_threshold: float = 70.0
    
    # 触发脚手架的条件
    scaffold_trigger_score: float = 65.0
    scaffold_trigger_consecutive: int = 2  # 连续N个高负荷窗口触发