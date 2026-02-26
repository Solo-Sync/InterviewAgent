from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.core.dependencies import get_orchestrator
from apps.api.core.response import ok
from libs.schemas.api import ApiResponseAnnotationCreate, HumanAnnotationCreateRequest
from services.orchestrator.service import OrchestratorService

router = APIRouter(tags=["annotation"])


@router.post("/sessions/{session_id}/annotations", response_model=ApiResponseAnnotationCreate)
def create_annotation(
    request: Request,
    session_id: str,
    body: HumanAnnotationCreateRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    if orchestrator.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    orchestrator.create_annotation(session_id, body)
    return ok(request, {"stored": True})
