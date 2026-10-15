"""Draft archive CRUD routes."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import VALIDATION_ERROR, AppError
from app.models.draft import Draft
from app.schemas.draft_schemas import DraftArchiveItem, DraftInput, UpdateDraftRequest

from app.api.draft_common import (
    _forbidden,
    _get_owned_draft,
    _not_found,
    _reject_body_user_id,
    _resolve_draft_id,
)

router = APIRouter()


@router.get("", response_model=List[DraftArchiveItem])
@router.get("/", response_model=List[DraftArchiveItem], include_in_schema=False)
def list_drafts(
    user_id: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List the authenticated user's archived drafts, filtered by topic or keyword.

    The ``user_id`` query parameter is retained for backwards compatibility but is
    never used as an identity source: the result set is always scoped to the
    presented credential.
    """
    _reject_body_user_id(user_id, current_user)
    query = select(Draft).where(Draft.user_id == current_user.id)
    if topic:
        query = query.where(Draft.topic.ilike(f"%{topic.strip()}%"))
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.where((Draft.topic.ilike(kw)) | (Draft.original_ai_draft.ilike(kw)) | (Draft.user_final_draft.ilike(kw)))

    query = query.order_by(Draft.created_at.desc()).offset(offset).limit(limit)
    drafts = session.exec(query).all()

    return [
        {
            "id": str(d.id),
            "user_id": str(d.user_id),
            "topic": d.topic,
            "title": (d.metadata_ or {}).get("title") or d.topic,
            "summary": (d.metadata_ or {}).get("summary"),
            "content": d.user_final_draft or d.original_ai_draft,
            "original_ai_draft": d.original_ai_draft,
            "user_final_draft": d.user_final_draft,
            "word_count": (d.metadata_ or {}).get("word_count") or len((d.user_final_draft or d.original_ai_draft or "").strip()),
            "metadata": d.metadata_ or {},
            "source_material_id": str(d.source_material_id) if d.source_material_id else None,
            "benchmark_blueprint_id": d.benchmark_blueprint_id,
            "lineage_snapshot": d.lineage_snapshot or {},
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in drafts
    ]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any], include_in_schema=False)
