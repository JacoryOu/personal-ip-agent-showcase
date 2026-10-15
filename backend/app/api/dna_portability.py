from app.api.dna_common import *  # noqa: F401,F403
from app.api.dna_common import (  # noqa: F401
    get_cognitive_engine,
    get_current_user,
    get_diff_agent,
    get_session,
    _trusted_user_id,
)

@router.get("/records", response_model=List[dict])
def list_dna_records(
    session: Session = Depends(get_session),
    limit: int = 20,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[dict]:
    # DNARecord rows are private to their owner, so the listing is filtered by
    # the authenticated identity instead of returning every user's records.
    records = session.exec(
        select(DNARecord)
        .where(col(DNARecord.user_id) == current_user.id)
        .order_by(DNARecord.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "draft_id": str(r.draft_id) if r.draft_id else None,
            "dna_data": r.dna_data,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/traits", response_model=List[CognitiveTrait])
def list_cognitive_traits(
    dimension: Optional[CognitiveDimension] = Query(default=None),
    status: Optional[TraitStatus] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[CognitiveTrait]:
    """List and filter individual cognitive traits in user profile."""
    trusted_user_id = _trusted_user_id(user_id, current_user)
    profile = CognitiveService.get_or_create_user_profile(session, trusted_user_id)
    return profile.get_traits(dimension=dimension, status=status)


@router.put("/traits/{trait_id}", response_model=CognitiveTrait)
@router.patch("/traits/{trait_id}", response_model=CognitiveTrait)
def update_cognitive_trait(
    trait_id: str,
    payload: UpdateTraitRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    """Update an existing trait's statement, dimension, status, or confidence score."""
    user_id = _trusted_user_id(payload.user_id, current_user)
    trait = CognitiveService.update_trait(
        session=session,
        trait_id=trait_id,
        statement=payload.statement,
        dimension=payload.dimension,
        status=payload.status,
        confidence_score=payload.confidence_score,
        user_id=user_id,
    )
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.post("/traits/{trait_id}/toggle", response_model=CognitiveTrait)
def toggle_cognitive_trait_by_id(
    trait_id: str,
    enabled: Optional[bool] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    """Toggle a trait between active and suppressed status."""
    trusted_user_id = _trusted_user_id(user_id, current_user)
    trait = CognitiveService.toggle_trait(
        session=session,
        trait_id=trait_id,
        user_id=trusted_user_id,
        enable=enabled,
    )
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.post("/traits/toggle", response_model=CognitiveTrait)
def toggle_cognitive_trait(
    payload: ToggleTraitRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    """Toggle trait status via payload."""
    user_id = _trusted_user_id(payload.user_id, current_user)
    trait = CognitiveService.toggle_trait(
        session=session,
        trait_id=payload.trait_id,
        user_id=user_id,
        enable=payload.enabled,
    )
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.get("/export", response_model=Dict[str, Any])
def export_thinking_dna_json(
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Export complete user Thinking DNA profile and traits as JSON."""
    trusted_user_id = _trusted_user_id(user_id, current_user)
    return CognitiveService.export_profile_json(session=session, user_id=trusted_user_id)


@router.post("/import", response_model=CognitiveProfile)
def import_thinking_dna_json(
    payload: ImportDNARequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveProfile:
    """Import Thinking DNA traits or profile from JSON."""
    user_id = _trusted_user_id(payload.user_id, current_user)
    return CognitiveService.import_profile_json(
        session=session,
        data={
            "traits": payload.traits or [],
            "thinking_dna": payload.thinking_dna.model_dump() if payload.thinking_dna else None,
        },
        user_id=user_id,
        mode=payload.mode,
    )


@router.post("/conflicts/detect", response_model=Dict[str, Any])
@router.post("/detect-conflicts", response_model=Dict[str, Any])
def detect_viewpoint_conflicts(
    payload: Optional[DetectConflictsRequest] = None,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Detects viewpoint and stance conflicts between candidate claims/draft content
    and user's authentic Thinking DNA traits.
    """
    req = payload or DetectConflictsRequest()
    user_id = _trusted_user_id(req.user_id, current_user)
    return MemoryService.detect_viewpoint_conflicts(
        session=session,
        user_id=user_id,
        statement=req.statement,
        statements=req.statements,
        draft_content=req.draft_content,
    )
