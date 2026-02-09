from fastapi import APIRouter, Request

from apps.api.config import settings
from apps.api.response import ok

router = APIRouter(tags=["system"])


@router.get("/health")
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
