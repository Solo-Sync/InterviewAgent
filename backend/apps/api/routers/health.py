from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from apps.api.core.config import settings
from apps.api.core.response import ok
from libs.llm_gateway.client import LLMGateway
from libs.observability import render_metrics
from libs.readiness import ReadinessProbe
from libs.schemas.api import ApiResponseHealth
from services.asr.engine import FunASREngine

router = APIRouter(tags=["system"])


def _get_llm_readiness() -> ReadinessProbe:
    return LLMGateway().readiness()


def _get_asr_readiness() -> ReadinessProbe:
    return FunASREngine().readiness()


def _overall_status(*probes: ReadinessProbe) -> str:
    statuses = {probe.status for probe in probes}
    if statuses == {"ready"}:
        return "ready"
    if statuses == {"not_configured"}:
        return "not_configured"
    if statuses == {"unavailable"}:
        return "unavailable"
    return "degraded"


@router.get("/health", response_model=ApiResponseHealth)
def health(request: Request):
    llm = _get_llm_readiness()
    asr = _get_asr_readiness()
    return ok(
        request,
        {
            "service": "metacog-interview",
            "version": settings.app_version,
            "status": _overall_status(llm, asr),
            "llm_ready": llm.ready,
            "asr_ready": asr.ready,
            "llm_status": llm.status,
            "asr_status": asr.status,
            "llm_detail": llm.detail,
            "asr_detail": asr.detail,
        },
    )


@router.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
