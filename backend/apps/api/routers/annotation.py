from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.core.auth import AuthPrincipal, AuthRole, require_roles
from apps.api.core.dependencies import get_orchestrator
from apps.api.core.response import err_response, ok
from libs.schemas.api import ApiResponseAnnotationCreate, HumanAnnotationCreateRequest
from libs.schemas.base import ErrorCode
from services.orchestrator.service import OrchestratorService

router = APIRouter(tags=["annotation"])


@router.post("/sessions/{session_id}/annotations", response_model=ApiResponseAnnotationCreate)
def create_annotation(
    request: Request,
    session_id: str,
    body: HumanAnnotationCreateRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    _: AuthPrincipal = Depends(require_roles(AuthRole.ANNOTATOR)),
):
    if orchestrator.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        orchestrator.create_annotation(session_id, body)
    except ValueError as exc:
        return err_response(
            request,
            status_code=400,
            code=ErrorCode.INVALID_ARGUMENT.value,
            message=str(exc),
        )
    return ok(request, {"stored": True})
