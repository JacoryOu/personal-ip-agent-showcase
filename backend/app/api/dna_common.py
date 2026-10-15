from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

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
from app.core.skill_engine import get_skill_manager
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.engine.agents.diff_agent import DiffAgent
from app.engine.cognitive_engine import CognitiveEngine, get_cognitive_engine
from app.models.dna_record import DNARecord
from app.models.draft import Draft
from app.schemas.diff_schemas import DiffInput, DNAExtractionOutput, ThinkingDNA
from app.services.cognitive_service import CognitiveService
from app.services.memory_service import MemoryService

router = APIRouter(tags=["dna"])


def get_diff_agent() -> DiffAgent:
    return DiffAgent()


def _trusted_user_id(
    requested: Optional[str], current_user: AuthenticatedUser
) -> str:
    """Resolve the effective user id from the credential only.

    ``user_id`` supplied in a request body or query string is never an
    identity source. It is still accepted for backwards compatibility, but a
    value that does not resolve to the authenticated user is refused instead
    of silently ignored. Comparison uses :func:`normalize_user_id`, the same
    normalisation the ownership helpers and the service layer use, so legacy
    non-UUID user ids stay comparable with the credential.
    """
    if requested is not None and str(requested).strip():
        if normalize_user_id(str(requested).strip()) != current_user.id:
            raise AppError(code=FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN)
    return current_user.user_id


class TraitActionRequest(BaseModel):
    trait_id: str
    user_id: Optional[str] = None


class AddTraitRequest(BaseModel):
    dimension: CognitiveDimension
    statement: str
    user_id: Optional[str] = None


class IngestOwnWorkRequest(BaseModel):
    content: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    user_id: Optional[str] = None


class DeconstructBenchmarkRequest(BaseModel):
    content: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    user_id: Optional[str] = None


class DialogueClashRequest(BaseModel):
    messages: List[Dict[str, str]]
    debate_topic: Optional[str] = None
    user_id: Optional[str] = None


class UpdateTraitRequest(BaseModel):
    statement: Optional[str] = None
    dimension: Optional[CognitiveDimension] = None
    status: Optional[TraitStatus] = None
    confidence_score: Optional[float] = None
    user_id: Optional[str] = None


class ToggleTraitRequest(BaseModel):
    trait_id: str
    enabled: Optional[bool] = None
    user_id: Optional[str] = None


class ImportDNARequest(BaseModel):
    traits: Optional[List[Dict[str, Any]]] = None
    thinking_dna: Optional[ThinkingDNA] = None
    mode: str = "merge"
    user_id: Optional[str] = None


class DetectConflictsRequest(BaseModel):
    statement: Optional[str] = None
    statements: Optional[List[str]] = None
    draft_content: Optional[str] = None
    user_id: Optional[str] = None


