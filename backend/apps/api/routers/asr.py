from fastapi import APIRouter, File, Form, Request, UploadFile

from apps.api.core.response import err_response, ok
from libs.schemas.api import ApiResponseAsrTranscribe
from libs.schemas.base import ErrorCode
from services.asr import ASRErrorCode, ASRService, ASRServiceError

router = APIRouter(tags=["asr"])
asr_service = ASRService()


@router.post("/asr/transcribe", response_model=ApiResponseAsrTranscribe)
async def transcribe(
    request: Request,
    audio_file: UploadFile = File(...),
    language: str = Form(default="zh"),
    need_word_timestamps: bool = Form(default=True),
):
    content = await audio_file.read()
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
            filename=audio_file.filename or "unknown",
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
