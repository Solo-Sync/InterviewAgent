from fastapi import APIRouter, Request

from apps.api.core.config import settings
from apps.api.core.response import ok
from libs.schemas.api import ApiResponseHealth

router = APIRouter(tags=["system"])


@router.get("/health", response_model=ApiResponseHealth)
def health(request: Request):
    return ok(
        request,
        {
            "service": "metacog-interview",
            "version": settings.app_version,
            "llm_ready": True,
            "asr_ready": True,
        },
    )
