from app.api.materials_common import *  # noqa: F401,F403
from app.api.materials_common import (  # noqa: F401
    MATERIAL_NOT_FOUND_MESSAGE,
    _get_owned_material,
    _parse_uid,
    _serialize_material,
    get_current_user,
    get_session,
    get_skill_manager,
    logger,
)

@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Retrieve single material detail by UUID, scoped to the caller."""
    mat = _get_owned_material(session, material_id, current_user)
    return _serialize_material(mat)


@router.patch("/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: str,
    payload: MaterialUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update material status, tags, blueprint data, or content."""
    mat = _get_owned_material(session, material_id, current_user)

    if payload.title is not None:
        mat.title = payload.title.strip()
    if payload.cleaned_content is not None:
        mat.cleaned_content = payload.cleaned_content.strip()
    if payload.status is not None:
        mat.status = payload.status.strip()
    if payload.tags is not None:
        mat.tags = payload.tags
    if payload.blueprint_data is not None:
        mat.blueprint_data = payload.blueprint_data
    if payload.meta_info is not None:
        merged_meta = dict(mat.meta_info or {})
        merged_meta.update(payload.meta_info)
        mat.meta_info = merged_meta

    mat.updated_at = datetime.now(timezone.utc)
    session.add(mat)
    session.commit()
    session.refresh(mat)

    return _serialize_material(mat)


@router.delete("/{material_id}")
def delete_material(
    material_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete material from vault. Nullifies draft foreign keys gracefully first."""
    mat = _get_owned_material(session, material_id, current_user)
    p_id = mat.id

    # Disconnect any referencing drafts to prevent foreign key errors
    drafts = session.exec(
        select(Draft).where(
            Draft.source_material_id == p_id,
            Draft.user_id == current_user.id,
        )
    ).all()
    for d in drafts:
        d.source_material_id = None
        session.add(d)

    session.delete(mat)
    session.commit()

    return {
        "success": True,
        "message": "Material deleted successfully.",
        "id": str(p_id),
    }
