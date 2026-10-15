from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import (
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.core.model_gateway import ModelRole, extract_json_from_text, get_model_gateway
from app.models.persona import IPPersona
from app.models.story import EpisodicStory
from app.models.product import ProductVault
from app.services.cognitive_service import CognitiveService

from app.api.dna_v2_common import (
    router,
    _trusted_user_id,
    _ensure_owned,
    _not_found,
    _unprocessable,
)


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import dna_v2
    return dna_v2


# ===========================================================================
# Timeline
# ===========================================================================

@router.get("/timeline")
def get_timeline(
    user_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Chronological stream of DNA evolutions + stories combined."""
    uid = _trusted_user_id(user_id, current_user)
    events: List[Dict[str, Any]] = []

    # Episodic stories
    stories = session.exec(select(EpisodicStory).where(EpisodicStory.user_id == uid)).all()
    for s in stories:
        events.append({
            "type": "story",
            "occurred_at": s.occurred_at.isoformat() if s.occurred_at else None,
            "title": s.title,
            "summary": s.story_content[:120],
            "story_type": s.story_type,
            "id": str(s.id),
        })

    # DNA trait evolutions (traits with evolution_reason set)
    profile = CognitiveService.get_or_create_user_profile(session, uid)
    for trait in profile.traits:
        er = getattr(trait, "evolution_reason", None)
        if er:
            events.append({
                "type": "dna_evolution",
                "occurred_at": (
                    trait.occurred_at.isoformat()
                    if getattr(trait, "occurred_at", None)
                    else trait.created_at.isoformat()
                ),
                "title": f"DNA演化: {trait.statement[:60]}",
                "evolution_reason": er,
                "version": getattr(trait, "version", 1),
                "trait_status": getattr(trait, "trait_status", "active"),
                "id": trait.id,
            })

    # Sort newest first
    events.sort(key=lambda e: e.get("occurred_at") or "", reverse=True)
    return events


# ===========================================================================
