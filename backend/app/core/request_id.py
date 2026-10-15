"""Request-id middleware.

Assigns every request a correlation id so a client-visible error can be traced
back to the exact server-side log line. The id is taken from an inbound
``X-Request-ID`` when present (so a caller can propagate its own trace id) and
generated otherwise.
"""

from __future__ import annotations

import logging
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.errors import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER_MAX_LENGTH = 64

# Accept a caller-supplied id only when it is short and printable; an
# unbounded header value would end up in every log line for this request.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,%d}$" % REQUEST_ID_HEADER_MAX_LENGTH)


def resolve_request_id(candidate: str | None) -> str:
    if candidate:
        cleaned = candidate.strip()
        if _SAFE_REQUEST_ID.match(cleaned):
            return cleaned
        logger.debug("Discarding malformed inbound X-Request-ID header.")
    return uuid.uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = ["REQUEST_ID_HEADER_MAX_LENGTH", "RequestIdMiddleware", "resolve_request_id"]
