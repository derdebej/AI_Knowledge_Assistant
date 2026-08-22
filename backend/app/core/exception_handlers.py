"""Maps domain exceptions to HTTP responses. See specs/API.md §5 and
specs/ARCHITECTURE.md §2.1 - services/domain code never raises `HTTPException`,
this is the one place that translation happens.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    ConversationNotFoundError,
    DocumentNotFoundError,
    DocumentOwnershipError,
    EmailAlreadyRegisteredError,
    FileTooLargeError,
    InvalidCredentialsError,
    UnsupportedFileTypeError,
)

_HANDLED_EXCEPTIONS: dict[type[Exception], tuple[int, str]] = {
    UnsupportedFileTypeError: (status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_FILE_TYPE"),
    FileTooLargeError: (status.HTTP_413_CONTENT_TOO_LARGE, "FILE_TOO_LARGE"),
    DocumentNotFoundError: (status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND"),
    ConversationNotFoundError: (status.HTTP_404_NOT_FOUND, "CONVERSATION_NOT_FOUND"),
    DocumentOwnershipError: (status.HTTP_400_BAD_REQUEST, "INVALID_DOCUMENT_SCOPE"),
    EmailAlreadyRegisteredError: (status.HTTP_409_CONFLICT, "EMAIL_ALREADY_REGISTERED"),
    InvalidCredentialsError: (status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS"),
}


def _make_handler(
    status_code: int, error_code: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "error_code": error_code},
        )

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, (http_status, error_code) in _HANDLED_EXCEPTIONS.items():
        app.add_exception_handler(exc_type, _make_handler(http_status, error_code))
