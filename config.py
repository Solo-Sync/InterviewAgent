"""配置常量"""
import os

# 模型路径 (可通过环境变量覆盖)
MODEL_DIR = os.getenv("ASR_MODEL_DIR", r"D:\model")

# 设备配置
DEVICE = os.getenv("ASR_DEVICE", "cuda:0")  # 或 "cpu"

# 填充词库
FILLER_WORDS = {
    'hesitation': ['嗯', '呃', '啊', '额', '这个', '那个', '就是', '然后'],
    'thinking': ['让我想想', '我想一下', '稍等', '等一下', '怎么说'],
    'confirmation': ['对', '是的', '没错', '嗯嗯', '好的', '对对对'],
    'uncertainty': ['可能', '大概', '也许', '好像', '似乎', '应该']
}

# 认知负荷指标权重
COGNITIVE_WEIGHTS = {
    'pause_frequency': 0.20,
    'long_pause_ratio': 0.15,
    'filler_frequency': 0.20,
    'speech_rate_variance': 0.15,
    'hesitation_density': 0.15,
    'silence_ratio': 0.15
}

# 脚手架触发阈值
SCAFFOLD_THRESHOLDS = {
    'low': 0.3,
    'medium': 0.6,
    'high': 0.8
}

# 停顿分类阈值 (秒)
PAUSE_THRESHOLDS = {
    'short': 0.5,   # < 0.5s
    'medium': 1.5   # 0.5s - 1.5s, > 1.5s 为 long
}

# 最小停顿检测阈值 (秒)
MIN_PAUSE_DURATION = 0.2

# 语速计算窗口 (秒)
SPEECH_RATE_WINDOW = 5.0
SPEECH_RATE_STEP = 1.0

# 认知负荷分析窗口 (秒)
COGNITIVE_WINDOW = 10.0
COGNITIVE_STEP = 5.0