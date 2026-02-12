from fastapi import APIRouter, Query, Request

from apps.api.response import err_response, ok
from libs.schemas.base import ErrorCode
from services.asr import ASRErrorCode, ASRService, ASRServiceError

router = APIRouter(tags=["asr"])
asr_service = ASRService()


@router.post("/asr/transcribe")
async def transcribe(
    request: Request,
    language: str = Query(default="zh"),
    need_word_timestamps: bool = Query(default=True),
):
    content = await request.body()
    if not content:
        return err_response(
            request,
            status_code=400,
            code=ErrorCode.INVALID_ARGUMENT.value,
            message="empty audio payload",
        )
    if len(content) > 20 * 1024 * 1024:
        return err_response(
            request,
            status_code=413,
            code=ErrorCode.INVALID_ARGUMENT.value,
            message="payload too large",
            detail={"max_bytes": 20 * 1024 * 1024},
        )
    try:
        asr_payload = asr_service.transcribe(
            audio_bytes=content,
            filename=request.headers.get("x-audio-filename", "unknown"),
            language=language,
            need_word_timestamps=need_word_timestamps,
        )
    except ASRServiceError as exc:
        if exc.code == ASRErrorCode.INVALID_INPUT:
            return err_response(
                request,
                status_code=400,
                code=ErrorCode.INVALID_ARGUMENT.value,
                message=str(exc),
            )
        if exc.code == ASRErrorCode.MODEL_NOT_READY:
            return err_response(
                request,
                status_code=503,
                code=ErrorCode.INTERNAL.value,
                message=str(exc),
                detail={"hint": "Install funasr and model dependencies."},
            )
        return err_response(
            request,
            status_code=500,
            code=ErrorCode.INTERNAL.value,
            message=str(exc),
        )

    return ok(request, {"asr": asr_payload.model_dump()})
