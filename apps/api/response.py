from fastapi import Request
from fastapi.responses import JSONResponse

from libs.schemas.base import ApiError


def ok(request: Request, data: dict) -> dict:
    return {"ok": True, "data": data, "error": None, "trace_id": request.state.trace_id}


def err_payload(request: Request, code: str, message: str, detail: dict | None = None) -> dict:
    error = ApiError(code=code, message=message, detail=detail)
    return {"ok": False, "data": None, "error": error.model_dump(), "trace_id": request.state.trace_id}


def err_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    detail: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=err_payload(request=request, code=code, message=message, detail=detail),
    )
