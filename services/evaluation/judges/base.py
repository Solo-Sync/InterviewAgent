from dataclasses import dataclass


@dataclass
class JudgeVote:
    judge_id: str
    scores: dict
    confidence: float
    rationale: str
