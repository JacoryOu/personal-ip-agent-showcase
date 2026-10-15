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
    from app.api import dna_v2
    return dna_v2


# ===========================================================================
# Personas
# ===========================================================================

class PersonaCreate(BaseModel):
    name: str
    target_audience: str = ""
    tone_style: str = ""
    reader_salutation: str = ""
    origin_story: str = ""
    user_id: Optional[str] = None


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    target_audience: Optional[str] = None
    tone_style: Optional[str] = None
    reader_salutation: Optional[str] = None
    origin_story: Optional[str] = None
    is_active: Optional[bool] = None
    user_id: Optional[str] = None


@router.get("/personas")
def list_personas(
    user_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    uid = _trusted_user_id(user_id, current_user)
    personas = session.exec(select(IPPersona).where(IPPersona.user_id == uid)).all()
    return [p.model_dump() for p in personas]


@router.post("/personas", status_code=201)
def create_persona(
    body: PersonaCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = _trusted_user_id(body.user_id, current_user)
    persona = IPPersona(
        user_id=uid,
        name=body.name,
        target_audience=body.target_audience,
        tone_style=body.tone_style,
        reader_salutation=body.reader_salutation,
        origin_story=body.origin_story,
        is_active=True,
    )
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona.model_dump()


class ExtractFromTextRequest(BaseModel):
    text: str
    auto_save: bool = False
    autoSave: bool = False
    user_id: Optional[str] = None
    cover_image: Optional[str] = None
    coverImage: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    galleryImages: Optional[List[str]] = None
    service_rights_images: Optional[List[str]] = None
    serviceRightsImages: Optional[List[str]] = None
