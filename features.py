"""声学特征提取器"""
import numpy as np
from typing import List, Dict

from .models import PauseEvent, FillerEvent
from .config import (
    FILLER_WORDS, 
    MIN_PAUSE_DURATION, 
    PAUSE_THRESHOLDS,
    SPEECH_RATE_WINDOW,
    SPEECH_RATE_STEP
)


class AcousticFeatureExtractor:
    """声学特征提取器"""
    
    def extract_pauses(self, word_timestamps: List[Dict]) -> List[PauseEvent]:
        """从词时间戳中提取停顿事件"""
        pauses = []
        
        for i in range(len(word_timestamps) - 1):
            current = word_timestamps[i]
            next_word = word_timestamps[i + 1]
            
            gap = next_word['start'] - current['end']
            
            if gap > MIN_PAUSE_DURATION:
                pause_type = self._classify_pause(gap)
                pauses.append(PauseEvent(
                    start_time=current['end'],
                    end_time=next_word['start'],
                    pause_type=pause_type,
                    preceding_word=current['word'],
                    following_word=next_word['word']
                ))
        
        return pauses
    
    def extract_pauses_from_vad(
        self, 
        vad_segments: List[Dict], 
        total_duration: float
    ) -> List[PauseEvent]:
        """从VAD结果中提取停顿（更准确）"""
        pauses = []
        
        for i in range(len(vad_segments) - 1):
            current = vad_segments[i]
            next_seg = vad_segments[i + 1]
            
            gap = next_seg['start'] - current['end']
            
            if gap > 0.1:
                pause_type = self._classify_pause(gap)
                pauses.append(PauseEvent(
                    start_time=current['end'],
                    end_time=next_seg['start'],
                    pause_type=pause_type
                ))
        
        return pauses
    
    def _classify_pause(self, duration: float) -> str:
        """分类停顿类型"""
        if duration < PAUSE_THRESHOLDS['short']:
            return 'short'
        elif duration < PAUSE_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'long'
    
    def extract_fillers(self, word_timestamps: List[Dict]) -> List[FillerEvent]:
        """提取填充词事件"""
        fillers = []
        
        for seg in word_timestamps:
            word = seg['word']
            
            for filler_type, filler_list in FILLER_WORDS.items():
                if word in filler_list:
                    fillers.append(FillerEvent(
                        word=word,
                        start_time=seg['start'],
                        end_time=seg['end'],
                        filler_type=filler_type
                    ))
                    break
        
        return fillers
    
    def calculate_speech_rate(
        self, 
        word_timestamps: List[Dict], 
        window_size: float = SPEECH_RATE_WINDOW,
        step_size: float = SPEECH_RATE_STEP
    ) -> List[Dict]:
        """计算滑动窗口内的语速"""
        if not word_timestamps:
            return []
        
        speech_rates = []
        total_duration = word_timestamps[-1]['end']
        
        current_time = 0.0
        punctuation = set('，。？！、；：""''（）【】')
        
        while current_time < total_duration:
            window_end = current_time + window_size
            
            chars_in_window = []
            speaking_time = 0.0
            
            for seg in word_timestamps:
                if seg['start'] >= current_time and seg['end'] <= window_end:
                    if seg['word'] not in punctuation:
                        chars_in_window.append(seg)
                        speaking_time += seg['end'] - seg['start']
            
            char_count = len(chars_in_window)
            actual_window = min(window_size, total_duration - current_time)
            
            if actual_window > 0:
                chars_per_minute = (char_count / actual_window) * 60
            else:
                chars_per_minute = 0
            
            speech_rates.append({
                'time_start': current_time,
                'time_end': window_end,
                'char_count': char_count,
                'chars_per_minute': chars_per_minute,
                'speaking_ratio': speaking_time / actual_window if actual_window > 0 else 0
            })
            
            current_time += step_size
        
        return speech_rates
    
    def extract_energy_features(self, audio_path: str) -> List[Dict]:
        """提取能量特征"""
        try:
            import librosa
            
            audio, sr = librosa.load(audio_path, sr=16000)
            
            hop_length = 512
            frame_length = 2048
            
            rms = librosa.feature.rms(
                y=audio, 
                frame_length=frame_length,
                hop_length=hop_length
            )[0]
            
            times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
            
            energy_timeline = []
            for t, e in zip(times, rms):
                energy_timeline.append({
                    'time': float(t),
                    'energy': float(e),
                    'energy_db': float(20 * np.log10(e + 1e-10))
                })
            
            return energy_timeline
            
        except Exception as e:
            print(f"能量提取失败: {e}")
            return []