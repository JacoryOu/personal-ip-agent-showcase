from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.auth.ownership import normalize_user_id
from app.core.db import get_readonly_session
from app.core.errors import FORBIDDEN, INTERNAL_ERROR, VALIDATION_ERROR, AppError
from app.engine.agents.outline_agent import OutlineAgent
from app.engine.cognitive_engine import CognitiveEngine, get_cognitive_engine
from app.schemas.outline_schemas import OutlineInput, OutlineOutput

router = APIRouter(tags=["outlines"])


def get_outline_agent() -> OutlineAgent:
    return OutlineAgent()


def _trusted_user_id(requested: str | None, current_user: AuthenticatedUser) -> str:
    """Resolve the effective user id from the credential, never from the body.

    ``OutlineInput.user_id`` is kept for backwards compatibility with existing
    clients, but it is no longer an identity source: the presented credential
    wins, and an explicit mismatch is rejected instead of silently ignored.
    """
    if requested is not None and str(requested).strip():
        if normalize_user_id(str(requested).strip()) != current_user.id:
            raise AppError(code=FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN)
    return current_user.user_id


@router.post("/generate", response_model=OutlineOutput)
async def generate_outlines(
    payload: OutlineInput,
    readonly_session: Session = Depends(get_readonly_session),
    agent: OutlineAgent = Depends(get_outline_agent),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> OutlineOutput:
    """
    Generate two divergent outlines (A and B) for the provided topic.
    Delegates generation to the headless CognitiveEngine.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    try:
        return await engine.explore_outlines(
            topic=payload.topic,
            additional_context=payload.additional_context,
            user_id=user_id,
            thinking_dna=payload.thinking_dna,
            agent=agent,
            readonly_session=readonly_session,
            persona_id=payload.persona_id,
            product_id=payload.product_id,
            story_ids=payload.story_ids,
        )
    except ValueError:
        # The engine validates the request shape; the message is derived from
        # caller input, but we still publish the generic contract message so
        # internal validation wording never becomes an information channel.
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    except AppError:
        raise
    except Exception as e:
        # The cause (upstream SDK text, DB messages, absolute paths) is logged
        # server-side by the global handler together with the request id.
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e
