"""Uniform error envelope + request correlation.

Every non-2xx response leaves the API in the same shape, so the frontend has
exactly one error contract to handle and every log line can be tied back to the
request that produced it:

    {"error": {"code": "http_404", "message": "...", "request_id": "..."}}
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return _request_id.get()


def error_body(code: str, message: str, **extra: object) -> dict:
    body = {"error": {"code": code, "message": message, "request_id": current_request_id()}}
    if extra:
        body["error"].update(extra)  # type: ignore[union-attr]
    return body


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, time the request and emit one structured access log."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        token = _request_id.set(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            logger.exception(
                "unhandled request error",
                extra={
                    "extra_fields": {
                        "request_id": rid,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration, 1),
                    }
                },
            )
            _request_id.reset(token)
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "internal_error", "message": "Internal server error", "request_id": rid}},
                headers={REQUEST_ID_HEADER: rid},
            )
        duration = (time.perf_counter() - start) * 1000
        response.headers[REQUEST_ID_HEADER] = rid
        response.headers["Server-Timing"] = f"app;dur={duration:.1f}"
        logger.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration, 1),
                }
            },
        )
        _request_id.reset(token)
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(f"http_{exc.status_code}", detail),
            headers={REQUEST_ID_HEADER: current_request_id()},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        fields = [
            {"field": ".".join(str(p) for p in err.get("loc", ())[1:]), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Die Eingaben sind unvollständig oder ungültig.", fields=fields),
            headers={REQUEST_ID_HEADER: current_request_id()},
        )
