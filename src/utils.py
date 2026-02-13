"""
工具函数
包括异常处理、文本预处理等
"""
import re
from typing import List, Dict, Any, Optional


def detect_hesitation(text: str) -> float:
    """
    检测犹豫度
    
    Args:
        text: 文本
        
    Returns:
        犹豫度分数 (0.0-1.0)
    """
    hesitation_words = [
        "嗯", "呃", "那个", "这个", "就是", "然后",
        "um", "uh", "like", "you know"
    ]
    
    words = text.split()
    if not words:
        return 0.0
    
    hesitation_count = sum(1 for word in words if any(hw in word.lower() for hw in hesitation_words))
    return min(hesitation_count / len(words), 1.0)


def clean_text(text: str) -> str:
    """
    清理文本
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 移除多余的空白
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    return text


def detect_silence_keywords(text: str) -> bool:
    """
    检测是否包含沉默/卡顿相关的关键词
    
    Args:
        text: 文本
        
    Returns:
        是否检测到沉默信号
    """
    silence_keywords = [
        "我不明白", "我不懂", "我不知道", "我不会",
        "卡住了", "想不出来", "不知道怎么说"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in silence_keywords)


def detect_confusion_keywords(text: str) -> bool:
    """
    检测是否包含困惑相关的关键词
    
    Args:
        text: 文本
        
    Returns:
        是否检测到困惑信号
    """
    confusion_keywords = [
        "搞错了", "理解错了", "我错了", "不对",
        "重新来", "重新思考"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in confusion_keywords)


def calculate_speech_rate(text: str, duration_seconds: float) -> float:
    """
    计算语速(字/分钟)
    
    Args:
        text: 文本
        duration_seconds: 持续时间(秒)
        
    Returns:
        语速(字/分钟)
    """
    if duration_seconds <= 0:
        return 0.0
    
    char_count = len(text)
    minutes = duration_seconds / 60.0
    return char_count / minutes if minutes > 0 else 0.0


def extract_filler_words(text: str) -> Dict[str, int]:
    """
    提取填充词统计
    
    Args:
        text: 文本
        
    Returns:
        填充词统计字典
    """
    fillers = {
        "嗯": 0, "呃": 0, "那个": 0, "这个": 0,
        "就是": 0, "然后": 0, "um": 0, "uh": 0
    }
    
    text_lower = text.lower()
    for filler in fillers.keys():
        fillers[filler] = text_lower.count(filler)
    
    return fillers


def determine_error_type(
    student_answer: str,
    silence_duration: float,
    hesitation_rate: float
) -> str:
    """
    确定错误类型
    
    Args:
        student_answer: 学生回答
        silence_duration: 沉默时长
        hesitation_rate: 犹豫度
        
    Returns:
        错误类型
    """
    # 检测沉默
    if silence_duration > 10.0 or not student_answer.strip():
        return "STUCK"
    
    # 检测偏离
    if detect_confusion_keywords(student_answer):
        return "OFFTRACK"
    
    # 检测高压力
    if hesitation_rate > 0.3:
        return "HIGH_STRESS"
    
    # 默认
    return "STUCK"


def should_trigger_scaffold(
    silence_duration: float,
    hesitation_rate: float,
    student_answer: str,
    threshold_silence: float = 10.0
) -> bool:
    """
    判断是否应该触发脚手架提示
    
    Args:
        silence_duration: 沉默时长
        hesitation_rate: 犹豫度
        student_answer: 学生回答
        threshold_silence: 沉默阈值(秒)
        
    Returns:
        是否应该触发脚手架
    """
    # 沉默超过阈值
    if silence_duration > threshold_silence:
        return True
    
    # 回答为空
    if not student_answer or not student_answer.strip():
        return True
    
    # 检测到沉默关键词
    if detect_silence_keywords(student_answer):
        return True
    
    # 犹豫度过高
    if hesitation_rate > 0.4:
        return True
    
    return False


def determine_scaffold_level(
    silence_duration: float,
    scaffold_level_used: Optional[str],
    consecutive_failures: int = 0
) -> str:
    """
    确定脚手架级别
    
    Args:
        silence_duration: 沉默时长
        scaffold_level_used: 已使用的脚手架级别
        consecutive_failures: 连续失败次数
        
    Returns:
        脚手架级别 (L1/L2/L3)
    """
    # 如果已经使用过L3,不再升级
    if scaffold_level_used == "L3":
        return "L3"
    
    # 根据沉默时长和失败次数决定级别
    if silence_duration > 20.0 or consecutive_failures >= 2:
        return "L3"
    elif silence_duration > 15.0 or consecutive_failures >= 1:
        return "L2"
    else:
        return "L1"

