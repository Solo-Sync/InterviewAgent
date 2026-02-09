from libs.schemas.base import DimScores, Discount, EvaluationResult, EvidenceSpan, JudgeVote


class ScoreAggregator:
    def score(self, text: str) -> EvaluationResult:
        base = min(max(len(text) // 40, 0), 3)
        score_value = float(base)
        scores = DimScores(
            plan=score_value,
            monitor=score_value,
            evaluate=float(max(base - 1, 0)),
            adapt=float(max(base - 1, 0)),
        )
        evidence = [
            EvidenceSpan(
                dimension="plan",
                quote=text[:60] or "",
                reason="Contains planning or decomposition cues.",
            )
        ]
        votes = [JudgeVote(judge_id="judge_stub", scores=scores, confidence=0.66)]
        discounts = [Discount(reason="no_scaffold_discount", dimension="monitor", multiplier=1.0)]
        return EvaluationResult(
            scores=scores,
            evidence=evidence,
            judge_votes=votes,
            final_confidence=0.66,
            discounts=discounts,
        )
