"""Unified public error contract (P0 security line B).

Before this module the API echoed internal exception text straight back to
clients via ``detail=str(e)``. That leaked database messages, filesystem
paths and third-party SDK payloads to anyone who could reach the endpoint.

Design
------
* Every error that reaches a client is rendered through :func:`error_response`
  so the wire format is identical regardless of the raiser.
* Raw exceptions are only ever written to the server log, correlated by the
  per-request id carried in ``X-Request-ID``.
* Unknown exceptions collapse to ``INTERNAL_ERROR`` with a fixed public
  message; the cause never crosses the process boundary.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# Public, stable error codes. These are part of the API contract: clients may
# branch on them, so renaming one is a breaking change.
AUTH_REQUIRED = "AUTH_REQUIRED"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
CONFLICT = "CONFLICT"
DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
INTERNAL_ERROR = "INTERNAL_ERROR"

_PUBLIC_MESSAGES = {
    AUTH_REQUIRED: "Authentication credentials were not provided.",
    FORBIDDEN: "You do not have access to this resource.",
    NOT_FOUND: "Resource not found.",
    VALIDATION_ERROR: "The request payload is invalid.",
    CONFLICT: "The request conflicts with the current state.",
    DEPENDENCY_FAILURE: "A downstream dependency failed.",
    INTERNAL_ERROR: "Internal server error.",
}

_DEFAULT_STATUS = {
    AUTH_REQUIRED: status.HTTP_401_UNAUTHORIZED,
    FORBIDDEN: status.HTTP_403_FORBIDDEN,
    NOT_FOUND: status.HTTP_404_NOT_FOUND,
    VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_CONTENT,
    CONFLICT: status.HTTP_409_CONFLICT,
    DEPENDENCY_FAILURE: status.HTTP_503_SERVICE_UNAVAILABLE,
    INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class AppError(Exception):
    """An error whose public code and message are safe to expose.

    Use this for expected business failures. Anything else should propagate as
    a normal exception and be collapsed to ``INTERNAL_ERROR``.
    """

    def __init__(
        self,
        code: str = INTERNAL_ERROR,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        headers: Optional[dict] = None,
    ) -> None:
        self.code = code
        self.message = message or _PUBLIC_MESSAGES.get(code, _PUBLIC_MESSAGES[INTERNAL_ERROR])
        self.status_code = status_code or _DEFAULT_STATUS.get(code, 500)
        self.headers = headers
        super().__init__(self.message)


def get_request_id(request: Optional[Request]) -> str:
    """Return the request id, tolerating non-HTTP callers."""
    if request is None:
        return str(uuid.uuid4())
    existing = getattr(request.state, "request_id", None)
    return existing or str(uuid.uuid4())


def error_payload(code: str, message: str, request_id: str) -> dict[str, Any]:
    """Build the single response shape used for every error path."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        },
        # ``detail`` is retained so existing clients that read FastAPI's
        # default field keep working during the transition.
        "detail": message,
    }


def error_response(
    request_id: str,
    code: str,
    message: str,
    status_code: int,
    headers: Optional[dict] = None,
) -> JSONResponse:
    # The request id is set on the error response itself, not only by
    # ``RequestIdMiddleware``: when an unhandled exception is converted into a
    # response by the application-level handler, the middleware may not get a
    # chance to add the header. Setting it here guarantees the client can always
    # quote an id that appears in the server log.
    response = JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, request_id),
    )
    if headers:
        for key, value in headers.items():
            if key.lower() != REQUEST_ID_HEADER.lower():
                response.headers[key] = value
    # Trusted value last: it wins over any caller-supplied header.
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def log_internal_error(request_id: str, request: Optional[Request], exc: BaseException) -> None:
    """Record the full cause server-side, including the traceback."""
    path = getattr(getattr(request, "url", None), "path", None)
    logger.exception(
        "UNHANDLED_ERROR request_id=%s path=%s exc_type=%s",
        request_id,
        path,
        type(exc).__name__,
    )


__all__ = [
    "AppError",
    "AUTH_REQUIRED",
    "CONFLICT",
    "DEPENDENCY_FAILURE",
    "FORBIDDEN",
    "INTERNAL_ERROR",
    "NOT_FOUND",
    "REQUEST_ID_HEADER",
    "VALIDATION_ERROR",
    "error_payload",
    "error_response",
    "get_request_id",
    "log_internal_error",
]

