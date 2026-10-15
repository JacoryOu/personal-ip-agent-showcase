"""Ownership helpers for object-level access control (IDOR protection).

All helpers intentionally return **404** rather than 403 when the caller does
not own the object, so that the API never confirms the existence of another
user's resource.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import HTTPException, status


def normalize_user_id(value: Any) -> Optional[uuid.UUID]:
    """Best-effort conversion of a stored ``user_id`` into a UUID."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(value))


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def ensure_same_user(caller_id: Any, owner_id: Any, detail: str) -> None:
    """Raise 404 when ``owner_id`` does not match the authenticated caller.

    Both sides are normalized so a ``str`` column value (``chat_session.user_id``)
    and a ``uuid.UUID`` column value (``benchmark_accounts.user_id``) compare
    correctly.
    """
    caller = normalize_user_id(caller_id)
    owner = normalize_user_id(owner_id)
    if owner is None:
        # Objects without an owner are never user-addressable.
        raise not_found(detail)
    if caller is None or caller != owner:
        raise not_found(detail)


def ensure_uuid_param(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{field_name}' must be a valid UUID.",
        )


__all__ = [
    "ensure_same_user",
    "ensure_uuid_param",
    "normalize_user_id",
    "not_found",
]