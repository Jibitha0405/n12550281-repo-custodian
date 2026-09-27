from __future__ import annotations

from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..errors import AppError


def _error_name(status_code: int) -> str:
    """Map raised exceptions to API error type names."""
    mapping = {
        400: "ValidationError",
        401: "Unauthorised",
        403: "Forbidden",
        404: "NotFound",
        409: "Conflict",
        500: "InternalError",
        501: "NotImplemented",
    }
    return mapping.get(status_code, HTTPStatus(status_code).phrase.replace(" ", ""))


def _payload(status_code: int, message: str) -> dict[str, str]:
    """Build a standardized JSON error response payload."""
    return {"error": _error_name(status_code), "message": message}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Translate HTTP exceptions into the API error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(exc.status_code, str(exc.detail)),
    )


async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Translate application errors into the API error response format."""
    if isinstance(exc, AppError):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "message": exc.message})

    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)

    return JSONResponse(
        status_code=500,
        content={"error": "InternalError", "message": str(exc)},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Translate request validation errors into the API error response format."""
    message = exc.errors()[0]["msg"] if exc.errors() else "Invalid request"
    return JSONResponse(status_code=400, content={"error": "ValidationError", "message": message})

