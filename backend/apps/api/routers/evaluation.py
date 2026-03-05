from fastapi import APIRouter, Request

from apps.api.core.response import err_response, ok
from libs.schemas.api import (
    ApiResponseEvaluationBatch,
    ApiResponseEvaluationScore,
    EvaluationBatchRequest,
    EvaluationScoreRequest,
)
from services.evaluation.aggregator import ScoreAggregator

router = APIRouter(tags=["evaluation"])
aggregator = ScoreAggregator()


@router.post("/evaluation/score", response_model=ApiResponseEvaluationScore)
def score(request: Request, body: EvaluationScoreRequest):
    try:
        scaffold_level = None
        if body.scaffold_used and body.scaffold_used.used:
            scaffold_level = body.scaffold_used.level
        result = aggregator.score(
            body.answer_clean_text,
            question=body.question,
            features=body.features,
            scaffold_level=scaffold_level,
        )
    except Exception as exc:  # noqa: BLE001
        return err_response(
            request,
            status_code=502,
            code="INTERNAL",
            message="LLM upstream error",
            detail={"type": exc.__class__.__name__},
        )
    return ok(request, {"evaluation": result.model_dump()})


@router.post("/evaluation/batch_score", response_model=ApiResponseEvaluationBatch)
def batch_score(request: Request, body: EvaluationBatchRequest):
    try:
        results = []
        for item in body.items:
            scaffold_level = None
            if item.scaffold_used and item.scaffold_used.used:
                scaffold_level = item.scaffold_used.level
            results.append(
                aggregator.score(
                    item.answer_clean_text,
                    question=item.question,
                    features=item.features,
                    scaffold_level=scaffold_level,
                )
            )
    except Exception as exc:  # noqa: BLE001
        return err_response(
            request,
            status_code=502,
            code="INTERNAL",
            message="LLM upstream error",
            detail={"type": exc.__class__.__name__},
        )
    return ok(
        request,
        {
            "items": [result.model_dump() for result in results],
            "stats": {"count": len(results)},
        },
    )
