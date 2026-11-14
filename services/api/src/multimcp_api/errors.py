"""HTTP error envelope from SPEC §6.2. Never includes tracebacks or secrets."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from multimcp.models import SCHEMA_VERSION

logger = logging.getLogger("multimcp_api")

ErrorCode = Literal[
    "unauthorized",
    "validation_error",
    "not_found",
    "payload_too_large",
    "storage_unavailable",
    "internal_error",
]


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        *,
        details: list[Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


def error_body(code: ErrorCode, message: str, details: list[Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
    }


class CatchUnhandledMiddleware(BaseHTTPMiddleware):
    """Turn unexpected exceptions into the SPEC envelope without a traceback."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except AppError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=error_body(exc.code, exc.message, exc.details),
            )
        except Exception:
            logger.exception("unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content=error_body("internal_error", "internal server error"),
            )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_middleware(CatchUnhandledMiddleware)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error",
                "request validation failed",
                details=list(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code: ErrorCode
        if exc.status_code == 401:
            code = "unauthorized"
        elif exc.status_code == 404:
            code = "not_found"
        elif exc.status_code == 413:
            code = "payload_too_large"
        elif exc.status_code == 503:
            code = "storage_unavailable"
        else:
            code = "internal_error"
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
        )
