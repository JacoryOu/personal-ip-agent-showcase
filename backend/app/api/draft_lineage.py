"""Draft lineage route."""
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import AppError

from app.api.draft_common import _get_owned_draft, _not_found, _resolve_draft_id

router = APIRouter()


@router.get("/{draft_id}/lineage", response_model=Dict[str, Any])
def get_draft_lineage(
    draft_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns full provenance and lineage graph for a draft:
    origin material, source author/platform, benchmark blueprint bones, and Thinking DNA used.
    """
    draft = _get_owned_draft(session, draft_id, current_user)
    t_id = draft.id

    # Resolve source material (with resilient fallback to lineage_snapshot if material was deleted or unlinked)
    source_mat_info = None
    mat = None
    if draft.source_material_id:
        from app.models.material import Material
        mat = session.get(Material, draft.source_material_id)
        if mat:
            source_mat_info = {
                "id": str(mat.id),
                "title": mat.title,
                "material_type": mat.material_type,
                "source_platform": mat.source_platform,
                "source_url": mat.source_url,
                "source_author": mat.source_author,
                "cleaned_content": mat.cleaned_content[:200] + ("..." if len(mat.cleaned_content) > 200 else ""),
                "tags": mat.tags or [],
                "status": mat.status,
            }
    if not source_mat_info and draft.lineage_snapshot and draft.lineage_snapshot.get("source_title"):
        source_mat_info = {
            "id": draft.lineage_snapshot.get("source_material_id"),
            "title": draft.lineage_snapshot.get("source_title"),
            "material_type": draft.lineage_snapshot.get("material_type", "benchmark"),
            "source_platform": draft.lineage_snapshot.get("source_platform"),
            "source_url": draft.lineage_snapshot.get("source_url"),
            "source_author": draft.lineage_snapshot.get("source_author"),
            "cleaned_content": "",
            "tags": [],
            "status": "archived_snapshot",
        }

    # Resolve benchmark blueprint
    blueprint_info = None
    bp_id = draft.benchmark_blueprint_id or (draft.lineage_snapshot or {}).get("benchmark_blueprint_id")
    if bp_id:
        from app.services.memory_service import MemoryService
        blueprints = MemoryService.get_benchmark_blueprints(user_id=draft.user_id, session=session)
        for bp in blueprints:
            if str(bp.get("id")) == str(bp_id):
                blueprint_info = bp
                break

    if not blueprint_info and mat and mat.blueprint_data:
        blueprint_info = mat.blueprint_data
    elif not blueprint_info and draft.lineage_snapshot and draft.lineage_snapshot.get("blueprint_title"):
        blueprint_info = {
            "id": bp_id or "snapshot_bp",
            "title": draft.lineage_snapshot.get("blueprint_title"),
            "hook_style": draft.lineage_snapshot.get("inspiration_hook"),
            "emotional_arc": draft.lineage_snapshot.get("emotional_arc"),
        }

    # Resolve thinking DNA used
    dna_info = (draft.metadata_ or {}).get("injected_dna")
    if not dna_info:
        from app.models.dna_record import DNARecord
        rec = session.exec(select(DNARecord).where(DNARecord.draft_id == t_id)).first()
        if rec and rec.dna_data:
            dna_info = rec.dna_data

    return {
        "draft_id": str(draft.id),
        "topic": draft.topic,
        "title": (draft.metadata_ or {}).get("title") or draft.topic,
        "source_material_id": str(draft.source_material_id) if draft.source_material_id else None,
        "source_material": source_mat_info,
        "benchmark_blueprint_id": bp_id,
        "benchmark_blueprint": blueprint_info,
        "thinking_dna_used": dna_info,
        "lineage_snapshot": draft.lineage_snapshot or {},
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }
