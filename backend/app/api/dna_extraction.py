from app.api.dna_common import *  # noqa: F401,F403
from app.api.dna_common import (  # noqa: F401
    get_cognitive_engine,
    get_current_user,
    get_diff_agent,
    get_session,
    _trusted_user_id,
)
@router.post("/extract", response_model=DNAExtractionOutput)
async def extract_thinking_dna(
    payload: DiffInput,
    session: Session = Depends(get_session),
    agent: DiffAgent = Depends(get_diff_agent),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DNAExtractionOutput:
    """
    Extract Thinking DNA by analyzing the differences between an AI draft
    and the user's final edited draft. Delegates to CognitiveEngine.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    original_ai_draft = payload.original_ai_draft
    user_final_draft = payload.user_final_draft

    if payload.draft_id:
        target_draft = session.get(Draft, payload.draft_id)
        if not target_draft:
            raise AppError(code=NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        if normalize_user_id(target_draft.user_id) != current_user.id:
            raise AppError(code=FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN)
        if not original_ai_draft:
            original_ai_draft = target_draft.original_ai_draft
        if not user_final_draft:
            user_final_draft = target_draft.user_final_draft or target_draft.original_ai_draft

    if not original_ai_draft or not original_ai_draft.strip():
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not user_final_draft or not user_final_draft.strip():
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    try:
        return await engine.evolve_with_diff(
            original_ai_draft=original_ai_draft,
            user_final_draft=user_final_draft,
            topic=payload.topic,
            draft_id=payload.draft_id,
            # evolve_with_diff writes Draft/DNARecord rows whose user_id column
            # is a UUID, so hand the engine the UUID identity, not its string
            # rendering.
            user_id=current_user.id,
            viewpoint_judgments=payload.viewpoint_judgments,
            agent=agent,
            session=session,
        )
    except AppError:
        raise
    except ValueError as e:
        # Expected business failure (e.g. identical drafts). The message can
        # embed internal wording, so only the public contract is returned.
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from e
    except Exception as e:
        # Underlying SDK / DB / filesystem text stays server-side; the global
        # handler logs it together with the request id.
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


@router.post("/ingest-own-work")
def ingest_own_work(
    payload: IngestOwnWorkRequest,
    session: Session = Depends(get_session),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Cold-start personal Thinking DNA by ingesting user's own original works
    via raw text or web link.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    target = payload.content or payload.url
    if not target or not target.strip():
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        return engine.ingest_own_works_for_dna(
            content_or_url=target.strip(),
            user_id=user_id,
            title=payload.title,
            session=session,
        )
    except AppError:
        raise
    except ValueError as e:
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from e
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


@router.post("/deconstruct-benchmark")
def deconstruct_benchmark(
    payload: DeconstructBenchmarkRequest,
    session: Session = Depends(get_session),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Deconstructs external benchmark article into Blueprint Skeletons & Clash Points.
    Guaranteed zero cognitive profile alteration.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    target = payload.content or payload.url
    if not target or not target.strip():
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        return engine.deconstruct_benchmark_article(
            content_or_url=target.strip(),
            user_id=user_id,
            title=payload.title,
            session=session,
        )
    except AppError:
        raise
    except ValueError as e:
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from e
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


@router.post("/dialogue-clash")
def record_dialogue_clash(
    payload: DialogueClashRequest,
    session: Session = Depends(get_session),
    engine: CognitiveEngine = Depends(get_cognitive_engine),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Captures user's refutations and debates against opponent viewpoints into Thinking DNA.
    """
    user_id = _trusted_user_id(payload.user_id, current_user)
    if not payload.messages:
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        return engine.record_dialogue_clash(
            messages=payload.messages,
            user_id=user_id,
            debate_topic=payload.debate_topic,
            session=session,
        )
    except AppError:
        raise
    except ValueError as e:
        raise AppError(code=VALIDATION_ERROR, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from e
    except Exception as e:
        raise AppError(code=INTERNAL_ERROR, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


