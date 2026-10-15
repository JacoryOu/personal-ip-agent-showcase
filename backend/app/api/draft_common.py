"""Shared helpers for the drafts API split modules."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session

from app.core.auth import AuthenticatedUser
from app.core.errors import FORBIDDEN, NOT_FOUND, AppError
from app.engine.agents.draft_agent import DraftAgent
from app.models.draft import Draft


def get_draft_agent() -> DraftAgent:
    return DraftAgent()

def get_draft_agent() -> DraftAgent:
    return DraftAgent()


def _resolve_draft_id(draft_id: str) -> uuid.UUID:
    """Resolve a draft primary key the way the service layer historically did."""
    try:
        return uuid.UUID(draft_id)
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(draft_id))


def _not_found(draft_id: str) -> AppError:
    """Public not-found error for a draft archive record.

    The draft id is echoed back because it is a caller-supplied identifier, never
    an internal one (no primary key, path, host, or upstream URL is exposed).
    """
    return AppError(
        code=NOT_FOUND,
        message=f"Draft with ID '{draft_id}' not found.",
        status_code=404,
    )


def _forbidden() -> AppError:
    """Ownership mismatch. Deliberately says nothing about the target resource."""
    return AppError(
        code=FORBIDDEN,
        message="You do not have access to this resource.",
        status_code=403,
    )


def _get_owned_draft(
    session: Session,
    draft_id: str,
    current_user: AuthenticatedUser,
) -> Draft:
    """Load a draft only when the authenticated caller owns it.

    Ownership is checked *before* the draft body is read, mutated or handed to a
    downstream service, so a caller can neither read nor change another user's
    archived work.
    """
    t_id = _resolve_draft_id(draft_id)
    draft = session.get(Draft, t_id)
    if not draft:
        raise _not_found(draft_id)
    if draft.user_id != current_user.id:
        raise _forbidden()
    return draft


def _reject_body_user_id(payload_user_id: Optional[str], current_user: AuthenticatedUser) -> None:
    """Refuse a body ``user_id`` that contradicts the presented credential.

    The credential is the only identity source. Silently ignoring a mismatching
    body field would let a client believe it wrote into another user's space, so
    the conflict is reported explicitly. A matching (or absent) value is fine.
    """
    if payload_user_id is None:
        return
    from app.engine.cognitive_engine import _parse_user_id

    claimed = _parse_user_id(payload_user_id)
    if claimed is not None and claimed != current_user.id:
        raise AppError(
            code=FORBIDDEN,
            message="The request body user_id does not match the authenticated user.",
            status_code=403,
        )
