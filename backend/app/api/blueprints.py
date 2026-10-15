from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.auth.ownership import not_found
from app.core.db import get_session
from app.core.errors import VALIDATION_ERROR, AppError
from app.engine.cognitive_engine import CognitiveEngine, get_cognitive_engine
from app.models.user import User
from app.services.memory_service import MemoryService

router = APIRouter(tags=["blueprints"])


def _get_owned_blueprint(
    session: Session,
    blueprint_id: str,
    current_user: AuthenticatedUser,
) -> Dict[str, Any]:
    """Return the blueprint only when it belongs to the authenticated caller.

    Blueprints live inside ``User.profile_data``, so ownership is determined by
    looking the object up *inside the caller's own profile*. A blueprint that
    exists for another user (or nowhere at all) produces the same 404 so the
    API never confirms the existence of another user's resource.
    """
    user = session.get(User, current_user.id)
    if not user:
        raise not_found(f"Benchmark blueprint with ID '{blueprint_id}' not found.")
    blueprints = (user.profile_data or {}).get("benchmark_blueprints", []) or []
    for bp in blueprints:
        if str(bp.get("id")) == str(blueprint_id):
            return bp
    raise not_found(f"Benchmark blueprint with ID '{blueprint_id}' not found.")


class BlueprintExtractRequest(BaseModel):
    content: Optional[str] = Field(default=None, description="Article raw text content.")
    text: Optional[str] = Field(default=None, description="Alias for content.")
    url: Optional[str] = Field(default=None, description="Article web URL if extracting from web.")
    title: Optional[str] = Field(default=None, description="Optional custom title for the blueprint.")
    user_id: Optional[str] = Field(default=None, description="Deprecated/ignored: identity comes from the credential.")


@router.post("/extract", response_model=Dict[str, Any])
async def extract_blueprint(
    payload: BlueprintExtractRequest,
    session: Session = Depends(get_session),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Extract structural bones (blueprint, hook, emotional arc, structural stages, pacing)
    from a benchmark article (via text or URL) and persist to the authenticated user's blueprint library.
    """
    target = payload.content or payload.text or payload.url
    if not target or not target.strip():
        raise AppError(
            code=VALIDATION_ERROR,
            message="Either 'content', 'text', or 'url' must be provided.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        return await engine.extract_blueprint_from_text(
            content_or_url=target.strip(),
            title=payload.title,
            user_id=current_user.id,
            session=session,
        )
    except ValueError:
        # The upstream message may quote article content or an internal fetch
        # detail, so it is never echoed. Unexpected exceptions propagate to the
        # global handler, which logs the cause and returns INTERNAL_ERROR.
        raise AppError(
            code=VALIDATION_ERROR,
            message="The blueprint could not be extracted from the provided input.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_blueprints(
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Returns saved benchmark blueprints for the authenticated user."""
    return MemoryService.get_benchmark_blueprints(user_id=current_user.id, session=session)


@router.get("/{blueprint_id}", response_model=Dict[str, Any])
def get_blueprint(
    blueprint_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve a single benchmark blueprint by ID."""
    return _get_owned_blueprint(session, blueprint_id, current_user)



class UpdateBlueprintRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Updated title of the blueprint.")
    hook_style: Optional[str] = Field(default=None, description="Updated hook style.")
    structural_stages: Optional[List[str]] = Field(default=None, description="Updated structural stages.")
    emotional_arc: Optional[str] = Field(default=None, description="Updated emotional arc.")
    pacing: Optional[str] = Field(default=None, description="Updated pacing description.")
    user_id: Optional[str] = Field(default=None, description="Deprecated/ignored: identity comes from the credential.")


@router.put("/{blueprint_id}", response_model=Dict[str, Any])
@router.patch("/{blueprint_id}", response_model=Dict[str, Any])
def update_blueprint(
    blueprint_id: str,
    payload: UpdateBlueprintRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update an existing benchmark blueprint owned by the authenticated user."""
    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.hook_style is not None:
        updates["hook_style"] = payload.hook_style.strip()
    if payload.structural_stages is not None:
        updates["structural_stages"] = payload.structural_stages
    if payload.emotional_arc is not None:
        updates["emotional_arc"] = payload.emotional_arc.strip()
    if payload.pacing is not None:
        updates["pacing"] = payload.pacing.strip()

    # Ownership is verified *before* touching the service layer: the service
    # falls back to the default user when the id is not found under the given
    # user, which would otherwise turn this into a cross-user write.
    _get_owned_blueprint(session, blueprint_id, current_user)

    updated = MemoryService.update_benchmark_blueprint(
        blueprint_id=blueprint_id,
        updates=updates,
        user_id=current_user.id,
        session=session,
    )
    if not updated:
        raise not_found(f"Benchmark blueprint with ID '{blueprint_id}' not found.")
    return updated


@router.delete("/{blueprint_id}")
def delete_blueprint(
    blueprint_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a benchmark blueprint owned by the authenticated user."""
    _get_owned_blueprint(session, blueprint_id, current_user)

    success = MemoryService.delete_benchmark_blueprint(
        blueprint_id=blueprint_id,
        user_id=current_user.id,
        session=session,
    )
    if not success:
        raise not_found(f"Benchmark blueprint with ID '{blueprint_id}' not found.")
    return {"success": True, "message": f"Blueprint '{blueprint_id}' deleted successfully.", "id": blueprint_id}
