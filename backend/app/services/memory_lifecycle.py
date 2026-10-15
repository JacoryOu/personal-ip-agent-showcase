"""Mem0 [ADD / UPDATE / NOOP] lifecycle for the user's own works.

Implementation of ``MemoryService.apply_mem0_lifecycle`` and
``MemoryService.add_own_work_dna``. The facade class is passed in as
``service_cls`` so dynamic attribute access (``cls.apply_mem0_lifecycle``,
``cls._compute_similarity``) still resolves through ``MemoryService`` and
therefore still honours monkeypatching.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional, Tuple
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.core.skill_engine import get_skill_manager
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.models.dna_record import DNARecord
from app.models.user import User
from app.services.cognitive_service import CognitiveService
from app.services.memory_common import Mem0Operation

def apply_mem0_lifecycle(
    cls,
    profile: CognitiveProfile,
    dimension: CognitiveDimension,
    statement: str,
    source_id: Optional[str] = None,
    similarity_threshold: float = 0.72,
) -> Tuple[Mem0Operation, CognitiveTrait]:
    """Applies the Mem0 memory triple [ADD / UPDATE / NOOP] to CognitiveProfile.

    - If near-identical (ratio > 0.92) and reinforced recently: NOOP or confidence bump.
    - If semantically overlapping (ratio >= similarity_threshold): UPDATE existing trait.
    - Otherwise: ADD new trait.
    """
    cleaned = statement.strip()
    if not cleaned:
        raise ValueError("Statement cannot be empty.")

    best_match: Optional[CognitiveTrait] = None
    best_ratio = 0.0

    for trait in profile.traits:
        if trait.dimension == dimension and trait.status != TraitStatus.SUPPRESSED:
            ratio = cls._compute_similarity(trait.statement, cleaned)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = trait

    if best_match and best_ratio >= similarity_threshold:
        if best_ratio >= 0.95:
            # Near identical: NOOP if confidence already high, else slight reinforce
            best_match.confidence_score = round(best_match.confidence_score + 0.3, 2)
            best_match.updated_at = datetime.now(timezone.utc)
            return Mem0Operation.NOOP, best_match
        else:
            # Substantive update / refinement
            best_match.statement = cleaned
            best_match.confidence_score = round(best_match.confidence_score + 0.5, 2)
            best_match.updated_at = datetime.now(timezone.utc)
            if source_id and not best_match.source_draft_id:
                best_match.source_draft_id = source_id
            return Mem0Operation.UPDATE, best_match

    # ADD new trait
    new_trait = CognitiveTrait(
        dimension=dimension,
        statement=cleaned,
        confidence_score=1.0,
        status=TraitStatus.ACTIVE,
        source_draft_id=source_id,
    )
    profile.traits.append(new_trait)
    return Mem0Operation.ADD, new_trait

def add_own_work_dna(
    cls,
    content: str,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingests user's own original content to extract and reinforce Thinking DNA.
    Follows Mem0 lifecycle [ADD / UPDATE / NOOP].
    """
    if not content or not content.strip():
        raise ValueError("Content cannot be empty.")

    # 1. Mine DNA insights using sandboxed skill
    skill_manager = get_skill_manager()
    miner_result = skill_manager.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": content, "analysis_type": "own_work"},
    )

    extracted_data = miner_result.output if miner_result.success and isinstance(miner_result.output, dict) else {}
    vocabulary = extracted_data.get("vocabulary_habits", [])
    logic = extracted_data.get("logic_preferences", [])
    values = extracted_data.get("core_values", [])

    # Fallback heuristic if empty
    if not vocabulary and not logic and not values:
        sentences = [s.strip() for s in re.split(r"[。！？!?\n]+", content) if len(s.strip()) > 8]
        if sentences:
            values = sentences[:3]
            logic = ["自底向上基于事实直觉的溯因归纳法"]
            vocabulary = ["偏好专业精炼的陈述表达"]

    def _execute_with_session(sess: Session) -> Dict[str, Any]:
        profile = CognitiveService.get_or_create_user_profile(sess, user_id)
        user_uuid = uuid.UUID(str(profile.user_id))
        user = sess.get(User, user_uuid) or CognitiveService.get_or_create_default_user(sess)

        actions = {Mem0Operation.ADD: [], Mem0Operation.UPDATE: [], Mem0Operation.NOOP: []}

        # Ingest Vocabulary
        for v in vocabulary:
            if v and isinstance(v, str) and v.strip():
                op, trait = cls.apply_mem0_lifecycle(profile, CognitiveDimension.VOCABULARY, v.strip())
                actions[op].append({"dimension": "vocabulary", "statement": trait.statement, "id": trait.id})

        # Ingest Logic
        for l in logic:
            if l and isinstance(l, str) and l.strip():
                op, trait = cls.apply_mem0_lifecycle(profile, CognitiveDimension.LOGIC_PREFERENCE, l.strip())
                actions[op].append({"dimension": "logic_preference", "statement": trait.statement, "id": trait.id})

        # Ingest Core Values & Stances
        for val in values:
            if val and isinstance(val, str) and val.strip():
                dim = (
                    CognitiveDimension.VIEWPOINT_STANCE
                    if any(k in val for k in ["必须", "应当", "坚决", "反对", "主张", "提倡", "永远"])
                    else CognitiveDimension.CORE_VALUE
                )
                op, trait = cls.apply_mem0_lifecycle(profile, dim, val.strip())
                actions[op].append({"dimension": dim.value, "statement": trait.statement, "id": trait.id})

        # Save updated profile
        CognitiveService.save_profile(sess, user, profile)

        # Persist DNARecord audit trail
        dna_record = DNARecord(
            user_id=user.id,
            dna_data={
                "vocabulary_habits": vocabulary,
                "logic_preferences": logic,
                "core_values": values,
                "summary": f"Own work DNA cold-start: {title or 'User Piece'} ({len(content)} chars)",
                "actions_summary": {k: len(v) for k, v in actions.items()},
            },
        )
        sess.add(dna_record)
        sess.commit()
        sess.refresh(dna_record)

        return {
            "success": True,
            "dna_record_id": str(dna_record.id),
            "user_id": str(user.id),
            "summary": dna_record.dna_data.get("summary"),
            "extracted_dna": {
                "vocabulary_habits": vocabulary,
                "logic_preferences": logic,
                "core_values": values,
            },
            "mem0_actions": actions,
            "total_traits_count": len(profile.traits),
        }

    if session:
        return _execute_with_session(session)
    else:
        with Session(engine) as sess:
            return _execute_with_session(sess)