def save_draft_archive(
    payload: Dict[str, Any],
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Save or update a creation draft in the authenticated user's archive."""
    draft_id_raw = payload.get("id")
    target_id: Optional[uuid.UUID] = None
    if draft_id_raw:
        try:
            target_id = uuid.UUID(str(draft_id_raw))
        except ValueError:
            target_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(draft_id_raw))

    _reject_body_user_id(payload.get("user_id"), current_user)
    target_user_id: uuid.UUID = current_user.id

    from app.models.user import User
    user = session.get(User, target_user_id)
    if not user:
        user = User(id=target_user_id, email="creator@cognition.engine", username="CognitiveCreator")
        session.add(user)
        session.commit()

    draft = session.get(Draft, target_id) if target_id else None
    if draft and draft.user_id != target_user_id:
        raise _forbidden()
    if draft:
        draft.topic = payload.get("topic", draft.topic)
        if "user_final_draft" in payload:
            draft.user_final_draft = payload["user_final_draft"]
        if "original_ai_draft" in payload and payload["original_ai_draft"]:
            draft.original_ai_draft = payload["original_ai_draft"]
        if "metadata_" in payload:
            draft.metadata_ = payload["metadata_"]
        if "source_material_id" in payload:
            try:
                draft.source_material_id = uuid.UUID(str(payload["source_material_id"])) if payload["source_material_id"] else None
            except Exception:
                pass
        if "benchmark_blueprint_id" in payload:
            draft.benchmark_blueprint_id = payload["benchmark_blueprint_id"]
        if "lineage_snapshot" in payload:
            draft.lineage_snapshot = payload["lineage_snapshot"]
        draft.updated_at = datetime.now(timezone.utc)
        session.add(draft)
        session.commit()
        session.refresh(draft)
    else:
        src_mat_id = None
        if payload.get("source_material_id"):
            try:
                src_mat_id = uuid.UUID(str(payload["source_material_id"]))
            except Exception:
                pass
        draft = Draft(
            id=target_id or uuid.uuid4(),
            user_id=target_user_id,
            topic=payload.get("topic", "未命名作品"),
            original_ai_draft=payload.get("original_ai_draft", payload.get("user_final_draft", "")),
            user_final_draft=payload.get("user_final_draft", ""),
            source_material_id=src_mat_id,
            benchmark_blueprint_id=payload.get("benchmark_blueprint_id"),
            lineage_snapshot=payload.get("lineage_snapshot"),
            metadata_=payload.get("metadata_", {}),
        )
        session.add(draft)
        session.commit()
        session.refresh(draft)

    return {
        "id": str(draft.id),
        "user_id": str(draft.user_id),
        "topic": draft.topic,
        "title": (draft.metadata_ or {}).get("title") or draft.topic,
        "summary": (draft.metadata_ or {}).get("summary"),
        "content": draft.user_final_draft or draft.original_ai_draft,
        "original_ai_draft": draft.original_ai_draft,
        "user_final_draft": draft.user_final_draft,
        "word_count": (draft.metadata_ or {}).get("word_count") or len((draft.user_final_draft or draft.original_ai_draft or "").strip()),
        "metadata": draft.metadata_ or {},
        "source_material_id": str(draft.source_material_id) if draft.source_material_id else None,
        "benchmark_blueprint_id": draft.benchmark_blueprint_id,
        "lineage_snapshot": draft.lineage_snapshot or {},
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.get("/{draft_id}", response_model=DraftArchiveItem)
def get_draft(
    draft_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve a single draft archive by ID."""
    draft = _get_owned_draft(session, draft_id, current_user)
    return {
        "id": str(draft.id),
        "user_id": str(draft.user_id),
        "topic": draft.topic,
        "title": (draft.metadata_ or {}).get("title") or draft.topic,
        "summary": (draft.metadata_ or {}).get("summary"),
        "content": draft.user_final_draft or draft.original_ai_draft,
        "original_ai_draft": draft.original_ai_draft,
        "user_final_draft": draft.user_final_draft,
        "word_count": (draft.metadata_ or {}).get("word_count") or len((draft.user_final_draft or draft.original_ai_draft or "").strip()),
        "metadata": draft.metadata_ or {},
        "source_material_id": str(draft.source_material_id) if draft.source_material_id else None,
        "benchmark_blueprint_id": draft.benchmark_blueprint_id,
        "lineage_snapshot": draft.lineage_snapshot or {},
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.put("/{draft_id}", response_model=DraftArchiveItem)
@router.patch("/{draft_id}", response_model=DraftArchiveItem)
def update_draft(
    draft_id: str,
    payload: UpdateDraftRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a draft's user edits, topic, title, or metadata."""
    draft = _get_owned_draft(session, draft_id, current_user)

    if payload.topic is not None:
        draft.topic = payload.topic.strip()
    if payload.user_final_draft is not None:
        draft.user_final_draft = payload.user_final_draft
    if payload.original_ai_draft is not None:
        draft.original_ai_draft = payload.original_ai_draft

    current_meta = dict(draft.metadata_ or {})
    if payload.title is not None:
        current_meta["title"] = payload.title.strip()
    if payload.metadata:
        current_meta.update(payload.metadata)

    content = draft.user_final_draft or draft.original_ai_draft or ""
    current_meta["word_count"] = len(content.strip())
    draft.metadata_ = current_meta

    draft.updated_at = datetime.now(timezone.utc)
    session.add(draft)
    session.commit()
    session.refresh(draft)

    return {
        "id": str(draft.id),
        "user_id": str(draft.user_id),
        "topic": draft.topic,
        "title": (draft.metadata_ or {}).get("title") or draft.topic,
        "summary": (draft.metadata_ or {}).get("summary"),
        "content": draft.user_final_draft or draft.original_ai_draft,
        "original_ai_draft": draft.original_ai_draft,
        "user_final_draft": draft.user_final_draft,
        "word_count": (draft.metadata_ or {}).get("word_count") or len((draft.user_final_draft or draft.original_ai_draft or "").strip()),
        "metadata": draft.metadata_ or {},
        "source_material_id": str(draft.source_material_id) if draft.source_material_id else None,
        "benchmark_blueprint_id": draft.benchmark_blueprint_id,
        "lineage_snapshot": draft.lineage_snapshot or {},
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.delete("/{draft_id}")
def delete_draft(
    draft_id: str,
    user_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete one of the authenticated user's drafts from the archive.

    The ``user_id`` query parameter is kept for backwards compatibility only; it is
    never trusted as an identity or authorization source.
    """
    _reject_body_user_id(user_id, current_user)
    draft = _get_owned_draft(session, draft_id, current_user)
    t_id = draft.id

    from app.models.dna_record import DNARecord
    from app.models.feedback import DraftFeedback
    # Nullify references in DNARecord to prevent DB foreign key constraint violations
    records = session.exec(select(DNARecord).where(DNARecord.draft_id == t_id)).all()
    for r in records:
        r.draft_id = None
        session.add(r)

    # Delete associated DraftFeedback records to prevent FK violations
    feedbacks = session.exec(select(DraftFeedback).where(DraftFeedback.draft_id == t_id)).all()
    for fb in feedbacks:
        session.delete(fb)

    session.delete(draft)
    session.commit()
    return {
        "success": True,
        "message": f"Draft '{draft_id}' deleted successfully.",
        "id": str(draft_id),
    }
