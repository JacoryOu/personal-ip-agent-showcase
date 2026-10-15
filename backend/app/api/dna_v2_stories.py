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
# Stories
# ===========================================================================



class StoryCreate(BaseModel):
    title: str = ""
    story_content: str
    story_type: str = "daily_life"
    occurred_at: Optional[datetime] = None
    tags: List[str] = []
    confidence_score: float = 1.0
    user_id: Optional[str] = None


@router.get("/stories")
def list_stories(
    user_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    story_type: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    uid = _trusted_user_id(user_id, current_user)
    stmt = select(EpisodicStory).where(EpisodicStory.user_id == uid)
    if story_type:
        stmt = stmt.where(EpisodicStory.story_type == story_type)
    if date_from:
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=timezone.utc)
        stmt = stmt.where(EpisodicStory.occurred_at >= date_from)
    if date_to:
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)
        stmt = stmt.where(EpisodicStory.occurred_at <= date_to)
    stories = session.exec(stmt.order_by(EpisodicStory.occurred_at.desc())).all()
    result = []
    for s in stories:
        d = s.model_dump()
        # Filter by tags if requested
        if tags:
            req_tags = {t.strip() for t in tags.split(",") if t.strip()}
            story_tags = set(s.tags or [])
            if not req_tags.issubset(story_tags):
                continue
        result.append(d)
    return result


@router.post("/stories", status_code=201)
def create_story(
    body: StoryCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = _trusted_user_id(body.user_id, current_user)
    if body.story_type not in _facade().VALID_STORY_TYPES:
        raise _unprocessable("story_type must be one of: daily_life, failure_reflection, client_case")
    occurred = body.occurred_at or datetime.now(timezone.utc)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)
    story = EpisodicStory(
        user_id=uid,
        title=body.title,
        story_content=body.story_content,
        story_type=body.story_type,
        occurred_at=occurred,
        tags=body.tags,
        confidence_score=body.confidence_score,
    )
    session.add(story)
    session.commit()
    session.refresh(story)
    return story.model_dump()
