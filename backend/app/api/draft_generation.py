"""Draft generation and distribution routes."""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_readonly_session, get_session
from app.core.errors import VALIDATION_ERROR, AppError
from app.engine.agents.draft_agent import DraftAgent
from app.engine.cognitive_engine import CognitiveEngine, get_cognitive_engine
from app.schemas.draft_schemas import (
    BlueprintDraftInput,
    DistributeContentInput,
    DistributeDraftRequest,
    DraftGenerateRequest,
    DraftOutput,
)

from app.api.draft_common import (
    get_draft_agent,
    _get_owned_draft,
    _reject_body_user_id,
)

router = APIRouter()


@router.post("/generate", response_model=DraftOutput)
async def generate_draft(
    payload: DraftGenerateRequest,
    readonly_session: Session = Depends(get_readonly_session),
    session: Session = Depends(get_session),
    agent: DraftAgent = Depends(get_draft_agent),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DraftOutput:
    """Generate a complete draft article based on the selected outline.

    The authenticated credential is the only identity source; a body ``user_id``
    that disagrees with it is rejected rather than trusted.
    """
    try:
        return await engine.generate_draft(
            topic=payload.topic,
            outline=payload.outline,
            additional_context=payload.additional_context,
            user_id=str(current_user.id),
            thinking_dna=payload.thinking_dna,
            agent=agent,
            readonly_session=readonly_session,
            session=session,
            source_material_id=payload.source_material_id,
            benchmark_blueprint_id=payload.benchmark_blueprint_id,
            persona_id=payload.persona_id,
            product_id=payload.product_id,
            story_ids=payload.story_ids,
            viral_analysis_id=payload.viral_analysis_id,
        )
    except ValueError:
        # Expected business failure: the message may quote user content, so it is
        # not echoed. Unexpected failures propagate to the global handler, which
        # logs the original exception and returns a fixed contract.
        raise AppError(
            code=VALIDATION_ERROR,
            message="The draft could not be generated from the provided input.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


@router.post("/generate-from-blueprint", response_model=DraftOutput)
async def generate_from_blueprint(
    payload: BlueprintDraftInput,
    readonly_session: Session = Depends(get_readonly_session),
    session: Session = Depends(get_session),
    agent: DraftAgent = Depends(get_draft_agent),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DraftOutput:
    """Generate an original draft by using a benchmark blueprint as structural bone
    and the user's Thinking DNA as stylistic skin.
    """
    try:
        return await engine.generate_from_blueprint(
            topic=payload.topic,
            blueprint=payload.blueprint,
            blueprint_id=payload.blueprint_id,
            additional_context=payload.additional_context,
            user_id=str(current_user.id),
            thinking_dna=payload.thinking_dna,
            agent=agent,
            readonly_session=readonly_session,
            session=session,
            source_material_id=payload.source_material_id,
            persona_id=payload.persona_id,
            product_id=payload.product_id,
            story_ids=payload.story_ids,
        )
    except ValueError:
        raise AppError(
            code=VALIDATION_ERROR,
            message="The draft could not be generated from the provided input.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


@router.post("/distribute")
async def distribute_content(
    payload: DistributeContentInput,
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Formats raw article content into 4 platform distributions (Xiaohongshu, WeChat, Twitter Thread, Video Script)
    via the content_multi_distributor sandboxed skill.
    """
    try:
        return engine.distribute_content(
            content=payload.content,
            title=payload.title,
            platforms=payload.platforms,
        )
    except ValueError:
        raise AppError(
            code=VALIDATION_ERROR,
            message="The content could not be distributed for the requested platforms.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


@router.post("/{draft_id}/distribute")
async def distribute_draft_by_id(
    draft_id: uuid.UUID,
    payload: Optional[DistributeDraftRequest] = None,
    session: Session = Depends(get_session),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetches an existing draft by ID and formats it into multi-platform distribution outputs."""
    draft = _get_owned_draft(session, str(draft_id), current_user)

    target_content = (draft.user_final_draft or draft.original_ai_draft or "").strip()
    if not target_content:
        raise AppError(
            code=VALIDATION_ERROR,
            message="Target draft has no content to distribute.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return engine.distribute_content(
        content=target_content,
        title=draft.topic,
        platforms=payload.platforms if payload else None,
    )
