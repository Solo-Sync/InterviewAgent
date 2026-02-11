"""FunASR 语音识别引擎"""
import re
from pathlib import Path
from typing import Dict, List

from .config import MODEL_DIR, DEVICE


class FunASREngine:
    """FunASR 语音识别引擎 (SenseVoice + VAD + 标点)"""
    
    def __init__(self, model_dir: str = MODEL_DIR, device: str = DEVICE):
        self.model_dir = Path(model_dir)
        self.device = device
        self.model = None
        self.vad_model = None
        self.punc_model = None
        self._load_models()
    
    def _load_models(self):
        """加载FunASR模型"""
        try:
            from funasr import AutoModel
            
            print("正在加载 FunASR 模型...")
            
            # 加载 SenseVoice 语音识别模型
            asr_model_path = self.model_dir / "SenseVoiceSmall"
            print(f"  ASR模型: {asr_model_path}")
            
            self.model = AutoModel(
                model=str(asr_model_path),
                trust_remote_code=True,
                disable_update=True,
                device=self.device
            )
            
            # 加载 VAD 模型
            vad_model_path = self.model_dir / "fsmn-vad"
            print(f"  VAD模型: {vad_model_path}")
            
            self.vad_model = AutoModel(
                model=str(vad_model_path),
                trust_remote_code=True,
                disable_update=True,
                device=self.device
            )
            
            # 加载标点模型
            punc_model_path = self.model_dir / "ct-punc"
            print(f"  标点模型: {punc_model_path}")
            
            self.punc_model = AutoModel(
                model=str(punc_model_path),
                trust_remote_code=True,
                disable_update=True,
                device=self.device
            )
            
            print("✓ 所有模型加载成功！\n")
            
        except ImportError:
            print("请先安装 funasr: pip install funasr")
            print("将使用模拟模式...")
            self.model = None
        except Exception as e:
            print(f"模型加载失败: {e}")
            print("将使用模拟模式...")
            self.model = None
    
    def transcribe(self, audio_path: str) -> Dict:
        """
        转录音频文件
        返回: 包含文本、时间戳、VAD信息的字典
        """
        if self.model is None:
            return self._mock_transcribe(audio_path)
        
        result = {
            'text': '',
            'word_timestamps': [],
            'vad_segments': [],
            'sentences': []
        }
        
        try:
            # Step 1: VAD 检测语音段
            print("  执行VAD检测...")
            vad_result = self.vad_model.generate(
                input=audio_path,
                batch_size_s=300
            )
            
            if vad_result and len(vad_result) > 0:
                vad_segments = vad_result[0].get('value', [])
                result['vad_segments'] = [
                    {'start': seg[0] / 1000, 'end': seg[1] / 1000}
                    for seg in vad_segments
                ]
                print(f"    检测到 {len(result['vad_segments'])} 个语音段")
            
            # Step 2: ASR 语音识别
            print("  执行语音识别...")
            asr_result = self.model.generate(
                input=audio_path,
                batch_size_s=300,
                return_raw_text=False
            )
            
            if asr_result and len(asr_result) > 0:
                asr_output = asr_result[0]
                
                if isinstance(asr_output, dict):
                    result['text'] = asr_output.get('text', '')
                    
                    if 'timestamp' in asr_output:
                        timestamps = asr_output['timestamp']
                        result['word_timestamps'] = self._parse_sensevoice_output(
                            result['text'], 
                            timestamps
                        )
                    else:
                        result['word_timestamps'] = self._estimate_timestamps(
                            result['text'],
                            result['vad_segments']
                        )
                else:
                    result['text'] = str(asr_output)
            
            # Step 3: 标点恢复
            if result['text'] and self.punc_model:
                print("  恢复标点...")
                punc_result = self.punc_model.generate(
                    input=result['text']
                )
                if punc_result and len(punc_result) > 0:
                    result['text'] = punc_result[0].get('text', result['text'])
            
            # 清理特殊标记
            result['text'] = re.sub(r'<\|[^|]+\|>', '', result['text']).strip()
            
            print(f"  识别完成: {result['text'][:50]}...")
            
        except Exception as e:
            print(f"转录出错: {e}")
            import traceback
            traceback.print_exc()
            return self._mock_transcribe(audio_path)
        
        return result
    
    def _parse_sensevoice_output(self, text: str, timestamps: List) -> List[Dict]:
        """解析SenseVoice输出的时间戳"""
        word_timestamps = []
        chars = list(text.replace(' ', ''))
        
        for i, (char, ts) in enumerate(zip(chars, timestamps)):
            if isinstance(ts, (list, tuple)) and len(ts) >= 2:
                word_timestamps.append({
                    'word': char,
                    'start': ts[0] / 1000 if ts[0] > 100 else ts[0],
                    'end': ts[1] / 1000 if ts[1] > 100 else ts[1],
                    'confidence': 0.95
                })
        
        return word_timestamps
    
    def _estimate_timestamps(self, text: str, vad_segments: List[Dict]) -> List[Dict]:
        """基于VAD和文本估算时间戳"""
        if not vad_segments or not text:
            return []
        
        word_timestamps = []
        chars = [c for c in text if c.strip()]
        
        total_speech_duration = sum(
            seg['end'] - seg['start'] for seg in vad_segments
        )
        
        if not chars:
            return []
        
        char_duration = total_speech_duration / len(chars)
        current_time = vad_segments[0]['start'] if vad_segments else 0
        seg_idx = 0
        
        for char in chars:
            if seg_idx < len(vad_segments):
                if current_time >= vad_segments[seg_idx]['end']:
                    seg_idx += 1
                    if seg_idx < len(vad_segments):
                        current_time = vad_segments[seg_idx]['start']
            
            word_timestamps.append({
                'word': char,
                'start': current_time,
                'end': current_time + char_duration,
                'confidence': 0.8
            })
            
            current_time += char_duration
        
        return word_timestamps
    
    def _mock_transcribe(self, audio_path: str) -> Dict:
        """模拟转录（用于测试）"""
        print("  [模拟模式] 生成测试数据...")
        
        mock_text = "嗯，我觉得这个问题，呃，应该从两个方面来考虑。首先是，嗯，基本概念的理解，然后是实际应用。"
        
        mock_timestamps = [
            {"word": "嗯", "start": 0.0, "end": 0.3, "confidence": 0.95},
            {"word": "，", "start": 0.3, "end": 0.35, "confidence": 1.0},
            {"word": "我", "start": 0.8, "end": 0.95, "confidence": 0.98},
            {"word": "觉", "start": 0.95, "end": 1.05, "confidence": 0.97},
            {"word": "得", "start": 1.05, "end": 1.15, "confidence": 0.97},
            {"word": "这", "start": 1.15, "end": 1.25, "confidence": 0.96},
            {"word": "个", "start": 1.25, "end": 1.35, "confidence": 0.96},
            {"word": "问", "start": 1.35, "end": 1.5, "confidence": 0.98},
            {"word": "题", "start": 1.5, "end": 1.65, "confidence": 0.98},
            {"word": "，", "start": 1.65, "end": 1.7, "confidence": 1.0},
            {"word": "呃", "start": 2.2, "end": 2.5, "confidence": 0.92},
            {"word": "，", "start": 2.5, "end": 2.55, "confidence": 1.0},
            {"word": "应", "start": 2.9, "end": 3.0, "confidence": 0.97},
            {"word": "该", "start": 3.0, "end": 3.15, "confidence": 0.97},
            {"word": "从", "start": 3.15, "end": 3.3, "confidence": 0.98},
            {"word": "两", "start": 3.3, "end": 3.45, "confidence": 0.96},
            {"word": "个", "start": 3.45, "end": 3.55, "confidence": 0.96},
            {"word": "方", "start": 3.55, "end": 3.7, "confidence": 0.97},
            {"word": "面", "start": 3.7, "end": 3.85, "confidence": 0.97},
            {"word": "来", "start": 3.85, "end": 4.0, "confidence": 0.98},
            {"word": "考", "start": 4.0, "end": 4.15, "confidence": 0.97},
            {"word": "虑", "start": 4.15, "end": 4.3, "confidence": 0.97},
            {"word": "。", "start": 4.3, "end": 4.35, "confidence": 1.0},
            {"word": "首", "start": 4.8, "end": 4.95, "confidence": 0.98},
            {"word": "先", "start": 4.95, "end": 5.1, "confidence": 0.98},
            {"word": "是", "start": 5.1, "end": 5.25, "confidence": 0.99},
            {"word": "，", "start": 5.25, "end": 5.3, "confidence": 1.0},
            {"word": "嗯", "start": 5.7, "end": 6.0, "confidence": 0.93},
            {"word": "，", "start": 6.0, "end": 6.05, "confidence": 1.0},
            {"word": "基", "start": 6.3, "end": 6.45, "confidence": 0.97},
            {"word": "本", "start": 6.45, "end": 6.6, "confidence": 0.97},
            {"word": "概", "start": 6.6, "end": 6.75, "confidence": 0.98},
            {"word": "念", "start": 6.75, "end": 6.9, "confidence": 0.98},
            {"word": "的", "start": 6.9, "end": 7.0, "confidence": 0.99},
            {"word": "理", "start": 7.0, "end": 7.15, "confidence": 0.97},
            {"word": "解", "start": 7.15, "end": 7.3, "confidence": 0.97},
            {"word": "，", "start": 7.3, "end": 7.35, "confidence": 1.0},
            {"word": "然", "start": 7.7, "end": 7.85, "confidence": 0.98},
            {"word": "后", "start": 7.85, "end": 8.0, "confidence": 0.98},
            {"word": "是", "start": 8.0, "end": 8.15, "confidence": 0.99},
            {"word": "实", "start": 8.15, "end": 8.3, "confidence": 0.97},
            {"word": "际", "start": 8.3, "end": 8.45, "confidence": 0.97},
            {"word": "应", "start": 8.45, "end": 8.6, "confidence": 0.98},
            {"word": "用", "start": 8.6, "end": 8.75, "confidence": 0.98},
            {"word": "。", "start": 8.75, "end": 8.8, "confidence": 1.0},
        ]
        
        mock_vad = [
            {'start': 0.0, 'end': 1.7},
            {'start': 2.2, 'end': 4.35},
            {'start': 4.8, 'end': 6.05},
            {'start': 6.3, 'end': 8.8}
        ]
        
        return {
            'text': mock_text,
            'word_timestamps': mock_timestamps,
            'vad_segments': mock_vad,
            'sentences': []
        }