import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import (
    DEPENDENCY_FAILURE,
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.core.skill_engine import SkillManager, get_skill_manager
from app.models.draft import Draft
from app.models.material import Material
from app.schemas.material_schemas import (
    CollectUrlRequest,
    FetchTrendingRequest,
    MaterialCreateRequest,
    MaterialResponse,
    MaterialUpdateRequest,
)

router = APIRouter(tags=["materials"])

logger = logging.getLogger(__name__)

# Public, fixed messages. Client-supplied ids are never echoed back, and a
# missing resource is indistinguishable from one owned by another user.
MATERIAL_NOT_FOUND_MESSAGE = "Material not found."


def _parse_uid(uid_raw: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    """Strictly parse a UUID.

    Invalid input returns ``None``. It is never silently coerced into a
    different UUID: doing so would let a malformed identifier resolve to an
    unrelated record and would make authorization checks ambiguous.
    """
    if not uid_raw:
        return None
    if isinstance(uid_raw, uuid.UUID):
        return uid_raw
    try:
        return uuid.UUID(str(uid_raw))
    except (ValueError, AttributeError, TypeError):
        return None


def _get_owned_material(
    session: Session,
    material_id: str,
    current_user: AuthenticatedUser,
) -> Material:
    """Fetch a material the caller owns, or raise a uniform 404.

    An unparsable id, a missing row and a row owned by someone else all produce
    the same response so the endpoint cannot be used to probe for the
    existence of other users' materials.
    """
    p_id = _parse_uid(material_id)
    if p_id is None:
        raise AppError(NOT_FOUND, MATERIAL_NOT_FOUND_MESSAGE)
    mat = session.get(Material, p_id)
    if mat is None or mat.user_id != current_user.id:
        raise AppError(NOT_FOUND, MATERIAL_NOT_FOUND_MESSAGE)
    return mat


def _serialize_material(m: Material) -> Dict[str, Any]:
    return {
        "id": str(m.id),
        "user_id": str(m.user_id),
        "material_type": m.material_type,
        "source_platform": m.source_platform,
        "source_url": m.source_url,
        "source_author": m.source_author,
        "title": m.title,
        "raw_content": m.raw_content,
        "cleaned_content": m.cleaned_content,
        "blueprint_data": m.blueprint_data,
        "tags": m.tags or [],
        "status": m.status,
        "meta_info": m.meta_info or {},
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }

