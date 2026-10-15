"""Authentication & identity resolution (P0 security line A).

Design goals
------------
* A single, explicit source of identity: the presented credential.
  ``user_id`` supplied in a query string or request body is **never**
  treated as an identity source.
* Fail closed by default. When authentication is required and no valid
  credential is presented, the request is rejected with ``401``.
* Local single-user development stays convenient, but only when the operator
  opts in explicitly via configuration (``AUTH_LOCAL_DEV_MODE``). Even then the
  fallback identity is a fixed, well-known UUID rather than "whatever the
  first row in the database happens to be".
"""

from __future__ import annotations

import hmac
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fixed well-known identity for local single-user development mode.
LOCAL_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    """Raised when a request cannot be attributed to a caller."""

    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass(frozen=True)
class AuthenticatedUser:
    """The identity resolved from the request credential."""

    id: uuid.UUID
    scopes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def user_id(self) -> str:
        return str(self.id)


def _parse_api_keys() -> Dict[str, str]:
    """Parse ``API_KEYS`` as a ``user_id=key,user_id=key`` mapping.

    Blank entries are ignored. Malformed entries are logged and skipped rather
    than silently accepted.
    """
    mapping: Dict[str, str] = {}
    for chunk in (settings.API_KEYS or "").split(","):
        entry = chunk.strip()
        if not entry:
            continue
        if "=" not in entry:
            logger.warning(
                "Ignoring malformed API_KEYS entry (expected 'user_id=key'): %r", entry
            )
            continue
        raw_uid, _, key = entry.partition("=")
        raw_uid = raw_uid.strip()
        key = key.strip()
        if not raw_uid or not key:
            logger.warning("Ignoring incomplete API_KEYS entry")
            continue
        mapping[key] = raw_uid
    return mapping


def _coerce_user_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        # Allow human-readable ids by deriving a stable UUID, mirroring the
        # existing `_parse_user_id` convention in the service layer.
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(raw))


def _lookup_key(raw_key: str) -> AuthenticatedUser:
    for key, raw_uid in _parse_api_keys().items():
        # Constant-time comparison to avoid leaking the key by timing.
        if hmac.compare_digest(key, raw_key):
            return AuthenticatedUser(id=_coerce_user_id(raw_uid), scopes=("api",))
    raise AuthError("Invalid API key.")


def _is_auth_enabled() -> bool:
    return bool((settings.API_KEYS or "").strip())


def resolve_user_from_key(raw_key: str) -> AuthenticatedUser:
    """Public helper used by tests and non-FastAPI callers."""
    return _lookup_key(raw_key)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """FastAPI dependency resolving the caller's identity.

    Behaviour matrix:

    * credentials provided -> validated against ``API_KEYS``. An invalid
      credential is always a 401; it never falls back to local dev mode.
    * no credentials:
        - ``AUTH_REQUIRED=true`` -> 401.
        - ``AUTH_REQUIRED=false`` and ``AUTH_LOCAL_DEV_MODE=true`` -> the
          well-known local dev identity (explicit operator opt-in only).
        - otherwise -> 401.
    """
    if credentials and credentials.scheme and credentials.scheme.lower() == "bearer":
        token = (credentials.credentials or "").strip()
        if not token:
            raise AuthError("Missing bearer token.")
        return _lookup_key(token)

    # Support ``X-API-Key`` as an explicit alternative for non-browser clients.
    header_key = (request.headers.get("x-api-key") or "").strip()
    if header_key:
        return _lookup_key(header_key)

    if settings.AUTH_LOCAL_DEV_MODE and not settings.AUTH_REQUIRED:
        logger.debug("Falling back to local development identity.")
        return AuthenticatedUser(id=LOCAL_DEV_USER_ID, scopes=("local-dev",))

    raise AuthError("Authentication credentials were not provided.")


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[AuthenticatedUser]:
    """Like :func:`get_current_user` but returns ``None`` instead of raising.

    Useful for endpoints that behave differently for anonymous callers while
    still never trusting a body/query ``user_id``.
    """
    try:
        return await get_current_user(request, credentials)
    except AuthError:
        return None


__all__ = [
    "AuthenticatedUser",
    "AuthError",
    "LOCAL_DEV_USER_ID",
    "get_current_user",
    "get_optional_current_user",
    "resolve_user_from_key",
]