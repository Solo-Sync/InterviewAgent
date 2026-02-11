"""语音分析主类"""
import json
import re
import numpy as np
from typing import List, Dict

from .config import MODEL_DIR
from .models import (
    WordSegment, SemanticStream, FeatureStream, 
    AnalysisResult, CognitiveLoadSignal
)
from .engine import FunASREngine
from .features import AcousticFeatureExtractor
from .cognitive import CognitiveLoadAnalyzer
from .adapter import ApiAdapter


class SpeechAnalyzer:
    """语音分析主类"""
    
    def __init__(self, model_dir: str = MODEL_DIR):
        self.asr_engine = FunASREngine(model_dir)
        self.feature_extractor = AcousticFeatureExtractor()
        self.cognitive_analyzer = CognitiveLoadAnalyzer()
    
    def analyze(self, audio_path: str) -> AnalysisResult:
        """完整分析流程"""
        print(f"\n{'='*60}")
        print(f"  语音分析系统")
        print(f"  文件: {audio_path}")
        print(f"{'='*60}\n")
        
        # Step 1: 语音识别
        print("[1/4] 语音识别...")
        asr_result = self.asr_engine.transcribe(audio_path)
        
        word_timestamps = asr_result['word_timestamps']
        vad_segments = asr_result['vad_segments']
        
        # 构建语义流
        segments = [
            WordSegment(
                word=w['word'],
                start_time=w['start'],
                end_time=w['end'],
                confidence=w.get('confidence', 1.0)
            )
            for w in word_timestamps
        ]
        
        sentences = self._segment_sentences(word_timestamps)
        
        semantic_stream = SemanticStream(
            full_text=asr_result['text'],
            segments=segments,
            sentences=sentences
        )
        
        # Step 2: 特征提取
        print("[2/4] 特征提取...")
        
        pauses_from_words = self.feature_extractor.extract_pauses(word_timestamps)
        pauses_from_vad = self.feature_extractor.extract_pauses_from_vad(
            vad_segments, 
            word_timestamps[-1]['end'] if word_timestamps else 0
        )
        
        all_pauses = pauses_from_vad if pauses_from_vad else pauses_from_words
        
        fillers = self.feature_extractor.extract_fillers(word_timestamps)
        speech_rates = self.feature_extractor.calculate_speech_rate(word_timestamps)
        
        try:
            energy_timeline = self.feature_extractor.extract_energy_features(audio_path)
        except:
            energy_timeline = []
        
        feature_stream = FeatureStream(
            pauses=all_pauses,
            fillers=fillers,
            speech_rate_timeline=speech_rates,
            energy_timeline=energy_timeline,
            vad_segments=[
                {'start': s['start'], 'end': s['end']} 
                for s in vad_segments
            ]
        )
        
        print(f"    停顿: {len(all_pauses)}个, 填充词: {len(fillers)}个")
        
        # Step 3: 认知负荷分析
        print("[3/4] 认知负荷分析...")
        total_duration = word_timestamps[-1]['end'] if word_timestamps else 0
        
        cognitive_signals = self.cognitive_analyzer.analyze(
            feature_stream,
            word_timestamps,
            total_duration
        )
        
        # Step 4: 汇总
        print("[4/4] 生成报告...")
        summary_metrics = self._calculate_summary(
            semantic_stream, feature_stream, cognitive_signals, total_duration
        )
        
        scaffold_recommendations = self._generate_scaffold_recommendations(
            cognitive_signals, feature_stream
        )
        
        print(f"\n{'='*60}")
        print("  分析完成！")
        print(f"{'='*60}\n")
        
        return AnalysisResult(
            semantic_stream=semantic_stream,
            feature_stream=feature_stream,
            cognitive_signals=cognitive_signals,
            summary_metrics=summary_metrics,
            scaffold_recommendations=scaffold_recommendations
        )
    
    def _segment_sentences(self, word_timestamps: List[Dict]) -> List[Dict]:
        """分割句子"""
        sentences = []
        current_sentence = []
        sentence_start = 0.0
        
        sentence_endings = ['。', '？', '！', '；']
        
        for seg in word_timestamps:
            current_sentence.append(seg)
            
            if seg['word'] in sentence_endings:
                sentences.append({
                    'text': ''.join(w['word'] for w in current_sentence),
                    'start_time': sentence_start,
                    'end_time': seg['end'],
                    'word_count': len(current_sentence)
                })
                current_sentence = []
                sentence_start = seg['end']
        
        if current_sentence:
            sentences.append({
                'text': ''.join(w['word'] for w in current_sentence),
                'start_time': sentence_start,
                'end_time': current_sentence[-1]['end'] if current_sentence else sentence_start,
                'word_count': len(current_sentence)
            })
        
        return sentences
    
    def _calculate_summary(
        self, 
        semantic: SemanticStream, 
        features: FeatureStream, 
        signals: List[CognitiveLoadSignal], 
        total_duration: float
    ) -> Dict:
        """计算汇总指标"""
        pause_durations = [p.duration for p in features.pauses]
        speech_rates = [r['chars_per_minute'] for r in features.speech_rate_timeline]
        load_scores = [s.load_score for s in signals]
        
        return {
            'total_duration': total_duration,
            'char_count': len(semantic.segments),
            'sentence_count': len(semantic.sentences),
            'pause_count': len(features.pauses),
            'pause_total_duration': sum(pause_durations) if pause_durations else 0,
            'pause_mean_duration': np.mean(pause_durations) if pause_durations else 0,
            'long_pause_count': len([p for p in features.pauses if p.pause_type == 'long']),
            'filler_count': len(features.fillers),
            'filler_by_type': {
                ft: len([f for f in features.fillers if f.filler_type == ft])
                for ft in ['hesitation', 'thinking', 'confirmation', 'uncertainty']
            },
            'speech_rate_mean': np.mean(speech_rates) if speech_rates else 0,
            'speech_rate_std': np.std(speech_rates) if speech_rates else 0,
            'cognitive_load_mean': np.mean(load_scores) if load_scores else 0,
            'cognitive_load_max': max(load_scores) if load_scores else 0,
            'high_load_ratio': len([s for s in signals if s.load_level == 'high']) / len(signals) if signals else 0,
            'scaffold_trigger_count': len([s for s in signals if s.trigger_scaffold])
        }
    
    def _generate_scaffold_recommendations(
        self, 
        signals: List[CognitiveLoadSignal], 
        features: FeatureStream
    ) -> List[Dict]:
        """生成脚手架建议"""
        return [
            {
                'timestamp': s.timestamp,
                'load_level': s.load_level,
                'load_score': s.load_score,
                'intervention': s.suggested_intervention,
                'priority': 'high' if s.load_level == 'high' else 'medium'
            }
            for s in signals if s.trigger_scaffold
        ]
    
    def print_report(self, result: AnalysisResult):
        """打印分析报告"""
        print("\n" + "="*70)
        print("                         语音分析报告")
        print("="*70)
        
        # 语义流
        print("\n📝 【语义流】")
        print(f"   文本: {result.semantic_stream.full_text}")
        print(f"   句子数: {len(result.semantic_stream.sentences)}")
        
        # 特征流
        print("\n📊 【特征流】")
        print(f"   停顿事件: {len(result.feature_stream.pauses)} 个")
        
        for i, p in enumerate(result.feature_stream.pauses[:5], 1):
            print(f"      {i}. [{p.start_time:.2f}s - {p.end_time:.2f}s] "
                  f"时长:{p.duration:.2f}s ({p.pause_type})")
        
        print(f"\n   填充词: {len(result.feature_stream.fillers)} 个")
        for f in result.feature_stream.fillers:
            print(f"      - '{f.word}' @ {f.start_time:.2f}s ({f.filler_type})")
        
        # 认知负荷
        print("\n🧠 【认知负荷信号】")
        for sig in result.cognitive_signals:
            icon = "🔴" if sig.load_level == 'high' else ("🟡" if sig.load_level == 'medium' else "🟢")
            print(f"   {icon} [{sig.timestamp:.1f}s] {sig.load_level.upper()} "
                  f"(得分: {sig.load_score:.2f})")
            if sig.trigger_scaffold:
                print(f"      ⚡ {sig.suggested_intervention}")
        
        # 汇总
        print("\n📈 【汇总指标】")
        m = result.summary_metrics
        print(f"   总时长: {m['total_duration']:.1f}s")
        print(f"   字符数: {m['char_count']}")
        print(f"   平均语速: {m['speech_rate_mean']:.0f} 字/分钟")
        print(f"   停顿总时长: {m['pause_total_duration']:.1f}s")
        print(f"   平均认知负荷: {m['cognitive_load_mean']:.2f}")
        print(f"   脚手架触发: {m['scaffold_trigger_count']} 次")
        
        print("\n" + "="*70)
    
    def export_json(self, result: AnalysisResult, output_path: str):
        """导出JSON (内部格式)"""
        
        def convert_to_serializable(obj):
            if isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            return obj
        
        data = {
            'semantic_stream': {
                'full_text': result.semantic_stream.full_text,
                'segments': [
                    {
                        'word': s.word, 
                        'start': float(s.start_time), 
                        'end': float(s.end_time), 
                        'confidence': float(s.confidence)
                    }
                    for s in result.semantic_stream.segments
                ],
                'sentences': result.semantic_stream.sentences
            },
            'feature_stream': {
                'pauses': [
                    {
                        'start': float(p.start_time), 
                        'end': float(p.end_time), 
                        'type': p.pause_type, 
                        'duration': float(p.duration)
                    }
                    for p in result.feature_stream.pauses
                ],
                'fillers': [
                    {
                        'word': f.word, 
                        'start': float(f.start_time), 
                        'type': f.filler_type
                    }
                    for f in result.feature_stream.fillers
                ],
                'speech_rates': result.feature_stream.speech_rate_timeline,
                'vad_segments': result.feature_stream.vad_segments
            },
            'cognitive_signals': [
                {
                    'timestamp': float(s.timestamp),
                    'level': s.load_level,
                    'score': float(s.load_score),
                    'indicators': {k: float(v) for k, v in s.indicators.items()},
                    'trigger': bool(s.trigger_scaffold),
                    'intervention': s.suggested_intervention
                }
                for s in result.cognitive_signals
            ],
            'summary': convert_to_serializable(result.summary_metrics),
            'recommendations': result.scaffold_recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 已导出: {output_path}")
    
    def export_api_json(self, result: AnalysisResult, output_path: str):
        """导出 API 兼容格式的 JSON"""
        
        def convert_numpy(obj):
            if isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            return obj
        
        api_data = {
            'asr': {
                'raw_text': result.semantic_stream.full_text,
                'tokens': [
                    {
                        'token': s.word,
                        'start_ms': int(s.start_time * 1000),
                        'end_ms': int(s.end_time * 1000)
                    }
                    for s in result.semantic_stream.segments
                ],
                'silence_segments': [
                    {
                        'start_ms': int(p.start_time * 1000),
                        'end_ms': int(p.end_time * 1000)
                    }
                    for p in result.feature_stream.pauses
                ],
                'audio_features': convert_numpy(
                    ApiAdapter.to_audio_features(
                        result.feature_stream, 
                        result.summary_metrics
                    )
                )
            },
            'preprocess': {
                'clean_text': ApiAdapter.clean_text(result.semantic_stream.full_text),
                'filler_stats': result.summary_metrics.get('filler_by_type', {}),
                'hesitation_rate': (
                    result.summary_metrics.get('filler_by_type', {}).get('hesitation', 0) /
                    max(result.summary_metrics.get('filler_count', 1), 1)
                )
            },
            'triggers': ApiAdapter.to_triggers(
                result.cognitive_signals,
                result.feature_stream
            ),
            'summary': convert_numpy(result.summary_metrics),
            'scaffold_recommendations': result.scaffold_recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 已导出 API 格式: {output_path}")
    
    # API 兼容方法
    def transcribe_for_api(self, audio_path: str) -> Dict:
        """API 兼容的转录方法"""
        raw_result = self.asr_engine.transcribe(audio_path)
        return ApiAdapter.to_asr_result(raw_result)
    
    def preprocess_for_api(self, text: str) -> Dict:
        """API 兼容的预处理方法"""
        from .config import FILLER_WORDS
        from .models import FillerEvent
        
        clean_text = ApiAdapter.clean_text(text)
        
        # 移除填充词
        for filler_list in FILLER_WORDS.values():
            for fw in filler_list:
                clean_text = clean_text.replace(fw, '')
        
        # 提取填充词
        fillers = []
        for filler_type, filler_list in FILLER_WORDS.items():
            for fw in filler_list:
                count = text.count(fw)
                for _ in range(count):
                    fillers.append(FillerEvent(
                        word=fw,
                        start_time=0,
                        end_time=0,
                        filler_type=filler_type
                    ))
        
        return ApiAdapter.to_preprocess_result(clean_text, fillers)