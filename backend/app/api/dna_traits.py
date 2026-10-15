from app.api.dna_common import *  # noqa: F401,F403
from app.api.dna_common import (  # noqa: F401
    get_cognitive_engine,
    get_current_user,
    get_diff_agent,
    get_session,
    _trusted_user_id,
)
@router.get("/benchmarks", response_model=List[Dict[str, Any]])
def get_benchmarks(
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Returns saved benchmark blueprints owned by the caller.
    """
    trusted_user_id = _trusted_user_id(user_id, current_user)
    return MemoryService.get_benchmark_blueprints(user_id=trusted_user_id, session=session)


@router.get("/skills", response_model=List[Dict[str, Any]])
def get_skills(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Returns registered sandboxed skills.
    """
    return get_skill_manager().list_skills()


@router.get("/profile", response_model=CognitiveProfile)
def get_cognitive_profile(
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveProfile:
    """
    Get the full cognitive profile for the authenticated user.
    """
    trusted_user_id = _trusted_user_id(user_id, current_user)
    return CognitiveService.get_or_create_user_profile(session, trusted_user_id)


@router.post("/traits/pin", response_model=CognitiveTrait)
def pin_cognitive_trait(
    payload: TraitActionRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    user_id = _trusted_user_id(payload.user_id, current_user)
    trait = CognitiveService.pin_trait(session, payload.trait_id, user_id)
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.post("/traits/unpin", response_model=CognitiveTrait)
def unpin_cognitive_trait(
    payload: TraitActionRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    user_id = _trusted_user_id(payload.user_id, current_user)
    trait = CognitiveService.unpin_trait(session, payload.trait_id, user_id)
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.post("/traits/suppress", response_model=CognitiveTrait)
def suppress_cognitive_trait(
    payload: TraitActionRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    user_id = _trusted_user_id(payload.user_id, current_user)
    trait = CognitiveService.suppress_trait(session, payload.trait_id, user_id)
    if not trait:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return trait


@router.post("/traits", response_model=CognitiveTrait)
def add_custom_cognitive_trait(
    payload: AddTraitRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CognitiveTrait:
    user_id = _trusted_user_id(payload.user_id, current_user)
    if not payload.statement.strip():
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    return CognitiveService.add_custom_trait(
        session=session,
        dimension=payload.dimension,
        statement=payload.statement.strip(),
        user_id=user_id,
    )


@router.delete("/traits/{trait_id}")
def delete_cognitive_trait(
    trait_id: str,
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    trusted_user_id = _trusted_user_id(user_id, current_user)
    success = CognitiveService.delete_trait(session, trait_id, trusted_user_id)
    if not success:
        raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
    return {"success": True, "message": f"Trait '{trait_id}' deleted successfully."}


