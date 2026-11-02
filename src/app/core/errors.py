from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class BadRequestError(AppError):
    """400 Bad Request."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    """401 Unauthorized."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    """403 Forbidden."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class NotFoundError(AppError):
    """404 Not Found."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    """409 Conflict."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class PayloadTooLargeError(AppError):
    """413 Payload Too Large."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "PAYLOAD_TOO_LARGE"


def _error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    """Build standardized error body for JSON responses."""
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Convert any `AppError` into a standardized JSON response."""
    if isinstance(exc, AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message),
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload("INTERNAL_ERROR", "Internal server error."),
    )


async def validation_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Convert Pydantic/FastAPI 422 validation errors into the unified error format."""
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        first_msg = errors[0].get("msg", "Validation error") if errors else "Validation error"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload("VALIDATION_ERROR", str(first_msg)),
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_error_payload("VALIDATION_ERROR", "Invalid request payload."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register unified exception handlers on the FastAPI application."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
