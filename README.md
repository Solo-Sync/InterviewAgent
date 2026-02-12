# ASR 语音分析模块

基于 FunASR (SenseVoice) 的语音分析系统，提供语音识别、特征提取和认知负荷分析功能。

## 功能特性

- 🎤 **语音识别 (ASR)** - 基于 SenseVoice 模型
- 🔇 **VAD 语音活动检测** - 基于 FSMN-VAD 模型
- ⏸️ **停顿检测** - 识别短/中/长停顿
- 💬 **填充词提取** - 识别犹豫词、思考词等
- 🧠 **认知负荷分析** - 实时评估学习者认知状态
- 🪜 **脚手架触发建议** - 基于认知负荷的干预建议

## 安装

```bash
pip install -r requirements.txt
# 基本用法
python -m asr interview.wav

# 指定输出
python -m asr interview.wav -o result.json

# API 格式输出
python -m asr interview.wav --api-format -o api_result.json

# 指定模型目录（Linux/Mac）
python -m asr interview.wav --model-dir ~/.cache/funasr

# 指定模型目录（Windows）
python -m asr interview.wav --model-dir C:\Users\xxx\.cache\funasr

# 使用环境变量
export ASR_MODEL_DIR=/data/models/funasr
python -m asr interview.wav

# 强制使用 CPU
python -m asr interview.wav --device cpu

# 详细日志
python -m asr interview.wav -v