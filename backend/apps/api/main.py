from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.api.core.auth import require_bearer_auth
from apps.api.core.config import settings
from apps.api.core.response import err_payload
from apps.api.middleware.trace import TraceIDMiddleware
from apps.api.routers import admin, annotation, asr, evaluation, health, nlp, safety, scaffold, sessions
from libs.schemas.base import ErrorCode

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(TraceIDMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=err_payload(
            request,
            code=ErrorCode.INVALID_ARGUMENT.value,
            message="Request validation failed",
            detail={"errors": exc.errors()},
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = ErrorCode.INTERNAL.value
    if exc.status_code == 404:
        code = ErrorCode.NOT_FOUND.value
    elif exc.status_code == 400:
        code = ErrorCode.INVALID_ARGUMENT.value
    elif exc.status_code == 401:
        code = ErrorCode.UNAUTHORIZED.value
    elif exc.status_code == 409:
        code = ErrorCode.CONFLICT.value

    detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    return JSONResponse(
        status_code=exc.status_code,
        content=err_payload(request=request, code=code, message=str(exc.detail), detail=detail),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=err_payload(
            request,
            code=ErrorCode.INTERNAL.value,
            message="Internal server error",
            detail={"type": exc.__class__.__name__},
        ),
    )


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(
    sessions.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    asr.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    nlp.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    safety.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    scaffold.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    evaluation.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    admin.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
app.include_router(
    annotation.router,
    prefix=settings.api_prefix,
    dependencies=[Depends(require_bearer_auth)],
)
