"""主入口"""
from .analyzer import SpeechAnalyzer
from .config import MODEL_DIR


def main():
    # 初始化分析器
    analyzer = SpeechAnalyzer(model_dir=MODEL_DIR)
    
    # 分析音频
    audio_path = r"D:\model\test1.m4a"
    
    result = analyzer.analyze(audio_path)
    
    # 打印报告
    analyzer.print_report(result)
    
    # 导出JSON (内部格式)
    analyzer.export_json(result, r"D:\model\analysis_result.json")
    
    # 导出JSON (API格式)
    analyzer.export_api_json(result, r"D:\model\analysis_result_api.json")
    
    # 打印关键指标
    print("\n🎯 【可用于脚手架/评分的实时指标】")
    print("-" * 50)
    print(f"• 认知负荷时间序列: {[f'{s.load_score:.2f}' for s in result.cognitive_signals]}")
    print(f"• 停顿模式: {[(p.pause_type, f'{p.duration:.1f}s') for p in result.feature_stream.pauses]}")
    hesitation_list = [
        (f.word, f'{f.start_time:.1f}s') 
        for f in result.feature_stream.fillers 
        if f.filler_type == 'hesitation'
    ]
    print(f"• 犹豫词位置: {hesitation_list}")
    trigger_points = [f"{r['timestamp']:.1f}s" for r in result.scaffold_recommendations]
    print(f"• 脚手架触发点: {trigger_points}")
    
    return result


if __name__ == "__main__":
    result = main()