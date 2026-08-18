"""The one safe error envelope for `/api/v1`.

Every error response takes the shape:

    {"error": {"code", "message", "request_id", "retryable"}}

Provider exceptions, prompts, tokens, resumes, job descriptions, and answers
never appear in these responses.
"""
import logging
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("backend.api_v1")

_DEFAULT_CODES_BY_STATUS = {
    status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
}


class ApiError(Exception):
    """A domain error rendered through the safe `/api/v1` error envelope."""

    def __init__(self, code: str, message: str, status_code: int, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{uuid4().hex[:12]}"


def _envelope(code: str, message: str, request_id: str, retryable: bool) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "retryable": retryable,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    """Register the request-id middleware and safe-envelope exception handlers."""

    @app.middleware("http")
    async def _stamp_request_id(request: Request, call_next):
        request.state.request_id = f"req_{uuid4().hex[:12]}"
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, _request_id(request), exc.retryable),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _DEFAULT_CODES_BY_STATUS.get(exc.status_code, "INTERNAL")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), _request_id(request), retryable=False),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "VALIDATION_ERROR",
                "The request body did not match the expected shape.",
                _request_id(request),
                retryable=False,
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Any bug here would otherwise fall through to a bare, envelope-less
        # 500. Log the exception type/traceback (never request content) so
        # it stays diagnosable, and still answer with the one safe envelope.
        request_id = _request_id(request)
        logger.exception("Unhandled error on %s %s [%s]", request.method, request.url.path, request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "INTERNAL",
                "Something went wrong. Please try again.",
                request_id,
                retryable=False,
            ),
        )
