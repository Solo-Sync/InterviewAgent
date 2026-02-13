"""
数据模型定义
根据openapi.yaml中的schema定义
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SessionState(str, Enum):
    """会话状态枚举"""
    S_INIT = "S_INIT"
    S_WAIT = "S_WAIT"
    S_PROBE = "S_PROBE"
    S_SCAFFOLD = "S_SCAFFOLD"
    S_EVAL_RT = "S_EVAL_RT"
    S_END = "S_END"


class NextActionType(str, Enum):
    """下一步动作类型"""
    ASK = "ASK"
    PROBE = "PROBE"
    SCAFFOLD = "SCAFFOLD"
    CALM = "CALM"
    END = "END"
    WAIT = "WAIT"


class ScaffoldLevel(str, Enum):
    """脚手架提示级别"""
    L1 = "L1"  # 温和提醒
    L2 = "L2"  # 具体方向
    L3 = "L3"  # 直接答案


class ResetType(str, Enum):
    """重置类型"""
    FULL_RESET = "full_reset"  # 完全重新开始
    PARTIAL_RESET = "partial_reset"  # 仅重新定义问题


class QuestionRef(BaseModel):
    """问题引用"""
    qid: Optional[str] = None
    text: str


class NextAction(BaseModel):
    """下一步动作"""
    type: NextActionType
    text: Optional[str] = None
    level: Optional[ScaffoldLevel] = None
    payload: Optional[Dict[str, Any]] = None


class ScaffoldResult(BaseModel):
    """脚手架结果"""
    fired: bool
    level: Optional[ScaffoldLevel] = None
    prompt: Optional[str] = None
    rationale: Optional[str] = None


class DimScores(BaseModel):
    """维度评分"""
    plan: float = Field(ge=0, le=1)  # 规划
    monitor: float = Field(ge=0, le=1)  # 监控
    evaluate: float = Field(ge=0, le=1)  # 评估
    adapt: float = Field(ge=0, le=1)  # 适应


class EvaluationResult(BaseModel):
    """评估结果"""
    scores: DimScores
    evidence: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None


class SessionContext(BaseModel):
    """会话上下文 - 状态机的状态"""
    session_id: str
    state: SessionState = SessionState.S_INIT
    current_question: Optional[QuestionRef] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    scaffold_level_used: Optional[ScaffoldLevel] = None
    silence_duration: float = 0.0  # 沉默时长(秒)
    turn_index: int = 0
    reset_type: Optional[ResetType] = None  # 异常重置类型
    metacognitive_signals: List[str] = Field(default_factory=list)  # 元认知信号记录
    evaluation_history: List[EvaluationResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

