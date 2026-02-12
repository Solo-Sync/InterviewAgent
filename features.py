"""声学特征提取器"""
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from .models import PauseEvent, FillerEvent
from .config import FILLER_WORDS, PauseConfig


class WindowAssignmentMethod(Enum):
    """Token 归属窗口的方法"""
    FULLY_CONTAINED = "fully_contained"  # 完全包含（原方法）
    MIDPOINT = "midpoint"                # 中点归属
    OVERLAP_RATIO = "overlap_ratio"      # 重叠比例


class AcousticFeatureExtractor:
    """声学特征提取器"""
    
    def __init__(self, pause_config: Optional[PauseConfig] = None):
        self.pause_config = pause_config or PauseConfig()
    
    def extract_pauses(self, word_timestamps: List[Dict]) -> List[PauseEvent]:
        """从词时间戳中提取停顿事件"""
        pauses = []
        
        for i in range(len(word_timestamps) - 1):
            current = word_timestamps[i]
            next_word = word_timestamps[i + 1]
            
            gap = next_word['start'] - current['end']
            
            if gap >= self.pause_config.short_pause_min:
                pause_type = self._classify_pause(gap)
                pauses.append(PauseEvent(
                    start_time=current['end'],
                    end_time=next_word['start'],
                    pause_type=pause_type,
                    preceding_word=current.get('word'),
                    following_word=next_word.get('word')
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
            
            if gap >= self.pause_config.short_pause_min:
                pause_type = self._classify_pause(gap)
                pauses.append(PauseEvent(
                    start_time=current['end'],
                    end_time=next_seg['start'],
                    pause_type=pause_type
                ))
        
        return pauses
    
    def _classify_pause(self, duration: float) -> str:
        """分类停顿类型"""
        if duration < self.pause_config.short_pause_max:
            return 'short'
        elif duration < self.pause_config.long_pause_min:
            return 'medium'
        elif duration < self.pause_config.very_long_pause_min:
            return 'long'
        else:
            return 'very_long'
    
    def extract_fillers(self, word_timestamps: List[Dict]) -> List[FillerEvent]:
        """
        提取填充词事件
        
        改进：按词长降序匹配，确保最长匹配优先
        """
        fillers = []
        
        for seg in word_timestamps:
            word = seg.get('word', '')
            if not word:
                continue
            
            matched = False
            for filler_type, filler_list in FILLER_WORDS.items():
                # filler_list 已在 config 中按长度降序排列
                for filler in filler_list:
                    if filler in word:
                        fillers.append(FillerEvent(
                            word=filler,
                            start_time=seg['start'],
                            end_time=seg['end'],
                            filler_type=filler_type
                        ))
                        matched = True
                        break
                if matched:
                    break
        
        return fillers
    
    def calculate_speech_rate(
        self, 
        word_timestamps: List[Dict], 
        window_size: float = 5.0,
        step_size: float = 2.5,
        method: WindowAssignmentMethod = WindowAssignmentMethod.MIDPOINT
    ) -> List[Dict]:
        """
        计算滑动窗口内的语速
        
        Args:
            word_timestamps: 词时间戳列表
            window_size: 窗口大小（秒）
            step_size: 滑动步长（秒）
            method: token 归属窗口的方法
            
        Returns:
            每个窗口的语速统计
        """
        if not word_timestamps:
            return []
        
        total_duration = word_timestamps[-1]['end']
        punctuation = set('，。？！、；：""''（）【】,.?!;:()[]')
        
        # 过滤标点，预计算中点
        valid_tokens = []
        for seg in word_timestamps:
            word = seg.get('word', '')
            if word and word not in punctuation:
                valid_tokens.append({
                    **seg,
                    'midpoint': (seg['start'] + seg['end']) / 2,
                    'duration': seg['end'] - seg['start']
                })
        
        speech_rates = []
        current_time = 0.0
        
        while current_time < total_duration:
            window_end = min(current_time + window_size, total_duration)
            actual_window = window_end - current_time
            
            if actual_window <= 0:
                break
            
            # 根据方法统计 token
            if method == WindowAssignmentMethod.MIDPOINT:
                stats = self._count_by_midpoint(
                    valid_tokens, current_time, window_end
                )
            elif method == WindowAssignmentMethod.OVERLAP_RATIO:
                stats = self._count_by_overlap(
                    valid_tokens, current_time, window_end
                )
            else:  # FULLY_CONTAINED
                stats = self._count_fully_contained(
                    valid_tokens, current_time, window_end
                )
            
            char_count = stats['char_count']
            speaking_time = stats['speaking_time']
            
            chars_per_minute = (char_count / actual_window) * 60 if actual_window > 0 else 0
            speaking_ratio = speaking_time / actual_window if actual_window > 0 else 0
            
            speech_rates.append({
                'time_start': round(current_time, 3),
                'time_end': round(window_end, 3),
                'char_count': char_count,
                'chars_per_minute': round(chars_per_minute, 1),
                'speaking_ratio': round(speaking_ratio, 3),
                'speaking_time': round(speaking_time, 3)
            })
            
            current_time += step_size
        
        return speech_rates
    
    def _count_by_midpoint(
        self, 
        tokens: List[Dict], 
        window_start: float, 
        window_end: float
    ) -> Dict:
        """
        中点归属法：token 中点在窗口内则整个 token 计入该窗口
        
        优点：简单直观，每个 token 只归属一个窗口
        """
        char_count = 0
        speaking_time = 0.0
        
        for token in tokens:
            midpoint = token['midpoint']
            if window_start <= midpoint < window_end:
                char_count += len(token.get('word', ''))
                speaking_time += token['duration']
        
        return {
            'char_count': char_count,
            'speaking_time': speaking_time
        }
    
    def _count_by_overlap(
        self, 
        tokens: List[Dict], 
        window_start: float, 
        window_end: float
    ) -> Dict:
        """
        重叠比例法：按 token 与窗口的重叠比例计入
        
        优点：更精确，不丢失任何信息
        缺点：同一 token 可能被多个窗口部分计入
        """
        char_count = 0.0
        speaking_time = 0.0
        
        for token in tokens:
            token_start = token['start']
            token_end = token['end']
            token_duration = token['duration']
            
            if token_duration <= 0:
                continue
            
            # 计算重叠区间
            overlap_start = max(token_start, window_start)
            overlap_end = min(token_end, window_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration > 0:
                ratio = overlap_duration / token_duration
                word_len = len(token.get('word', ''))
                char_count += word_len * ratio
                speaking_time += overlap_duration
        
        return {
            'char_count': round(char_count, 2),  # 可能是小数
            'speaking_time': speaking_time
        }
    
    def _count_fully_contained(
        self, 
        tokens: List[Dict], 
        window_start: float, 
        window_end: float
    ) -> Dict:
        """
        完全包含法（原方法）：只统计完全在窗口内的 token
        
        缺点：会丢失跨边界的 token
        """
        char_count = 0
        speaking_time = 0.0
        
        for token in tokens:
            if token['start'] >= window_start and token['end'] <= window_end:
                char_count += len(token.get('word', ''))
                speaking_time += token['duration']
        
        return {
            'char_count': char_count,
            'speaking_time': speaking_time
        }
    
    def calculate_speech_rate_statistics(
        self, 
        speech_rates: List[Dict]
    ) -> Dict:
        """计算语速的统计摘要"""
        if not speech_rates:
            return {
                'mean': 0,
                'std': 0,
                'min': 0,
                'max': 0,
                'median': 0,
                'cv': 0  # 变异系数
            }
        
        rates = [r['chars_per_minute'] for r in speech_rates]
        rates_array = np.array(rates)
        
        mean = float(np.mean(rates_array))
        std = float(np.std(rates_array))
        
        return {
            'mean': round(mean, 1),
            'std': round(std, 1),
            'min': round(float(np.min(rates_array)), 1),
            'max': round(float(np.max(rates_array)), 1),
            'median': round(float(np.median(rates_array)), 1),
            'cv': round(std / mean, 3) if mean > 0 else 0  # 变异系数
        }
    
    def extract_energy_features(
        self, 
        audio_path: str,
        frame_length: int = 2048,
        hop_length: int = 512
    ) -> List[Dict]:
        """提取能量特征"""
        try:
            import librosa
            
            audio, sr = librosa.load(audio_path, sr=16000)
            
            rms = librosa.feature.rms(
                y=audio, 
                frame_length=frame_length,
                hop_length=hop_length
            )[0]
            
            times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
            
            energy_timeline = []
            for t, e in zip(times, rms):
                energy_db = float(20 * np.log10(e + 1e-10))
                energy_timeline.append({
                    'time': round(float(t), 3),
                    'energy': round(float(e), 6),
                    'energy_db': round(energy_db, 1)
                })
            
            return energy_timeline
            
        except ImportError:
            print("警告: librosa 未安装，跳过能量特征提取")
            return []
        except Exception as e:
            print(f"能量提取失败: {e}")
            return []
    
    def detect_speech_rate_anomalies(
        self, 
        speech_rates: List[Dict],
        threshold_std: float = 1.5
    ) -> List[Dict]:
        """
        检测语速异常区间（过快或过慢）
        
        Args:
            speech_rates: 语速统计列表
            threshold_std: 异常阈值（标准差倍数）
            
        Returns:
            异常区间列表
        """
        if len(speech_rates) < 3:
            return []
        
        rates = np.array([r['chars_per_minute'] for r in speech_rates])
        mean = np.mean(rates)
        std = np.std(rates)
        
        if std < 1:  # 语速很稳定，无异常
            return []
        
        anomalies = []
        upper_bound = mean + threshold_std * std
        lower_bound = mean - threshold_std * std
        
        for i, rate_info in enumerate(speech_rates):
            rate = rate_info['chars_per_minute']
            
            if rate > upper_bound:
                anomalies.append({
                    'time_start': rate_info['time_start'],
                    'time_end': rate_info['time_end'],
                    'type': 'fast',
                    'rate': rate,
                    'deviation': round((rate - mean) / std, 2)
                })
            elif rate < lower_bound and rate > 0:
                anomalies.append({
                    'time_start': rate_info['time_start'],
                    'time_end': rate_info['time_end'],
                    'type': 'slow',
                    'rate': rate,
                    'deviation': round((rate - mean) / std, 2)
                })
        
        return anomalies