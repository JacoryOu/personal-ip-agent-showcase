"""Thinking DNA evolution: time naturalisation and trait supersession."""

from datetime import datetime, timezone
from typing import Optional

from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveTrait,
    TraitStatus,
)
from app.services.cognitive_service import CognitiveService

def naturalize_time_expression(occurred_at: datetime, mode: str = "fuzzy") -> str:
    """Converts absolute datetime to natural Chinese time expression.

    Modes:
      'invisible' -> '' (no time hint)
      'fuzzy'     -> '之前有段时间' / '最近' / '前两年'
      'solar_term'-> '去年深秋那阵子' / '初春时节' etc.
    """
    if mode == "invisible":
        return ""

    now = datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    delta = now - occurred_at
    days = delta.days

    if mode == "fuzzy":
        if days <= 7:
            return "最近"
        elif days <= 60:
            return "最近这段时间"
        elif days <= 365:
            return "之前有段时间"
        elif days <= 730:
            return "前一年"
        else:
            return "前两年"

    if mode == "solar_term":
        month = occurred_at.month
        year_delta = now.year - occurred_at.year
        prefix = "去年" if year_delta == 1 else ("前年" if year_delta == 2 else ("今年" if year_delta == 0 else f"{year_delta}年前"))

        if month in (3, 4):
            season = "初春时节"
        elif month in (5, 6):
            season = "初夏那阵子"
        elif month in (7, 8):
            season = "盛夏时节"
        elif month == 9:
            season = "初秋时节"
        elif month in (10, 11):
            season = "深秋那阵子"
        else:
            season = "冬日时节"

        if year_delta == 0:
            return season
        return f"{prefix}{season}"

    if mode == "anniversary":
        year_delta = now.year - occurred_at.year
        if year_delta <= 1:
            return "一年前的今天"
        elif year_delta == 2:
            return "两年前的今天"
        else:
            return f"{year_delta}年前的今天"

    return ""


def supersede_dna_trait(
    old_trait_id: str,
    new_content: str,
    evolution_reason: str,
    session,
    user_id=None,
) -> dict:
    """Marks an existing CognitiveTrait as 'superseded' and creates a new V2 active trait.

    Returns a dict with old_trait_id, new_trait_id, and evolution metadata.
    """
    from app.services.cognitive_service import CognitiveService
    from app.domain.cognitive.models import CognitiveDimension, TraitStatus

    profile = CognitiveService.get_or_create_user_profile(session, user_id)
    old_trait = profile.find_trait(old_trait_id)
    if not old_trait:
        raise ValueError(f"Trait {old_trait_id} not found in profile.")

    # Mark old trait superseded
    old_trait.trait_status = "superseded"
    old_trait.status = TraitStatus.SUPPRESSED

    # Create new V2 trait
    from app.domain.cognitive.models import CognitiveTrait
    new_trait = CognitiveTrait(
        dimension=old_trait.dimension,
        statement=new_content.strip(),
        confidence_score=old_trait.confidence_score,
        status=TraitStatus.ACTIVE,
        version=getattr(old_trait, "version", 1) + 1,
        trait_status="active",
        superseded_by_id=None,
        evolution_reason=evolution_reason,
        occurred_at=datetime.now(timezone.utc),
    )
    old_trait.superseded_by_id = new_trait.id
    profile.traits.append(new_trait)

    # Persist
    from app.models.user import User
    import uuid
    user_uuid = uuid.UUID(str(profile.user_id))
    user = session.get(User, user_uuid)
    if user:
        CognitiveService.save_profile(session, user, profile)

    return {
        "old_trait_id": old_trait_id,
        "new_trait_id": new_trait.id,
        "new_version": new_trait.version,
        "evolution_reason": evolution_reason,
        "old_statement": old_trait.statement,
        "new_statement": new_trait.statement,
    }
