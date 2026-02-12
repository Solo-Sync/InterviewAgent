#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
asr/main.py - 语音分析命令行入口

用法:
    # 作为模块运行（推荐）
    python -m asr audio.wav
    
    # 或直接运行
    python asr/main.py audio.wav
    
    # 指定输出路径
    python -m asr audio.wav -o result.json
    
    # 指定模型目录
    python -m asr audio.wav --model-dir /path/to/models
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# 处理直接运行 vs 模块运行的导入问题
if __name__ == "__main__" and __package__ is None:
    # 直接运行 python main.py 时，添加父目录到 path
    parent_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(parent_dir))
    __package__ = "asr"

from .config import ASRConfig, MODEL_DIR
from .analyzer import SpeechAnalyzer
from .engine import ASRError, ASRErrorCode


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def parse_args(argv=None):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="语音分析工具 - 基于 FunASR 的语音识别与认知负荷分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    %(prog)s interview.wav
    %(prog)s interview.wav -o result.json
    %(prog)s interview.wav --api-format -o api_result.json
    %(prog)s interview.wav --model-dir ~/models/funasr
        """
    )
    
    # 必需参数
    parser.add_argument(
        "audio",
        type=str,
        help="输入音频文件路径（支持 wav, mp3, m4a 等格式）"
    )
    
    # 输出选项
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径（默认: 与输入文件同名的 .json）"
    )
    
    parser.add_argument(
        "--api-format",
        action="store_true",
        help="使用 API 兼容格式输出"
    )
    
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="不打印分析报告到控制台"
    )
    
    # 模型选项
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help=f"模型目录路径（默认: {MODEL_DIR}）"
    )
    
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="ASR 模型名称（默认: iic/SenseVoiceSmall）"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="推理设备（默认: auto）"
    )
    
    # 其他选项
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    return parser.parse_args(argv)


def resolve_output_path(audio_path: Path, output: str = None, api_format: bool = False) -> Path:
    """确定输出文件路径"""
    if output:
        return Path(output)
    
    suffix = "_api.json" if api_format else ".json"
    return audio_path.with_suffix(suffix)


def resolve_device(device: str) -> str:
    """解析设备参数"""
    if device == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    return device


def main(argv=None) -> int:
    """
    主函数
    
    Returns:
        int: 退出码，0 表示成功，非0 表示失败
    """
    args = parse_args(argv)
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # 验证输入文件
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"错误: 音频文件不存在: {audio_path}", file=sys.stderr)
        return 1
    
    if not audio_path.is_file():
        print(f"错误: 路径不是文件: {audio_path}", file=sys.stderr)
        return 1
    
    # 确定输出路径
    output_path = resolve_output_path(audio_path, args.output, args.api_format)
    
    # 配置模型
    model_dir = args.model_dir or os.environ.get("ASR_MODEL_DIR") or MODEL_DIR
    device = resolve_device(args.device)
    
    logger.info(f"音频文件: {audio_path}")
    logger.info(f"输出路径: {output_path}")
    logger.info(f"模型目录: {model_dir}")
    logger.info(f"推理设备: {device}")
    
    # 执行分析
    try:
        analyzer = SpeechAnalyzer(model_dir=model_dir)
        result = analyzer.analyze(str(audio_path))
        
        # 打印报告
        if not args.no_report:
            analyzer.print_report(result)
        
        # 导出 JSON
        if args.api_format:
            analyzer.export_api_json(result, str(output_path))
        else:
            analyzer.export_json(result, str(output_path))
        
        print(f"\n✓ 分析完成: {output_path}")
        return 0
        
    except ASRError as e:
        print(f"\n错误 [{e.code.value}]: {e.message}", file=sys.stderr)
        if e.code == ASRErrorCode.MODEL_NOT_LOADED:
            print("提示: 请检查模型是否已下载，或使用 --model-dir 指定正确路径", file=sys.stderr)
        return 2
        
    except FileNotFoundError as e:
        print(f"\n错误: 文件未找到 - {e}", file=sys.stderr)
        return 3
        
    except Exception as e:
        logger.exception("分析过程中发生未知错误")
        print(f"\n错误: {e}", file=sys.stderr)
        return 99


if __name__ == "__main__":
    sys.exit(main())