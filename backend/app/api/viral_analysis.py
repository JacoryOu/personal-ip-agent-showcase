"""API routes for viral / benchmark article semantic breakdown."""

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

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
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.schemas.viral_schemas import ViralAnalysisRequest, ViralAnalysisResponse
from app.services.viral_semantic_service import ViralSemanticService

router = APIRouter(tags=["viral-analysis"])


def _trusted_user_id(requested: Optional[uuid.UUID], current_user: AuthenticatedUser) -> uuid.UUID:
    """The credential is the only identity source; a body mismatch is refused."""
    if requested is not None and normalize_user_id(requested) != current_user.id:
        raise AppError(code=FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN)
    return current_user.id


@router.post("/analyze", response_model=ViralAnalysisResponse)
async def analyze_article(
    payload: ViralAnalysisRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Extracts reusable semantic signals from one viral / benchmark article.

    Returns 200 with ``extraction_mode="fallback"`` if the model layer fails, so a
    caller always receives a usable payload with explicit warnings.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    try:
        return await ViralSemanticService().analyze_article(
            title=payload.title,
            content=payload.content,
            session=session,
            source_platform=payload.source_platform,
            source_url=payload.source_url,
            user_id=user_id,
            material_id=payload.material_id,
        )
    except AppError:
        raise
    except ValueError as e:
        # Provenance validation failures are caller-input problems, but the
        # message can embed internal ids and wording; keep it server-side only.
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from e
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


@router.get("/{analysis_id}", response_model=ViralAnalysisResponse)
def get_analysis(
    analysis_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns a previously persisted semantic analysis owned by the caller."""
    record = session.get(ViralSemanticAnalysisRecord, analysis_id)
    if record is None:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    owner = normalize_user_id(record.user_id)
    if owner is None or owner != current_user.id:
        # Refuse rather than confirm existence of another user's analysis.
        raise AppError(code=FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN)
    try:
        result = ViralSemanticService().get_analysis(analysis_id, session)
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e
    if result is None:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return result
