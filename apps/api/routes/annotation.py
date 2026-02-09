from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.dependencies import get_orchestrator
from apps.api.response import ok
from libs.schemas.api import HumanAnnotationCreateRequest
from services.orchestrator.service import OrchestratorService

router = APIRouter(tags=["annotation"])
ANNOTATIONS: list[dict] = []


@router.post("/sessions/{session_id}/annotations")
def create_annotation(
    request: Request,
    session_id: str,
    body: HumanAnnotationCreateRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    if orchestrator.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    payload = {"session_id": session_id, **body.model_dump()}
    ANNOTATIONS.append(payload)
    return ok(request, {"stored": True})
