from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

from libs.schemas.base import (
    ApiError,
    AsrResult,
    Candidate,
    ClientMeta,
    DimScores,
    EvaluationResult,
    EvidenceSpan,
    PreprocessResult,
    NextAction,
    Report,
    SafetyAction,
    SafetyCategory,
    ScaffoldLevel,
    ScaffoldResult,
    Session,
    SessionMode,
    SessionReviewStatus,
    SessionState,
    Thresholds,
    Trigger,
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
    triggers: list[Trigger] | None = None
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
    asr: AsrResult


class PreprocessData(BaseModel):
    preprocess: PreprocessResult


class ScaffoldGenerateData(BaseModel):
    scaffold: ScaffoldResult


class EvaluationScoreData(BaseModel):
    evaluation: EvaluationResult


class EvaluationBatchData(BaseModel):
    items: list[EvaluationResult]
    stats: dict[str, Any] | None = None


class SafetyCheckData(BaseModel):
    is_safe: bool
    category: SafetyCategory
    action: SafetyAction
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


class AdminSessionSummary(BaseModel):
    session: Session
    turn_count: int
    report: Report | None = None
    review_status: SessionReviewStatus
    prompt_injection_count: int = 0
    invalid_reason: str | None = None


class AdminSessionDetailData(BaseModel):
    session: Session
    turns: list[Turn]
    report: Report | None = None
    opening_prompt: str | None = None
    review_status: SessionReviewStatus
    prompt_injection_count: int = 0
    invalid_reason: str | None = None


class AdminSessionListData(BaseModel):
    items: list[AdminSessionSummary]


class HealthData(BaseModel):
    service: str
    version: str
    status: Literal["ready", "degraded", "not_configured", "unavailable"]
    llm_ready: bool
    asr_ready: bool
    llm_status: Literal["ready", "degraded", "not_configured", "unavailable"]
    asr_status: Literal["ready", "degraded", "not_configured", "unavailable"]
    llm_detail: str | None = None
    asr_detail: str | None = None


class AsrTranscribeRequest(BaseModel):
    language: str = "zh"
    need_word_timestamps: bool = True


class CursorEnvelope(BaseModel):
    offset: int
    ts: datetime | None = None


class ApiResponseError(BaseModel):
    ok: bool
    data: None = None
    error: ApiError
    trace_id: str


class _ApiResponseSuccessBase(BaseModel):
    ok: bool
    error: ApiError | None = None
    trace_id: str


class ApiResponseHealth(_ApiResponseSuccessBase):
    data: HealthData


class ApiResponseSessionCreate(_ApiResponseSuccessBase):
    data: SessionCreateData


class ApiResponseSessionGet(_ApiResponseSuccessBase):
    data: SessionGetData


class ApiResponseTurnCreate(_ApiResponseSuccessBase):
    data: TurnCreateData


class ApiResponseTurnList(_ApiResponseSuccessBase):
    data: TurnListData


class ApiResponseSessionEnd(_ApiResponseSuccessBase):
    data: SessionEndData


class ApiResponseReportGet(_ApiResponseSuccessBase):
    data: ReportGetData


class ApiResponseAsrTranscribe(_ApiResponseSuccessBase):
    data: AsrTranscribeData


class ApiResponsePreprocess(_ApiResponseSuccessBase):
    data: PreprocessData


class ApiResponseScaffoldGenerate(_ApiResponseSuccessBase):
    data: ScaffoldGenerateData


class ApiResponseEvaluationScore(_ApiResponseSuccessBase):
    data: EvaluationScoreData


class ApiResponseEvaluationBatch(_ApiResponseSuccessBase):
    data: EvaluationBatchData


class ApiResponseSafetyCheck(_ApiResponseSuccessBase):
    data: SafetyCheckData


class ApiResponseAnnotationCreate(_ApiResponseSuccessBase):
    data: AnnotationCreateData


class ApiResponseQuestionSetList(_ApiResponseSuccessBase):
    data: QuestionSetListData


class ApiResponseQuestionSetGet(_ApiResponseSuccessBase):
    data: QuestionSetGetData


class ApiResponseRubricList(_ApiResponseSuccessBase):
    data: RubricListData


class ApiResponseRubricGet(_ApiResponseSuccessBase):
    data: RubricGetData


class ApiResponseAdminSessionList(_ApiResponseSuccessBase):
    data: AdminSessionListData


class ApiResponseAdminSessionDetail(_ApiResponseSuccessBase):
    data: AdminSessionDetailData
