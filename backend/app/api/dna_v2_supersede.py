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


# Supersede
# ===========================================================================

class SupersedeRequest(BaseModel):
    old_trait_id: str
    new_content: str
    evolution_reason: str
    user_id: Optional[str] = None


@router.post("/supersede")
def supersede_trait(
    body: SupersedeRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    from app.services.memory_service import supersede_dna_trait

    uid = _trusted_user_id(body.user_id, current_user)
    try:
        return supersede_dna_trait(
            old_trait_id=body.old_trait_id,
            new_content=body.new_content,
            evolution_reason=body.evolution_reason,
            session=session,
            user_id=uid,
        )
    except AppError:
        raise
    except ValueError:
        # The service raises ValueError for a missing/unknown trait; its message
        # is internal state and must not reach the client verbatim.
        raise _not_found("Trait not found")
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=500) from e
