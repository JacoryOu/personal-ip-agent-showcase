"""Closed-loop DNA evolution and trait curation.

Split out of ``cognitive_service``; behaviour is unchanged and the original
module re-exposes the same methods through the ``CognitiveService`` facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlmodel import Session

from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.models.user import User
from app.schemas.diff_schemas import ThinkingDNA
from app.services.cognitive_common import _parse_user_id



class CognitiveEvolutionMixin:


    @classmethod
    def sync_extracted_dna(
        cls,
        session: Session,
        user_id: Optional[uuid.UUID | str],
        thinking_dna: ThinkingDNA,
        source_draft_id: Optional[str] = None,
    ) -> CognitiveProfile:
        """
        Incorporates newly extracted Thinking DNA into the user's CognitiveProfile.
        Reinforces existing traits (increasing confidence) or registers new traits.
        """
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        if not user:
            user = cls.get_or_create_default_user(session)

        profile = cls.get_or_create_user_profile(session, user.id)

        # Reinforce/add vocabulary
        for v in thinking_dna.vocabulary_habits:
            if v and v.strip():
                profile.add_or_reinforce_trait(
                    CognitiveDimension.VOCABULARY, v.strip(), source_draft_id=source_draft_id
                )

        # Reinforce/add logic
        for l in thinking_dna.logic_preferences:
            if l and l.strip():
                profile.add_or_reinforce_trait(
                    CognitiveDimension.LOGIC_PREFERENCE, l.strip(), source_draft_id=source_draft_id
                )

        # Reinforce/add core values and viewpoints
        for c in thinking_dna.core_values:
            if c and c.strip():
                dim = (
                    CognitiveDimension.VIEWPOINT_STANCE
                    if "主张:" in c or "关于「" in c
                    else CognitiveDimension.CORE_VALUE
                )
                profile.add_or_reinforce_trait(dim, c.strip(), source_draft_id=source_draft_id)

        cls.save_profile(session, user, profile)
        return profile


    @classmethod
    def evolve_traits_from_feedback(
        cls,
        session: Session,
        user_id: Optional[uuid.UUID | str],
        resonant_ideas: List[str],
        source_draft_id: Optional[str] = None,
        delta: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically boosts confidence scores of existing CognitiveProfile traits based on audience resonance,
        or registers new reinforced traits when strong resonance occurs.
        """
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        if not user:
            user = cls.get_or_create_default_user(session)

        profile = cls.get_or_create_user_profile(session, user.id)
        boosted_records: List[Dict[str, Any]] = []
        boosted_trait_ids: set[str] = set()

        for idea in resonant_ideas:
            if not isinstance(idea, str) or not idea.strip():
                continue
            cleaned_idea = idea.strip()
            matched_trait = None

            # 1. Look for semantic / token / substring overlap in existing traits
            tokens = [w for w in re.split(r"[\s,，.。;；:：“”\"']+", cleaned_idea) if len(w) >= 2]
            for trait in profile.traits:
                if trait.status == TraitStatus.SUPPRESSED:
                    continue
                # Substring match
                if trait.statement.lower() in cleaned_idea.lower() or cleaned_idea.lower() in trait.statement.lower():
                    matched_trait = trait
                    break
                # Keyword overlap (>= 2 significant keywords)
                matching_tokens = [w for w in tokens if w.lower() in trait.statement.lower()]
                if len(matching_tokens) >= 2:
                    matched_trait = trait
                    break

            if matched_trait:
                if matched_trait.id in boosted_trait_ids:
                    continue
                boosted_trait_ids.add(matched_trait.id)
                old_conf = matched_trait.confidence_score
                profile.boost_trait_confidence(matched_trait.id, delta=delta)
                dim_str = matched_trait.dimension.value if hasattr(matched_trait.dimension, "value") else str(matched_trait.dimension)
                boosted_records.append({
                    "id": str(matched_trait.id),
                    "statement": matched_trait.statement,
                    "dimension": dim_str,
                    "old_confidence": old_conf,
                    "new_confidence": matched_trait.confidence_score,
                    "boost_amount": delta,
                    "reason": f"读者共鸣呼应：「{cleaned_idea[:60]}」",
                })
            else:
                # Register new reinforced viewpoint or value trait from high reader resonance
                dim = (
                    CognitiveDimension.VIEWPOINT_STANCE
                    if any(k in cleaned_idea for k in ["主张", "观点", "认为", "立场", "坚信", "应该"])
                    else CognitiveDimension.CORE_VALUE
                )
                now_utc = datetime.now(timezone.utc)
                new_trait = CognitiveTrait(
                    dimension=dim,
                    statement=cleaned_idea,
                    confidence_score=round(1.0 + delta, 2),
                    status=TraitStatus.ACTIVE,
                    source_draft_id=source_draft_id,
                    evolution_boost_count=1,
                    last_boosted_at=now_utc,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                profile.traits.append(new_trait)
                boosted_trait_ids.add(new_trait.id)
                dim_str = new_trait.dimension.value if hasattr(new_trait.dimension, "value") else str(new_trait.dimension)
                boosted_records.append({
                    "id": str(new_trait.id),
                    "statement": new_trait.statement,
                    "dimension": dim_str,
                    "old_confidence": 1.0,
                    "new_confidence": new_trait.confidence_score,
                    "boost_amount": delta,
                    "reason": f"读者新发现高共鸣认知：「{cleaned_idea[:60]}」",
                })

        cls.save_profile(session, user, profile)
        return boosted_records


    @classmethod
    def pin_trait(
        cls, session: Session, trait_id: str, user_id: Optional[uuid.UUID | str] = None
    ) -> Optional[CognitiveTrait]:
        """Pins a trait to prioritize it for generation."""
        profile = cls.get_or_create_user_profile(session, user_id)
        success = profile.pin_trait(trait_id)
        if not success:
            return None
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return profile.find_trait(trait_id)


    @classmethod
    def unpin_trait(
        cls, session: Session, trait_id: str, user_id: Optional[uuid.UUID | str] = None
    ) -> Optional[CognitiveTrait]:
        """Unpins a trait."""
        profile = cls.get_or_create_user_profile(session, user_id)
        success = profile.unpin_trait(trait_id)
        if not success:
            return None
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return profile.find_trait(trait_id)


    @classmethod
    def suppress_trait(
        cls, session: Session, trait_id: str, user_id: Optional[uuid.UUID | str] = None
    ) -> Optional[CognitiveTrait]:
        """Suppresses a trait so it will not be injected into generation."""
        profile = cls.get_or_create_user_profile(session, user_id)
        success = profile.suppress_trait(trait_id)
        if not success:
            return None
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return profile.find_trait(trait_id)


    @classmethod
    def delete_trait(
        cls, session: Session, trait_id: str, user_id: Optional[uuid.UUID | str] = None
    ) -> bool:
        """Permanently removes a trait from the profile."""
        profile = cls.get_or_create_user_profile(session, user_id)
        before_len = len(profile.traits)
        profile.traits = [t for t in profile.traits if t.id != trait_id]
        if len(profile.traits) == before_len:
            return False
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return True


    @classmethod
    def add_custom_trait(
        cls,
        session: Session,
        dimension: CognitiveDimension,
        statement: str,
        user_id: Optional[uuid.UUID | str] = None,
    ) -> CognitiveTrait:
        """Manually registers a custom cognitive trait."""
        profile = cls.get_or_create_user_profile(session, user_id)
        trait = profile.add_or_reinforce_trait(dimension, statement)
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return trait


    @classmethod
    def update_trait(
        cls,
        session: Session,
        trait_id: str,
        statement: Optional[str] = None,
        dimension: Optional[CognitiveDimension] = None,
        status: Optional[TraitStatus] = None,
        confidence_score: Optional[float] = None,
        user_id: Optional[uuid.UUID | str] = None,
    ) -> Optional[CognitiveTrait]:
        """Updates an existing cognitive trait."""
        profile = cls.get_or_create_user_profile(session, user_id)
        updated = profile.update_trait(
            trait_id=trait_id,
            statement=statement,
            dimension=dimension,
            status=status,
            confidence_score=confidence_score,
        )
        if not updated:
            return None
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return updated


    @classmethod
    def toggle_trait(
        cls,
        session: Session,
        trait_id: str,
        user_id: Optional[uuid.UUID | str] = None,
        enable: Optional[bool] = None,
    ) -> Optional[CognitiveTrait]:
        """Toggles trait between active and suppressed."""
        profile = cls.get_or_create_user_profile(session, user_id)
        toggled = profile.toggle_trait(trait_id, enable=enable)
        if not toggled:
            return None
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)
        cls.save_profile(session, user, profile)
        return toggled

