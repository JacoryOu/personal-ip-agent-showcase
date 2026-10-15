"""Pure, side-effect-free helpers shared by the inspection scheduler modules."""

from __future__ import annotations

from typing import Any
from typing import Dict
from app.models.material import Material
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)

def _parse_uid(uid_raw: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not uid_raw:
        return None
    if isinstance(uid_raw, uuid.UUID):
        return uid_raw
    try:
        return uuid.UUID(str(uid_raw))
    except (ValueError, AttributeError, TypeError):
        # Strict: never silently derive a stable UUID from arbitrary input.
        # A malformed identifier must stay "unknown", not become some user's id.
        logger.warning("Rejected malformed user id: %r", uid_raw)
        return None


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


#: Scope key used by the background scheduler loop, which has no acting user.
DEFAULT_SCOPE = "__default__"


def _facade_engine():
    """Resolve ``engine`` from the facade module at call time.

    The public module ``app.services.inspection_scheduler_service`` keeps
    re-exporting ``engine`` and ``get_skill_manager`` because tests and callers
    monkeypatch them there. Resolving lazily keeps that compatibility intact
    after the responsibility split, and avoids a circular import at module load.
    """
    from app.services import inspection_scheduler_service as _facade

    return _facade.engine


def _facade_skill_manager():
    """Resolve ``get_skill_manager`` from the facade module at call time."""
    from app.services import inspection_scheduler_service as _facade

    return _facade.get_skill_manager
