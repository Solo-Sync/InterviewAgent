from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from libs.schemas.base import (
    Candidate,
    ClientMeta,
    DimScores,
    EvaluationResult,
    EvidenceSpan,
    NextAction,
    Report,
    ScaffoldLevel,
    ScaffoldResult,
    Session,
    SessionMode,
    SessionState,
    Thresholds,
    Turn,
    TurnInput,
)


class SessionCreateRequest(BaseModel):
    candidate: Candidate
    mode: SessionMode
    question_set_id: str
    scoring_policy_id: str
    scaffold_policy_id: str
    thresholds: Thresholds | None = None


class TurnCreateRequest(BaseModel):
    input: TurnInput
    client_meta: ClientMeta | None = None


class SessionEndReason(str, Enum):
    COMPLETED = "completed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


class SessionEndRequest(BaseModel):
    reason: SessionEndReason


class PreprocessRequest(BaseModel):
    text: str


class TaskRef(BaseModel):
    question: str
    qid: str | None = None


class ScaffoldErrorType(str, Enum):
    STUCK = "STUCK"
    OFFTRACK = "OFFTRACK"
    LOOP = "LOOP"
    FACT_ERROR = "FACT_ERROR"
    HIGH_STRESS = "HIGH_STRESS"


class ScaffoldGenerateRequest(BaseModel):
    level: ScaffoldLevel
    task: TaskRef
    candidate_last_answer: str
    error_type: ScaffoldErrorType
    state: SessionState


class ScaffoldUsed(BaseModel):
    used: bool
    level: ScaffoldLevel | None = None


class EvaluationScoreRequest(BaseModel):
    rubric_id: str
    question: str
    answer_clean_text: str
    features: dict[str, Any] | None = None
    scaffold_used: ScaffoldUsed | None = None


class EvaluationBatchRequest(BaseModel):
    items: list[EvaluationScoreRequest]


class SafetyCheckRequest(BaseModel):
    text: str


class HumanAnnotationCreateRequest(BaseModel):
    turn_id: str
    human_scores: DimScores
    notes: str | None = None
    evidence: list[EvidenceSpan] | None = None


class SessionCreateData(BaseModel):
    session: Session
    next_action: NextAction


class SessionGetData(BaseModel):
    session: Session
    last_next_action: NextAction | None = None


class TurnCreateData(BaseModel):
    turn: Turn
    next_action: NextAction
    triggers: list | None = None
    scaffold: ScaffoldResult | None = None
    evaluation: EvaluationResult | None = None


class TurnListData(BaseModel):
    items: list[Turn]
    next_cursor: str | None


class SessionEndData(BaseModel):
    report: Report


class ReportGetData(BaseModel):
    report: Report


class AsrTranscribeData(BaseModel):
    asr: dict


class PreprocessData(BaseModel):
    preprocess: dict


class ScaffoldGenerateData(BaseModel):
    scaffold: ScaffoldResult


class EvaluationScoreData(BaseModel):
    evaluation: EvaluationResult


class EvaluationBatchData(BaseModel):
    items: list[EvaluationResult]
    stats: dict[str, Any] | None = None


class SafetyCheckData(BaseModel):
    is_safe: bool
    category: str
    action: str
    sanitized_text: str | None = None


class AnnotationCreateData(BaseModel):
    stored: bool


class QuestionSetSummary(BaseModel):
    question_set_id: str
    title: str
    description: str | None = None


class QuestionSetDetail(BaseModel):
    question_set_id: str
    title: str
    description: str | None = None
    questions: list[dict[str, Any]]


class RubricSummary(BaseModel):
    rubric_id: str
    title: str
    description: str | None = None


class RubricDetail(BaseModel):
    rubric_id: str
    title: str
    description: str | None = None
    scale: dict[str, Any]


class QuestionSetListData(BaseModel):
    items: list[QuestionSetSummary]


class QuestionSetGetData(BaseModel):
    question_set: QuestionSetDetail


class RubricListData(BaseModel):
    items: list[RubricSummary]


class RubricGetData(BaseModel):
    rubric: RubricDetail


class HealthData(BaseModel):
    service: str
    version: str
    llm_ready: bool
    asr_ready: bool


class AsrTranscribeRequest(BaseModel):
    language: str = "zh"
    need_word_timestamps: bool = True


class CursorEnvelope(BaseModel):
    offset: int
    ts: datetime | None = None
