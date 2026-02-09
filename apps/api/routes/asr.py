from fastapi import APIRouter, File, Form, Request, UploadFile

from apps.api.response import err_response, ok

router = APIRouter(tags=["asr"])


@router.post("/asr/transcribe")
async def transcribe(
    request: Request,
    audio_file: UploadFile = File(...),
    language: str = Form(default="zh"),
    need_word_timestamps: bool = Form(default=True),
):
    content = await audio_file.read()
    if len(content) > 20 * 1024 * 1024:
        return err_response(
            request,
            status_code=413,
            code="INVALID_ARGUMENT",
            message="payload too large",
            detail={"max_bytes": 20 * 1024 * 1024},
        )
    asr_payload = {
        "raw_text": "",
        "tokens": [] if need_word_timestamps else None,
        "silence_segments": [],
        "audio_features": {"language": language, "filename": audio_file.filename},
    }
    return ok(request, {"asr": asr_payload})
