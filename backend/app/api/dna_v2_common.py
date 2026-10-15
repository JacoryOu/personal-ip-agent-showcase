"""Thinking DNA 2.0 API – Personas, Products, Stories, Timeline, Supersede."""

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
from app.core.auth.ownership import normalize_user_id
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

router = APIRouter(tags=["dna_v2"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trusted_user_id(
    requested: Optional[str], current_user: AuthenticatedUser
) -> uuid.UUID:
    """Resolve the acting user from credentials, never from client input.

    A client-supplied ``user_id`` is only ever accepted when it denotes the very
    same identity as the authenticated principal. Any mismatch is a forbidden
    attempt to act on someone else's private resources; it is never silently
    coerced back to a default/development user.
    """
    if requested is not None and str(requested).strip():
        if normalize_user_id(str(requested).strip()) != current_user.id:
            raise AppError(code=FORBIDDEN, status_code=403)
    return current_user.id


def _ensure_owned(resource_owner: Optional[uuid.UUID], current_user: AuthenticatedUser) -> None:
    """Reject access to a private resource that belongs to another user."""
    if resource_owner is None or resource_owner != current_user.id:
        raise AppError(code=FORBIDDEN, status_code=403)


def _not_found(detail: str) -> AppError:
    return AppError(code=NOT_FOUND, status_code=404, message=detail)


def _unprocessable(detail: str) -> AppError:
    return AppError(code=VALIDATION_ERROR, status_code=422, message=detail)

VALID_STORY_TYPES = {"daily_life", "failure_reflection", "client_case"}
