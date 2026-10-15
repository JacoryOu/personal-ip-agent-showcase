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


@router.get("", response_model=List[MaterialResponse])
@router.get("/", response_model=List[MaterialResponse], include_in_schema=False)
def list_materials(
    material_type: Optional[str] = Query(default=None, description="Filter by 'trending', 'benchmark', 'personal'"),
    status: Optional[str] = Query(default=None, description="Filter by 'inbox', 'archived', 'used', 'discarded'"),
    tag: Optional[str] = Query(default=None, description="Filter by tag keyword"),
    search: Optional[str] = Query(default=None, description="Search across title, content, or author"),
    user_id: Optional[str] = Query(
        default=None,
        description="Deprecated and ignored; materials are always scoped to the caller",
    ),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[Dict[str, Any]]:
    """List materials from the Material Vault with optional filtering.

    The result set is always restricted to the authenticated caller. The
    legacy ``user_id`` query parameter is accepted for backwards compatibility
    but is ignored, so it can no longer widen the visible scope.
    """
    if user_id:
        logger.debug("Ignoring client-supplied user_id on list_materials.")

    query = select(Material).where(Material.user_id == current_user.id)

    if material_type:
        query = query.where(Material.material_type == material_type.strip())

    if status:
        query = query.where(Material.status == status.strip())

    if search:
        kw = f"%{search.strip()}%"
        query = query.where(
            (Material.title.ilike(kw))
            | (Material.cleaned_content.ilike(kw))
            | (Material.source_author.ilike(kw))
        )

    query = query.order_by(Material.created_at.desc())

    if tag and tag.strip():
        all_materials = session.exec(query).all()
        target_tag = tag.strip().lower()
        matching_materials = [
            m for m in all_materials
            if m.tags and any(target_tag in str(t).lower() for t in m.tags)
        ]
        materials = matching_materials[offset : offset + limit]
    else:
        materials = session.exec(query.offset(offset).limit(limit)).all()

    return [_serialize_material(m) for m in materials]


@router.post("", response_model=MaterialResponse)
@router.post("/", response_model=MaterialResponse, include_in_schema=False)
def create_material(
    payload: MaterialCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Manually create a new material record (personal note, benchmark insight, or idea fragment)."""
    if payload.user_id:
        logger.debug("Ignoring client-supplied user_id on create_material.")
    target_uid = current_user.id

    content = (payload.cleaned_content or payload.raw_content or payload.title).strip()
    material = Material(
        id=uuid.uuid4(),
        user_id=target_uid,
        material_type=payload.material_type or "personal",
        source_platform=payload.source_platform or "manual",
        source_url=payload.source_url,
        source_author=payload.source_author or "本人记录",
        title=payload.title.strip(),
        raw_content=payload.raw_content,
        cleaned_content=content,
        blueprint_data=payload.blueprint_data,
        tags=payload.tags or [],
        status=payload.status or "inbox",
        meta_info=payload.meta_info or {},
    )
    session.add(material)
    session.commit()
    session.refresh(material)

    return _serialize_material(material)


