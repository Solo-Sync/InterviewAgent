from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    S_INIT = "S_INIT"
    S_WAIT = "S_WAIT"
    S_PROBE = "S_PROBE"
    S_SCAFFOLD = "S_SCAFFOLD"
    S_EVAL_RT = "S_EVAL_RT"
    S_END = "S_END"


class NextActionType(str, Enum):
    ASK = "ASK"
    PROBE = "PROBE"
    SCAFFOLD = "SCAFFOLD"
    CALM = "CALM"
    END = "END"
    WAIT = "WAIT"


class ScaffoldLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class TriggerType(str, Enum):
    SILENCE = "SILENCE"
    OFFTRACK = "OFFTRACK"
    LOOP = "LOOP"
    HELP_KEYWORD = "HELP_KEYWORD"
    STRESS_SIGNAL = "STRESS_SIGNAL"


class MetacogDimension(str, Enum):
    PLAN = "plan"
    MONITOR = "monitor"
    EVALUATE = "evaluate"
    ADAPT = "adapt"


class TurnInputType(str, Enum):
    TEXT = "text"
    AUDIO_REF = "audio_ref"


class SafetyCategory(str, Enum):
    OK = "OK"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    SENSITIVE = "SENSITIVE"
    OTHER = "OTHER"


class SafetyAction(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    SANITIZE = "SANITIZE"
    REPHRASE = "REPHRASE"


class SessionMode(str, Enum):
    TEXT = "text"
    AUDIO = "audio"


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    CONFLICT = "CONFLICT"
    INTERNAL = "INTERNAL"


class ApiError(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: ApiError | None = None
    trace_id: str


class Candidate(BaseModel):
    candidate_id: str
    display_name: str | None = None


class Thresholds(BaseModel):
    silence_s: float = 15
    offtrack_threshold: float = 0.7
    loop_threshold: float = 0.8


class NextAction(BaseModel):
    type: NextActionType
    text: str | None = None
    level: ScaffoldLevel | None = None
    payload: dict[str, Any] | None = None


class Trigger(BaseModel):
    type: TriggerType
    score: float = Field(ge=0, le=1)
    detail: str | None = None


class DimScores(BaseModel):
    plan: float
    monitor: float
    evaluate: float
    adapt: float


class EvidenceSpan(BaseModel):
    dimension: MetacogDimension
    quote: str
    start: int | None = None
    end: int | None = None
    reason: str


class JudgeVote(BaseModel):
    judge_id: str
    scores: DimScores
    confidence: float = Field(ge=0, le=1)


class Discount(BaseModel):
    reason: str
    dimension: MetacogDimension
    multiplier: float = Field(ge=0, le=1)


class EvaluationResult(BaseModel):
    scores: DimScores
    evidence: list[EvidenceSpan] | None = None
    judge_votes: list[JudgeVote] | None = None
    final_confidence: float | None = None
    discounts: list[Discount] | None = None


class ScaffoldResult(BaseModel):
    fired: bool
    level: ScaffoldLevel | None = None
    prompt: str | None = None
    rationale: str | None = None


class QuestionRef(BaseModel):
    qid: str | None = None
    text: str | None = None


class TurnInput(BaseModel):
    type: TurnInputType
    text: str | None = None
    audio_url: str | None = None
    audio_id: str | None = None


class ClientMeta(BaseModel):
    client_timestamp: datetime | None = None
    client_platform: str | None = None


class AsrToken(BaseModel):
    token: str
    start_ms: int
    end_ms: int


class SilenceSegment(BaseModel):
    start_ms: int
    end_ms: int


class AsrResult(BaseModel):
    raw_text: str
    tokens: list[AsrToken] | None = None
    silence_segments: list[SilenceSegment] | None = None
    audio_features: dict[str, Any] | None = None


class PreprocessResult(BaseModel):
    clean_text: str
    filler_stats: dict[str, int] | None = None
    hesitation_rate: float | None = None


class Turn(BaseModel):
    turn_id: str
    turn_index: int
    state_before: SessionState
    state_after: SessionState
    question: QuestionRef | None = None
    input: TurnInput
    asr: AsrResult | None = None
    preprocess: PreprocessResult | None = None
    triggers: list[Trigger] | None = None
    scaffold: ScaffoldResult | None = None
    evaluation: EvaluationResult | None = None
    next_action: NextAction | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Session(BaseModel):
    session_id: str
    candidate: Candidate | None = None
    mode: SessionMode
    state: SessionState
    question_set_id: str
    scoring_policy_id: str
    scaffold_policy_id: str
    thresholds: Thresholds | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportPoint(BaseModel):
    turn_index: int
    scores: DimScores


class Report(BaseModel):
    overall: DimScores
    timeline: list[ReportPoint]
    notes: list[str] | None = None
