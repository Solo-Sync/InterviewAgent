import logging
from time import perf_counter

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.core.response import err_payload
from libs.schemas.base import ErrorCode
from libs.observability import (
    log_event,
    new_trace_id,
    observe_http_request,
    reset_trace_id,
    set_trace_id,
)


logger = logging.getLogger(__name__)


class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("x-trace-id") or new_trace_id()
        token = set_trace_id(trace_id)
        request.state.trace_id = trace_id
        start = perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                route = request.scope.get("route")
                route_path = getattr(route, "path", request.url.path)
                logger.exception(
                    "Unhandled exception",
                    extra={
                        "event_type": "unhandled_exception",
                        "method": request.method,
                        "path": route_path,
                        "status_code": 500,
                    },
                )
                response = JSONResponse(
                    status_code=500,
                    content=err_payload(
                        request,
                        code=ErrorCode.INTERNAL.value,
                        message="Internal server error",
                        detail={"type": "UnhandledException"},
                    ),
                )
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            duration_seconds = perf_counter() - start
            observe_http_request(
                method=request.method,
                path=route_path,
                status_code=response.status_code,
                duration_seconds=duration_seconds,
            )
            log_event(
                logger,
                logging.INFO,
                "request_completed",
                method=request.method,
                path=route_path,
                status_code=response.status_code,
                latency_ms=round(duration_seconds * 1000, 3),
            )
            response.headers["x-trace-id"] = trace_id
            return response
        finally:
            reset_trace_id(token)
