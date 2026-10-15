"""Audience feedback ingestion and evolution routes."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import NOT_FOUND, AppError
from app.schemas.draft_schemas import (
    FeedbackCreateRequest,
    FeedbackExtractRequest,
    FeedbackExtractResponse,
    FeedbackItemResponse,
)
from app.services.feedback_service import FeedbackService

from app.api.draft_common import _get_owned_draft, _reject_body_user_id

router = APIRouter()


# ==============================================================================
# Audience Feedback Ingestion & Cognitive Asset Evolution Endpoints (Phase 4)
# ==============================================================================

@router.post("/{draft_id}/feedback", response_model=FeedbackItemResponse)
def record_feedback(
    draft_id: str,
    payload: FeedbackCreateRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FeedbackItemResponse:
    """Records reader comments, reviews, or audience engagement feedback."""
    _reject_body_user_id(payload.user_id, current_user)
    _get_owned_draft(session, draft_id, current_user)
    try:
        fb = FeedbackService.record_feedback(
            draft_id=draft_id,
            comments_text=payload.comments_text,
            metrics=payload.metrics,
            user_id=str(current_user.id),
            session=session,
        )
        return FeedbackItemResponse(
            id=str(fb.id),
            draft_id=str(fb.draft_id),
            user_id=str(fb.user_id),
            comments_text=fb.comments_text,
            metrics=fb.metrics or {},
            extracted_insights=fb.extracted_insights,
            boosted_dna_traits=fb.boosted_dna_traits,
            saved_material_ids=fb.saved_material_ids,
            created_at=fb.created_at.isoformat() if fb.created_at else None,
            updated_at=fb.updated_at.isoformat() if fb.updated_at else None,
        )
    except ValueError:
        raise AppError(
            code=NOT_FOUND,
            message="The referenced feedback or draft record could not be found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@router.post("/{draft_id}/feedback/extract", response_model=FeedbackExtractResponse)
async def extract_feedback_insights(
    draft_id: str,
    payload: FeedbackExtractRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FeedbackExtractResponse:
    """Analyzes audience feedback via LLM to extract resonant ideas, auto-save inspiration notes into MaterialVault, and dynamically evolve ThinkingDNA confidence scores."""
    _reject_body_user_id(payload.user_id, current_user)
    _get_owned_draft(session, draft_id, current_user)
    try:
        return await FeedbackService.extract_feedback_insights(
            draft_id=draft_id,
            comments_text=payload.comments_text,
            feedback_id=payload.feedback_id,
            metrics=payload.metrics,
            user_id=str(current_user.id),
            session=session,
        )
    except ValueError:
        raise AppError(
            code=NOT_FOUND,
            message="The referenced feedback or draft record could not be found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@router.get("/{draft_id}/feedback", response_model=List[FeedbackItemResponse])
def list_feedbacks(
    draft_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[FeedbackItemResponse]:
    """Lists audience feedback records and evolutionary insights for a draft."""
    _get_owned_draft(session, draft_id, current_user)
    try:
        return FeedbackService.list_feedbacks(draft_id=draft_id, session=session)
    except ValueError:
        raise AppError(
            code=NOT_FOUND,
            message="The referenced feedback or draft record could not be found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


# ---------------------------------------------------------------------------
# Audience Feedback Evolution Loop (Phase 4)
# ---------------------------------------------------------------------------

class FeedbackEvolveRequest(BaseModel):
    """Request payload for the [📊 录入发布反馈] audience feedback evolution endpoint."""
    feedback_text: str
    metrics: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None


class FeedbackEvolveResponse(BaseModel):
    draft_id: str
    resonant_ideas: List[str] = []
    boosted_traits: List[Any] = []
    potential_v2_upgrades: List[str] = []
    evolution_summary: str = ""


@router.post("/{draft_id}/feedback/evolve", response_model=FeedbackEvolveResponse)
async def evolve_feedback(
    draft_id: str,
    payload: FeedbackEvolveRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FeedbackEvolveResponse:
    """
    Audience Feedback Evolution Loop.

    Analyzes feedback_text to:
    - Extract resonant ideas from audience comments.
    - Boost confidence_score of related ThinkingDNA traits.
    - Flag potential V2 evolution if feedback contradicts existing DNA.

    Designed for the [📊 录入发布反馈] button in the draft workbench view.
    """
    _reject_body_user_id(payload.user_id, current_user)
    _get_owned_draft(session, draft_id, current_user)
    try:
        extract_result = await FeedbackService.extract_feedback_insights(
            draft_id=draft_id,
            comments_text=payload.feedback_text,
            feedback_id=None,
            metrics=payload.metrics,
            user_id=str(current_user.id),
            session=session,
        )

        # Flag traits for potential V2 evolution when:
        # - Boost is small AND draft generated controversy points
        potential_v2: List[str] = []
        for trait in extract_result.boosted_traits:
            if trait.boost_amount < 0.3 and extract_result.controversy_points:
                potential_v2.append(
                    f"[{trait.dimension}] {trait.statement[:60]}…"
                    f"(置信度 {trait.new_confidence:.2f}，读者存在争议，建议迭代为 V2)"
                )

        return FeedbackEvolveResponse(
            draft_id=extract_result.draft_id,
            resonant_ideas=extract_result.resonant_ideas,
            boosted_traits=[t.model_dump() for t in extract_result.boosted_traits],
            potential_v2_upgrades=potential_v2,
            evolution_summary=extract_result.evolution_summary,
        )
    except ValueError:
        raise AppError(
            code=NOT_FOUND,
            message="The referenced feedback or draft record could not be found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
