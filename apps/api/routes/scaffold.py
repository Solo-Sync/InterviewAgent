from fastapi import APIRouter, Request

from apps.api.response import ok
from libs.schemas.api import ScaffoldGenerateRequest
from services.scaffold.generator import ScaffoldGenerator

router = APIRouter(tags=["scaffold"])
generator = ScaffoldGenerator()


@router.post("/scaffold/generate")
def generate(request: Request, body: ScaffoldGenerateRequest):
    context = {
        "task": body.task.model_dump(),
        "candidate_last_answer": body.candidate_last_answer,
        "error_type": body.error_type.value,
        "state": body.state.value,
    }
    result = generator.generate(body.level, context)
    return ok(request, {"scaffold": result.model_dump()})
